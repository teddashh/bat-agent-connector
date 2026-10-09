use bat_fleet_core::{
    discovery::Observation,
    ownership::ProcessState,
    process_adapter::{LoginIdentity, ProcessSnapshot},
    unconfigured::verify_absence,
    Result,
};
use std::path::PathBuf;

struct Fixture(PathBuf);
impl Fixture {
    fn new() -> Self {
        let root = std::env::temp_dir().join(format!("bac-absent-{:032x}", rand::random::<u128>()));
        std::fs::create_dir(&root).unwrap();
        Self(root)
    }
    fn installation(&self) -> PathBuf {
        self.0.join("config/fleet.json")
    }
    fn verify(&self, mock: &Mock) -> Result<()> {
        verify_absence(&self.installation(), &self.0, mock)
    }
    fn marker(&self) -> PathBuf {
        self.0.join("bat-fleet-monitor-launch.json")
    }
}
impl Drop for Fixture {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.0);
    }
}
fn process() -> ProcessSnapshot {
    ProcessSnapshot {
        pid: 41,
        created_filetime: 134000000000000000,
        executable: "C:\\Apps\\Dashboard.exe".into(),
        arguments: vec![
            "--fleet-supervisor".into(),
            "--fleet-config".into(),
            "C:\\Config\\fleet.json".into(),
        ],
        login: LoginIdentity {
            owner_sid: "S-1-5-21-111-222-333-1001".into(),
            session_id: 2,
        },
    }
}
#[derive(Default)]
struct Mock {
    live: bool,
    unknown: bool,
    legacy: bool,
    reappear: Option<PathBuf>,
}
impl Observation for Mock {
    fn current_login(&self) -> Result<LoginIdentity> {
        Ok(process().login)
    }
    fn state(&self, _: u32) -> ProcessState {
        panic!("no loose PID-only absence")
    }
    fn observe(&self, _: u32) -> Result<Option<ProcessSnapshot>> {
        if self.unknown {
            Err("OWNER_UNPROVEN")
        } else {
            Ok(self.live.then(process))
        }
    }
    fn legacy_candidates(&self) -> Result<Vec<ProcessSnapshot>> {
        if self.unknown {
            return Err("OWNER_UNPROVEN");
        }
        if let Some(path) = &self.reappear {
            std::fs::create_dir_all(path.parent().unwrap()).unwrap();
            std::fs::write(path, "restored").unwrap();
        }
        if self.legacy {
            let mut candidate = process();
            candidate.executable =
                "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe".into();
            candidate.arguments = vec![
                "-NoProfile".into(),
                "-ExecutionPolicy".into(),
                "Bypass".into(),
                "-File".into(),
                "C:\\OtherKit\\bat-connect.ps1".into(),
                "-InventoryPath".into(),
                "C:\\OtherKit\\fleet-inventory.json".into(),
                "-ProfileIndexPath".into(),
                "C:\\OtherKit\\bat-profiles\\index.json".into(),
            ];
            candidate.login.session_id += 1;
            Ok(vec![candidate])
        } else {
            Ok(vec![])
        }
    }
}
fn intent() -> serde_json::Value {
    serde_json::json!({"schema_version":1,"configuration_binding":"a".repeat(64),
        "executable":process().executable,"arguments":process().arguments,
        "owner_sid":process().login.owner_sid,"session_id":2,
        "child":{"pid":41,"created_filetime":process().created_filetime.to_string()}})
}

