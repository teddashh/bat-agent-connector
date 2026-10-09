mod support;
use bat_fleet_core::{
    configuration::Configuration,
    process_adapter::{HeldProcess, LoginIdentity, ProcessSnapshot, TunnelRecord},
    selection_io::{Snapshot, Store},
    tunnel::{self, Context, Plan, Platform, SpawnFailure},
    Result,
};
use std::{
    cell::Cell,
    path::{Path, PathBuf},
    rc::Rc,
};
use support::Fixture;
const EPOCH: &str = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";

struct Child {
    snapshot: ProcessSnapshot,
    stops: Rc<Cell<u32>>,
    uncertain_stop: bool,
}
impl HeldProcess for Child {
    fn snapshot(&self) -> Result<ProcessSnapshot> {
        Ok(self.snapshot.clone())
    }
    fn terminate_and_wait(&mut self) -> Result<()> {
        self.stops.set(self.stops.get() + 1);
        if self.uncertain_stop {
            Err("STOP_UNCONFIRMED")
        } else {
            Ok(())
        }
    }
}
struct Adapter {
    executable: PathBuf,
    parent: ProcessSnapshot,
    spawns: usize,
    stops: Rc<Cell<u32>>,
    failure: Option<SpawnFailure>,
    occupied: bool,
    uncertain_stop: bool,
    on_spawn: Option<Box<dyn FnMut()>>,
}
impl Platform for Adapter {
    type Child = Child;
    fn owner(&mut self, epoch: &str) -> Result<ProcessSnapshot> {
        assert_eq!(epoch, EPOCH);
        Ok(self.parent.clone())
    }
    fn endpoint_free(&mut self, _: std::net::SocketAddrV4) -> Result<()> {
        if self.occupied {
            Err("ENDPOINT_IN_USE")
        } else {
            Ok(())
        }
    }
    fn executable(&self) -> &Path {
        &self.executable
    }
    fn spawn(&mut self, plan: &Plan) -> std::result::Result<Child, SpawnFailure> {
        self.spawns += 1;
        if let Some(error) = self.failure.take() {
            return Err(error);
        }
        if let Some(hook) = &mut self.on_spawn {
            hook();
        }
        Ok(Child {
            snapshot: ProcessSnapshot {
                pid: 222,
                created_filetime: 2000000,
                executable: self.executable.to_str().unwrap().into(),
                arguments: plan.arguments().to_vec(),
                login: self.parent.login.clone(),
            },
            stops: self.stops.clone(),
            uncertain_stop: self.uncertain_stop,
        })
    }
}
fn fixture() -> (Fixture, Configuration, Store, Snapshot, Plan, Adapter) {
    let fixture = Fixture::new();
    let config = fixture.load();
    let store = Store::new(fixture.0.clone());
    let selection = store.read(&config).unwrap();
    let host = &config.inventory.hosts()[0];
    let plan = Plan::new(
        &config,
        &selection,
        host["name"].as_str().unwrap(),
        host["routes"][0]["alias"].as_str().unwrap(),
        EPOCH,
    )
    .unwrap();
    let adapter = Adapter {
        executable: fixture.0.join("system/ssh.exe"),
        parent: ProcessSnapshot {
            pid: 111,
            created_filetime: 1000000,
            executable: fixture.0.join("dashboard.exe").to_str().unwrap().into(),
            arguments: vec!["--fleet-supervisor".into()],
            login: LoginIdentity {
                owner_sid: "S-1-5-21-123-456-789-1001".into(),
                session_id: 1,
            },
        },
        spawns: 0,
        stops: Rc::new(Cell::new(0)),
        failure: None,
        occupied: false,
        uncertain_stop: false,
        on_spawn: None,
    };
    (fixture, config, store, selection, plan, adapter)
}
fn context<'a>(f: &'a Fixture, c: &'a Configuration, s: &'a Store, p: &'a Snapshot) -> Context<'a> {
    Context {
        configuration: c,
        store: s,
        selection: p,
        roaming: &f.0,
    }
}
fn intent(f: &Fixture, plan: &Plan) -> PathBuf {
    f.0.join("BetterAgentTerminal/fleet-tunnel-intents")
        .join(format!("{}.json", plan.name()))
}

