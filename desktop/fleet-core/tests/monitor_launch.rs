use bat_fleet_core::{
    discovery::{Backend, MonitorIdentity, NativeIdentity, Observation, Ownership},
    monitor_launch::{ensure, Outcome, Platform},
    ownership::ProcessState,
    process_adapter::{LoginIdentity, ProcessSnapshot},
    tunnel::SpawnFailure,
    Result,
};
use std::{cell::Cell, path::PathBuf};

fn native() -> NativeIdentity {
    NativeIdentity::new("C:\\Apps\\Dashboard.exe", "C:\\Config\\fleet.json").unwrap()
}

#[test]
fn routing_environment_keeps_path_helpers_without_central_bat_or_proxy_secrets() {
    let values = [
        ("Path", "C:\\Tools"),
        ("SystemRoot", "C:\\Windows"),
        ("BATC_DESKTOP_TOKEN", "synthetic"),
        ("BATC_API_TOKEN", "synthetic"),
        ("BAT_TOKEN", "synthetic"),
        ("HTTPS_PROXY", "synthetic"),
        ("OTHER", "value"),
    ];
    let selected = bat_fleet_core::monitor_launch::environment(
        values.into_iter().map(|(k, v)| (k.into(), v.into())),
    );
    assert_eq!(
        selected,
        vec![
            ("Path".into(), "C:\\Tools".into()),
            ("SystemRoot".into(), "C:\\Windows".into())
        ]
    );
}
fn process() -> ProcessSnapshot {
    ProcessSnapshot {
        pid: 41,
        created_filetime: 134000000000000000,
        executable: native().executable().into(),
        arguments: native().arguments().to_vec(),
        login: LoginIdentity {
            owner_sid: "S-1-5-21-111-222-333-1001".into(),
            session_id: 2,
        },
    }
}
struct Fixture(PathBuf);
impl Fixture {
    fn new() -> Self {
        let dir = std::env::temp_dir().join(format!(
            "bac-monitor-launch-{:032x}",
            rand::random::<u128>()
        ));
        std::fs::create_dir(&dir).unwrap();
        Self(dir)
    }
    fn path(&self) -> PathBuf {
        self.0.join("bat-fleet-monitor-launch.json")
    }
}
impl Drop for Fixture {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.0);
    }
}
#[derive(Default)]
struct Mock {
    launches: usize,
    owner: bool,
    alive: bool,
    unknown: bool,
    other_login: bool,
    birth: Option<u64>,
    fail: u8,
    drift: Cell<bool>,
}
impl Observation for Mock {
    fn current_login(&self) -> Result<LoginIdentity> {
        let mut login = process().login;
        if self.other_login {
            login.session_id += 1;
        }
        Ok(login)
    }
    fn state(&self, _: u32) -> ProcessState {
        ProcessState::Unknown
    }
    fn observe(&self, _: u32) -> Result<Option<ProcessSnapshot>> {
        if self.unknown {
            return Err("OWNER_UNPROVEN");
        }
        if !self.alive {
            return Ok(None);
        }
        let mut p = process();
        if let Some(birth) = self.birth {
            p.created_filetime = birth;
        }
        Ok(Some(p))
    }
    fn legacy_candidates(&self) -> Result<Vec<ProcessSnapshot>> {
        Ok(vec![])
    }
}
impl Platform for Mock {
    fn verify(&self) -> Result<()> {
        if self.drift.get() {
            Err("INSTALLATION_CHANGED")
        } else {
            Ok(())
        }
    }
    fn owner(&self) -> Result<Option<MonitorIdentity>> {
        Ok(self.owner.then(|| MonitorIdentity {
            process: process(),
            backend: Backend::Rust,
            instance: Some("a".repeat(32)),
            ownership: Ownership::CurrentLogin,
            directories: vec![],
            legacy: false,
            record: None,
        }))
    }
    fn spawn(&mut self) -> std::result::Result<ProcessSnapshot, SpawnFailure> {
        self.launches += 1;
        match self.fail {
            1 => Err(SpawnFailure::Unconfirmed),
            2 => Err(SpawnFailure::NotStarted),
            3 => {
                self.drift.set(true);
                self.alive = true;
                Ok(process())
            }
            4 => {
                let mut p = process();
                p.arguments.push("unexpected".into());
                Ok(p)
            }
            _ => {
                self.alive = true;
                Ok(process())
            }
        }
    }
}
fn start(f: &Fixture, m: &mut Mock) -> Result<Outcome> {
    ensure(&f.path(), &native(), &"b".repeat(64), m)
}