#[test]
fn empty_fixed_directories_allow_a_fresh_dashboard_without_creating_files() {
    let f = Fixture::new();
    f.verify(&Mock::default()).unwrap();
    assert_eq!(std::fs::read_dir(&f.0).unwrap().count(), 0);
    for dir in ["BetterAgentTerminal", "org.tonyq.better-agent-terminal"] {
        for name in [
            "fleet-tunnel-owners",
            "fleet-tunnel-intents",
            "fleet-tunnel-stop-intents",
        ] {
            std::fs::create_dir_all(f.0.join(dir).join(name)).unwrap();
        }
    }
    f.verify(&Mock::default()).unwrap();
}
#[test]
fn both_directory_owner_and_intent_residue_refuse_without_touching_bytes() {
    for dir in ["BetterAgentTerminal", "org.tonyq.better-agent-terminal"] {
        for name in [
            "fleet-monitor.json",
            "fleet-tunnel-owners/old.json",
            "fleet-tunnel-intents/unknown.tmp",
            "fleet-tunnel-stop-intents/old.json",
        ] {
            let f = Fixture::new();
            let path = f.0.join(dir).join(name);
            std::fs::create_dir_all(path.parent().unwrap()).unwrap();
            std::fs::write(&path, b"unknown original evidence").unwrap();
            assert_eq!(
                f.verify(&Mock::default()),
                Err("FLEET_OWNERSHIP_REQUIRES_CONFIGURATION")
            );
            assert_eq!(std::fs::read(path).unwrap(), b"unknown original evidence");
        }
    }
}
#[test]
fn durable_launch_intent_requires_positive_original_child_absence() {
    let f = Fixture::new();
    let bytes = serde_json::to_vec(&intent()).unwrap();
    std::fs::write(f.marker(), &bytes).unwrap();
    assert_eq!(
        f.verify(&Mock {
            live: true,
            ..Default::default()
        }),
        Err("MONITOR_STARTING")
    );
    assert_eq!(
        f.verify(&Mock {
            unknown: true,
            ..Default::default()
        }),
        Err("OWNER_UNPROVEN")
    );
    f.verify(&Mock::default()).unwrap();
    assert_eq!(std::fs::read(f.marker()).unwrap(), bytes);
    let mut unknown = intent();
    unknown["child"] = serde_json::Value::Null;
    std::fs::write(f.marker(), serde_json::to_vec(&unknown).unwrap()).unwrap();
    assert_eq!(
        f.verify(&Mock::default()),
        Err("MONITOR_LAUNCH_UNCONFIRMED")
    );
    std::fs::write(f.marker(), b"partial").unwrap();
    assert!(f.verify(&Mock::default()).is_err());
}
#[test]
fn unrecorded_other_login_legacy_candidate_and_unknown_enumeration_refuse() {
    let f = Fixture::new();
    assert_eq!(
        f.verify(&Mock {
            legacy: true,
            ..Default::default()
        }),
        Err("FLEET_OWNERSHIP_REQUIRES_CONFIGURATION")
    );
    assert_eq!(
        f.verify(&Mock {
            unknown: true,
            ..Default::default()
        }),
        Err("OWNER_UNPROVEN")
    );
}
#[test]
fn reappearing_installation_is_checked_at_the_last_boundary() {
    let f = Fixture::new();
    assert_eq!(
        f.verify(&Mock {
            reappear: Some(f.installation()),
            ..Default::default()
        }),
        Err("FLEET_CONFIGURATION_UNPROVEN")
    );
    assert_eq!(std::fs::read(f.installation()).unwrap(), b"restored");
}
#[test]
fn ownership_or_unknown_launch_appearing_during_enumeration_refuses() {
    for path in [
        "BetterAgentTerminal/fleet-monitor.json",
        "org.tonyq.better-agent-terminal/fleet-tunnel-owners/new.json",
        "bat-fleet-monitor-launch.json",
        "config/fleet-migrations/active.json",
    ] {
        let f = Fixture::new();
        let path = f.0.join(path);
        assert!(f
            .verify(&Mock {
                reappear: Some(path.clone()),
                ..Default::default()
            })
            .is_err());
        assert_eq!(std::fs::read(path).unwrap(), b"restored");
    }
}
#[test]
fn missing_configuration_does_not_erase_an_unsettled_migration() {
    let f = Fixture::new();
    let pointer = f.0.join("config/fleet-migrations/active.json");
    std::fs::create_dir_all(pointer.parent().unwrap()).unwrap();
    for bytes in [b"\"original-migration\"".as_slice(), b"partial"] {
        std::fs::write(&pointer, bytes).unwrap();
        assert_eq!(f.verify(&Mock::default()), Err("MIGRATION_PENDING"));
        assert_eq!(std::fs::read(&pointer).unwrap(), bytes);
        assert!(!f.installation().exists());
    }
}
#[test]
fn non_directory_evidence_and_relative_inputs_never_mean_absence() {
    let f = Fixture::new();
    std::fs::write(f.0.join("BetterAgentTerminal"), b"not a directory").unwrap();
    assert!(f.verify(&Mock::default()).is_err());
    assert!(verify_absence(std::path::Path::new("fleet.json"), &f.0, &Mock::default()).is_err());
}
#[cfg(unix)]
#[test]
fn linked_directory_is_refused_without_following_ownership_files() {
    let f = Fixture::new();
    let target = Fixture::new();
    std::os::unix::fs::symlink(&target.0, f.0.join("BetterAgentTerminal")).unwrap();
    assert_eq!(f.verify(&Mock::default()), Err("FLEET_ABSENCE_UNPROVEN"));
}