#[test]
fn publishes_exact_child_and_parent_once_without_replacing_owner() {
    let (f, c, s, p, plan, mut a) = fixture();
    let ctx = context(&f, &c, &s, &p);
    let launched = tunnel::launch(&ctx, &plan, &mut a).unwrap();
    let saved = std::fs::read(&launched.record_path).unwrap();
    let record = TunnelRecord::parse(&saved, None).unwrap();
    assert_eq!(record.process.pid, 222);
    assert_eq!(record.origin.unwrap().pid, 111);
    assert_eq!(record.process.arguments, plan.arguments());
    assert!(!intent(&f, &plan).exists());
    assert!(matches!(
        tunnel::launch(&ctx, &plan, &mut a),
        Err("TUNNEL_START_UNSETTLED")
    ));
    assert_eq!(a.spawns, 1);
    assert_eq!(a.stops.get(), 0);
    assert_eq!(std::fs::read(&launched.record_path).unwrap(), saved);
}
#[test]
fn occupied_endpoint_and_foreign_record_never_launch_or_overwrite() {
    for record in [false, true] {
        let (f, c, s, p, plan, mut a) = fixture();
        let ctx = context(&f, &c, &s, &p);
        let path =
            f.0.join("BetterAgentTerminal/fleet-tunnel-owners")
                .join(format!("{}.json", plan.name()));
        if record {
            std::fs::create_dir_all(path.parent().unwrap()).unwrap();
            std::fs::write(&path, b"foreign").unwrap();
        } else {
            a.occupied = true;
        }
        assert!(tunnel::launch(&ctx, &plan, &mut a).is_err());
        assert_eq!(a.spawns, 0);
        assert!(!intent(&f, &plan).exists());
        if record {
            assert_eq!(std::fs::read(path).unwrap(), b"foreign");
        }
    }
}
#[test]
fn uncertain_spawn_retains_intent_and_refuses_a_second_launch() {
    let (f, c, s, p, plan, mut a) = fixture();
    let ctx = context(&f, &c, &s, &p);
    a.failure = Some(SpawnFailure::Unconfirmed);
    assert!(matches!(
        tunnel::launch(&ctx, &plan, &mut a),
        Err("TUNNEL_START_UNSETTLED")
    ));
    let bytes = std::fs::read(intent(&f, &plan)).unwrap();
    assert!(tunnel::launch(&ctx, &plan, &mut a).is_err());
    assert_eq!(a.spawns, 1);
    assert_eq!(std::fs::read(intent(&f, &plan)).unwrap(), bytes);
}
#[test]
fn proven_spawn_failure_releases_only_its_exact_intent() {
    let (f, c, s, p, plan, mut a) = fixture();
    let ctx = context(&f, &c, &s, &p);
    a.failure = Some(SpawnFailure::NotStarted);
    assert!(matches!(
        tunnel::launch(&ctx, &plan, &mut a),
        Err("TUNNEL_START_FAILED")
    ));
    assert!(!intent(&f, &plan).exists());
    assert_eq!(a.spawns, 1);
    assert!(tunnel::launch(&ctx, &plan, &mut a).is_ok());
    assert_eq!(a.spawns, 2);
}
#[test]
fn selection_change_after_spawn_rolls_back_only_the_held_child() {
    for uncertain in [false, true] {
        let (f, c, s, p, plan, mut a) = fixture();
        let ctx = context(&f, &c, &s, &p);
        let prefs = f.0.join("BetterAgentTerminal/fleet-client.json");
        a.on_spawn = Some(Box::new(move || {
            std::fs::write(
                &prefs,
                br#"{"version":1,"connections":[],"profiles":[],"dashboard":false}"#,
            )
            .unwrap()
        }));
        a.uncertain_stop = uncertain;
        assert!(matches!(
            tunnel::launch(&ctx, &plan, &mut a),
            Err("SELECTION_CHANGED")
        ));
        assert_eq!(a.spawns, 1);
        assert_eq!(a.stops.get(), 1);
        assert_eq!(intent(&f, &plan).exists(), uncertain);
        assert!(!f
            .0
            .join("BetterAgentTerminal/fleet-tunnel-owners")
            .join(format!("{}.json", plan.name()))
            .exists());
    }
}
#[test]
fn changed_configuration_is_refused_before_an_intent_or_child() {
    let (f, c, s, p, plan, mut a) = fixture();
    let ctx = context(&f, &c, &s, &p);
    std::fs::write(f.0.join("kit/ssh-config"), b"changed").unwrap();
    assert!(matches!(
        tunnel::launch(&ctx, &plan, &mut a),
        Err("CONFIGURATION_CHANGED")
    ));
    assert_eq!(a.spawns, 0);
    assert!(!intent(&f, &plan).exists());
}
#[test]
fn plan_cannot_inject_an_alias_or_reenable_an_explicit_disconnect() {
    let (_f, c, s, p, _plan, _a) = fixture();
    let host = &c.inventory.hosts()[0];
    let id = host["name"].as_str().unwrap();
    assert!(matches!(
        Plan::new(&c, &p, id, "-ProxyCommand=anything", EPOCH),
        Err("ROUTE_NOT_CONFIGURED")
    ));
    let disconnected = s.set_connections(&c, &p, &[], None, || Ok(None)).unwrap();
    assert!(matches!(
        Plan::new(
            &c,
            &disconnected,
            id,
            host["routes"][0]["alias"].as_str().unwrap(),
            EPOCH
        ),
        Err("CONNECTION_NOT_SELECTED")
    ));
}
#[test]
fn mismatched_data_directory_does_not_use_another_selections_authority() {
    let (f, c, s, p, plan, mut a) = fixture();
    let other = Fixture::new();
    let ctx = Context {
        configuration: &c,
        store: &s,
        selection: &p,
        roaming: &other.0,
    };
    assert!(tunnel::launch(&ctx, &plan, &mut a).is_err());
    assert_eq!(a.spawns, 0);
    assert!(!intent(&f, &plan).exists());
}

#[test]
fn old_launch_plan_cannot_borrow_a_new_disconnected_snapshot() {
    let (f, c, s, p, plan, mut a) = fixture();
    let disconnected = s.set_connections(&c, &p, &[], None, || Ok(None)).unwrap();
    let ctx = context(&f, &c, &s, &disconnected);
    assert!(matches!(
        tunnel::launch(&ctx, &plan, &mut a),
        Err("SELECTION_CHANGED")
    ));
    assert_eq!(a.spawns, 0);
    assert!(!intent(&f, &plan).exists());
}