#[test]
fn lost_reply_and_alive_child_without_monitor_record_never_spawn_twice() {
    let f = Fixture::new();
    let mut m = Mock::default();
    assert!(matches!(start(&f, &mut m), Ok(Outcome::Started(_))));
    assert!(matches!(start(&f, &mut m), Err("MONITOR_STARTING")));
    m.owner = true;
    assert!(matches!(start(&f, &mut m), Ok(Outcome::Running(_))));
    assert_eq!(m.launches, 1);
}

#[test]
fn exact_born_child_survives_valid_inventory_reload_without_rewriting_launch_receipt() {
    let f = Fixture::new();
    let mut m = Mock::default();
    start(&f, &mut m).unwrap();
    let original = std::fs::read(f.path()).unwrap();
    m.owner = true;
    assert!(matches!(
        ensure(&f.path(), &native(), &"c".repeat(64), &mut m),
        Ok(Outcome::Running(_))
    ));
    assert_eq!(std::fs::read(f.path()).unwrap(), original);
    assert_eq!(m.launches, 1);
}
#[test]
fn uncertain_spawn_retains_pre_effect_intent_until_positive_owner_readback() {
    let f = Fixture::new();
    let mut m = Mock {
        fail: 1,
        ..Mock::default()
    };
    assert!(matches!(
        start(&f, &mut m),
        Err("MONITOR_LAUNCH_UNCONFIRMED")
    ));
    let original = std::fs::read(f.path()).unwrap();
    m.fail = 0;
    assert!(matches!(
        start(&f, &mut m),
        Err("MONITOR_LAUNCH_UNCONFIRMED")
    ));
    assert_eq!(std::fs::read(f.path()).unwrap(), original);
    m.owner = true;
    assert!(matches!(start(&f, &mut m), Ok(Outcome::Running(_))));
    let value: serde_json::Value =
        serde_json::from_slice(&std::fs::read(f.path()).unwrap()).unwrap();
    assert_eq!(value["child"]["pid"], 41);
    assert_eq!(m.launches, 1);
}
#[test]
fn known_unsent_failure_can_retry_but_mismatched_child_cannot() {
    let f = Fixture::new();
    let mut m = Mock {
        fail: 2,
        ..Mock::default()
    };
    assert!(matches!(start(&f, &mut m), Err("MONITOR_START_FAILED")));
    assert!(!f.path().exists());
    m.fail = 4;
    assert!(matches!(
        start(&f, &mut m),
        Err("MONITOR_LAUNCH_UNCONFIRMED")
    ));
    assert!(matches!(
        start(&f, &mut m),
        Err("MONITOR_LAUNCH_UNCONFIRMED")
    ));
    assert_eq!(m.launches, 2);
}
#[test]
fn unknown_exit_keeps_birth_and_positive_ended_incarnation_allows_new_launch() {
    let f = Fixture::new();
    let mut m = Mock::default();
    start(&f, &mut m).unwrap();
    let original = std::fs::read(f.path()).unwrap();
    m.unknown = true;
    assert!(matches!(start(&f, &mut m), Err("OWNER_UNPROVEN")));
    assert_eq!(std::fs::read(f.path()).unwrap(), original);
    assert_eq!(m.launches, 1);
    m.unknown = false;
    m.birth = Some(process().created_filetime + 1);
    assert!(matches!(start(&f, &mut m), Ok(Outcome::Started(_))));
    assert_eq!(m.launches, 2);
}
#[test]
fn backend_drift_after_spawn_still_records_child_and_refuses_further_effect() {
    let f = Fixture::new();
    let mut m = Mock {
        fail: 3,
        ..Mock::default()
    };
    assert!(matches!(start(&f, &mut m), Err("INSTALLATION_CHANGED")));
    let value: serde_json::Value =
        serde_json::from_slice(&std::fs::read(f.path()).unwrap()).unwrap();
    assert_eq!(value["child"]["pid"], 41);
    assert!(matches!(start(&f, &mut m), Err("INSTALLATION_CHANGED")));
    assert_eq!(m.launches, 1);
}
#[test]
fn other_login_and_corrupt_intent_refuse_without_changes() {
    let f = Fixture::new();
    let mut m = Mock::default();
    start(&f, &mut m).unwrap();
    let original = std::fs::read(f.path()).unwrap();
    m.other_login = true;
    assert!(matches!(start(&f, &mut m), Err("OTHER_LOGIN_OWNER")));
    assert_eq!(std::fs::read(f.path()).unwrap(), original);
    m.other_login = false;
    std::fs::write(f.path(), b"{\"schema_version\":1,\"schema_version\":1}").unwrap();
    assert!(start(&f, &mut m).is_err());
    assert_eq!(m.launches, 1);
}
