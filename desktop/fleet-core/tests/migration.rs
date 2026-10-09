use bat_fleet_core::{
    discovery::{Backend, MonitorIdentity, Ownership},
    migration::{Owner, Phase, Platform, Progress, Store},
    process_adapter::{LoginIdentity, ProcessSnapshot},
    Result,
};
use serde_json::{json, Value};
use std::{
    cell::{Cell, RefCell},
    path::PathBuf,
    rc::Rc,
};
const ID: &str = "11111111111111111111111111111111";
const REVERSE: &str = "22222222222222222222222222222222";
fn config(b: Backend) -> Vec<u8> {
    serde_json::to_vec(&json!({"kit_root":"synthetic-kit","backend":b})).unwrap()
}
fn login() -> LoginIdentity {
    LoginIdentity {
        owner_sid: "S-1-5-21-123-456-789-1001".into(),
        session_id: 7,
    }
}
fn owner(b: Backend, n: u32) -> MonitorIdentity {
    MonitorIdentity {
        backend: b,
        ownership: Ownership::CurrentLogin,
        legacy: false,
        instance: Some(format!("{n:032x}")),
        directories: vec![],
        record: None,
        process: ProcessSnapshot {
            pid: n,
            created_filetime: 123456000 + n as u64,
            executable: "C:\\Synthetic\\monitor.exe".into(),
            arguments: vec!["--fixed".into()],
            login: login(),
        },
    }
}
struct Temp(PathBuf);
impl Temp {
    fn new() -> Self {
        let p = std::env::temp_dir().join(format!(
            "bac-migration-{}-{:032x}",
            std::process::id(),
            rand::random::<u128>()
        ));
        std::fs::create_dir_all(p.join("Startup")).unwrap();
        std::fs::write(p.join("fleet.json"), config(Backend::Powershell)).unwrap();
        std::fs::write(p.join("Startup/Open BAT.lnk"), b"powershell").unwrap();
        std::fs::write(p.join("Startup/Unrelated.lnk"), b"untouched").unwrap();
        Self(p)
    }
    fn store(&self) -> Store {
        Store::new(&self.0.join("fleet.json"), &self.0.join("Startup")).unwrap()
    }
    fn journal(&self) -> PathBuf {
        self.0.join(format!("fleet-migrations/{ID}.json"))
    }
}
impl Drop for Temp {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.0);
    }
}
struct Guard(Rc<Cell<bool>>);
impl Guard {
    fn acquire(v: &Rc<Cell<bool>>) -> Result<Self> {
        if v.replace(true) {
            return Err("BUSY");
        }
        Ok(Self(v.clone()))
    }
}
impl Drop for Guard {
    fn drop(&mut self) {
        self.0.set(false)
    }
}
struct Fake {
    owner: Option<MonitorIdentity>,
    unknown: bool,
    quit: usize,
    launched: usize,
    uncertain: bool,
    launcher: Rc<Cell<bool>>,
    monitor: Rc<Cell<bool>>,
    events: RefCell<Vec<&'static str>>,
    new_owner_on_guard: bool,
}
impl Fake {
    fn new() -> Self {
        Self {
            owner: Some(owner(Backend::Powershell, 10)),
            unknown: false,
            quit: 0,
            launched: 0,
            uncertain: false,
            launcher: Rc::new(Cell::new(false)),
            monitor: Rc::new(Cell::new(false)),
            events: RefCell::new(vec![]),
            new_owner_on_guard: false,
        }
    }
}
impl Platform for Fake {
    type LauncherGuard = Guard;
    type MonitorGuard = Guard;
    fn launcher_guard(&mut self) -> Result<Guard> {
        Guard::acquire(&self.launcher)
    }
    fn monitor_guard(&mut self) -> Result<Guard> {
        assert!(self.launcher.get());
        if self.new_owner_on_guard {
            self.owner = Some(owner(Backend::Rust, 99));
        }
        Guard::acquire(&self.monitor)
    }
    fn login(&self) -> Result<LoginIdentity> {
        Ok(login())
    }
    fn discover(&mut self) -> Result<Option<MonitorIdentity>> {
        assert!(self.launcher.get());
        if self.unknown {
            Err("OWNER_UNPROVEN")
        } else {
            Ok(self.owner.clone())
        }
    }
    fn request_quit(&mut self, expected: &Owner) -> Result<()> {
        assert!(self.launcher.get());
        assert!(expected.matches(self.owner.as_ref().unwrap(), &login()));
        self.quit += 1;
        self.events.borrow_mut().push("quit");
        Ok(())
    }
    fn launch(&mut self, backend: Backend) -> Result<()> {
        assert!(self.launcher.get());
        assert!(!self.monitor.get());
        self.launched += 1;
        self.events.borrow_mut().push("launch");
        if self.uncertain {
            return Err("LOST_REPLY");
        }
        self.owner = Some(owner(backend, 20 + self.launched as u32));
        Ok(())
    }
    fn validate_config(&self, bytes: &[u8], b: Backend) -> Result<()> {
        let v: Value = serde_json::from_slice(bytes).map_err(|_| "INSTALLATION_INVALID")?;
        if v != json!({"kit_root":"synthetic-kit","backend":b}) {
            return Err("INSTALLATION_INVALID");
        }
        Ok(())
    }
    fn classify_shortcut(&self, bytes: &[u8]) -> Result<Backend> {
        match bytes {
            b"powershell" => Ok(Backend::Powershell),
            b"rust" => Ok(Backend::Rust),
            _ => Err("STARTUP_UNOWNED"),
        }
    }
    fn shortcut(&self, b: Backend) -> Result<Vec<u8>> {
        Ok(match b {
            Backend::Powershell => b"powershell".to_vec(),
            Backend::Rust => b"rust".to_vec(),
        })
    }
}
fn begin(t: &Temp, p: &mut Fake) {
    let preview = t.store().preview(p, Backend::Powershell).unwrap();
    assert_eq!(
        t.store()
            .begin(p, ID, &preview, Backend::Rust, &config(Backend::Rust), true),
        Ok(Phase::Prepared)
    );
}
#[test]
fn normal_switch_and_explicit_reverse_preserve_exact_original_bytes_and_unrelated_entry() {
    let t = Temp::new();
    let original = std::fs::read(t.0.join("fleet.json")).unwrap();
    let mut p = Fake::new();
    begin(&t, &mut p);
    assert_eq!(t.store().advance(&mut p, ID), Ok(Progress::WaitingExit));
    assert_eq!(p.quit, 1);
    assert_eq!(p.launched, 0);
    assert_eq!(std::fs::read(t.0.join("fleet.json")).unwrap(), original);
    p.owner = None;
    assert_eq!(t.store().advance(&mut p, ID), Ok(Progress::WaitingLaunch));
    assert_eq!(p.launched, 1);
    assert_eq!(t.store().advance(&mut p, ID), Ok(Progress::Complete));
    assert!(t.store().pending().unwrap().is_none());
    assert_eq!(t.store().restore(&mut p, ID, REVERSE), Ok(Phase::Prepared));
    assert_eq!(t.store().restore(&mut p, ID, REVERSE), Ok(Phase::Prepared));
    assert_eq!(
        t.store().advance(&mut p, REVERSE),
        Ok(Progress::WaitingExit)
    );
    p.owner = None;
    assert_eq!(
        t.store().advance(&mut p, REVERSE),
        Ok(Progress::WaitingLaunch)
    );
    assert_eq!(t.store().advance(&mut p, REVERSE), Ok(Progress::Complete));
    assert_eq!(std::fs::read(t.0.join("fleet.json")).unwrap(), original);
    assert_eq!(
        std::fs::read(t.0.join("Startup/Open BAT.lnk")).unwrap(),
        b"powershell"
    );
    assert_eq!(
        std::fs::read(t.0.join("Startup/Unrelated.lnk")).unwrap(),
        b"untouched"
    );
    assert!(t.journal().is_file());
    assert_eq!(p.launched, 2);
}
#[test]
fn unknown_quit_owner_drift_other_login_and_legacy_never_change_slots() {
    for kind in 0..4 {
        let t = Temp::new();
        let mut p = Fake::new();
        begin(&t, &mut p);
        assert_eq!(t.store().advance(&mut p, ID), Ok(Progress::WaitingExit));
        match kind {
            0 => p.unknown = true,
            1 => p.owner.as_mut().unwrap().instance = Some("f".repeat(32)),
            2 => p.owner.as_mut().unwrap().process.login.session_id += 1,
            _ => p.owner.as_mut().unwrap().legacy = true,
        };
        assert!(t.store().advance(&mut p, ID).is_err());
        assert_eq!(p.launched, 0);
        assert_eq!(
            std::fs::read(t.0.join("fleet.json")).unwrap(),
            config(Backend::Powershell)
        );
        assert_eq!(
            std::fs::read(t.0.join("Startup/Open BAT.lnk")).unwrap(),
            b"powershell"
        );
    }
}
#[test]
fn no_owner_is_not_sufficient_without_common_monitor_exclusion_and_recheck() {
    for replacement in [false, true] {
        let t = Temp::new();
        let mut p = Fake::new();
        p.owner = None;
        begin(&t, &mut p);
        if replacement {
            p.new_owner_on_guard = true
        } else {
            p.monitor.set(true)
        };
        assert!(t.store().advance(&mut p, ID).is_err());
        assert_eq!(p.launched, 0);
        assert_eq!(
            std::fs::read(t.0.join("Startup/Open BAT.lnk")).unwrap(),
            b"powershell"
        );
    }
}
#[test]
fn launch_intent_restart_never_resends_and_requires_matching_positive_owner() {
    let t = Temp::new();
    let mut p = Fake::new();
    p.owner = None;
    p.uncertain = true;
    begin(&t, &mut p);
    assert_eq!(t.store().advance(&mut p, ID), Err("LOST_REPLY"));
    assert_eq!(
        t.store().pending().unwrap(),
        Some((ID.into(), Phase::LaunchRequested))
    );
    for _ in 0..3 {
        assert_eq!(
            t.store().advance(&mut p, ID),
            Err("MIGRATION_LAUNCH_UNKNOWN")
        );
    }
    assert_eq!(p.launched, 1);
    p.owner = Some(owner(Backend::Powershell, 44));
    assert_eq!(
        t.store().advance(&mut p, ID),
        Err("MIGRATION_OWNER_CHANGED")
    );
    p.owner = Some(owner(Backend::Rust, 45));
    assert_eq!(t.store().advance(&mut p, ID), Ok(Progress::Complete));
    assert_eq!(p.launched, 1);
}
#[test]
fn lost_quit_receipt_replays_exact_idempotent_request_without_inventing_death() {
    let t = Temp::new();
    let mut p = Fake::new();
    begin(&t, &mut p);
    let mut doc: Value = serde_json::from_slice(&std::fs::read(t.journal()).unwrap()).unwrap();
    doc["phase"] = json!("quit_requested");
    std::fs::write(t.journal(), serde_json::to_vec(&doc).unwrap()).unwrap();
    assert_eq!(t.store().advance(&mut p, ID), Ok(Progress::WaitingExit));
    assert_eq!(p.quit, 1);
    assert_eq!(p.launched, 0);
}
#[test]
fn lost_slot_receipt_settles_exact_bytes_but_third_value_never_gets_overwritten() {
    for changed in [false, true] {
        let t = Temp::new();
        let mut p = Fake::new();
        p.owner = None;
        begin(&t, &mut p);
        std::fs::write(
            t.0.join("Startup/Open BAT.lnk"),
            if changed {
                b"foreign".as_slice()
            } else {
                b"rust".as_slice()
            },
        )
        .unwrap();
        let result = t.store().advance(&mut p, ID);
        if changed {
            assert_eq!(result, Err("MIGRATION_CHANGED"));
            assert_eq!(p.launched, 0);
            assert_eq!(
                std::fs::read(t.0.join("Startup/Open BAT.lnk")).unwrap(),
                b"foreign"
            );
        } else {
            assert_eq!(result, Ok(Progress::WaitingLaunch));
            assert_eq!(p.launched, 1);
        }
    }
}
#[test]
fn fixed_id_conflict_pending_intent_and_foreign_shortcut_refuse_before_effects() {
    let t = Temp::new();
    let mut p = Fake::new();
    let preview = t.store().preview(&mut p, Backend::Powershell).unwrap();
    begin(&t, &mut p);
    assert_eq!(
        t.store().begin(
            &mut p,
            ID,
            &preview,
            Backend::Rust,
            &config(Backend::Rust),
            true
        ),
        Ok(Phase::Prepared)
    );
    assert_eq!(
        t.store().begin(
            &mut p,
            ID,
            &preview,
            Backend::Rust,
            &config(Backend::Rust),
            false
        ),
        Err("MIGRATION_ID_CONFLICT")
    );
    assert_eq!(
        t.store().begin(
            &mut p,
            REVERSE,
            &preview,
            Backend::Rust,
            &config(Backend::Rust),
            true
        ),
        Err("MIGRATION_PENDING")
    );
    let other = Temp::new();
    let preview = other.store().preview(&mut p, Backend::Powershell).unwrap();
    std::fs::write(other.0.join("Startup/Open BAT.lnk"), b"foreign").unwrap();
    assert_eq!(
        other.store().begin(
            &mut p,
            ID,
            &preview,
            Backend::Rust,
            &config(Backend::Rust),
            true
        ),
        Err("STARTUP_UNOWNED")
    );
    assert!(!other.journal().exists());
    assert_eq!(p.quit + p.launched, 0);
}
#[test]
fn disabled_autostart_removes_only_owned_slot_and_reverse_restores_it() {
    let t = Temp::new();
    let mut p = Fake::new();
    p.owner = None;
    let preview = t.store().preview(&mut p, Backend::Powershell).unwrap();
    t.store()
        .begin(
            &mut p,
            ID,
            &preview,
            Backend::Rust,
            &config(Backend::Rust),
            false,
        )
        .unwrap();
    t.store().advance(&mut p, ID).unwrap();
    t.store().advance(&mut p, ID).unwrap();
    assert!(!t.0.join("Startup/Open BAT.lnk").exists());
    assert!(t.0.join("Startup/Unrelated.lnk").exists());
    t.store().restore(&mut p, ID, REVERSE).unwrap();
    t.store().advance(&mut p, REVERSE).unwrap();
    p.owner = None;
    t.store().advance(&mut p, REVERSE).unwrap();
    assert_eq!(
        std::fs::read(t.0.join("Startup/Open BAT.lnk")).unwrap(),
        b"powershell"
    );
}
#[cfg(unix)]
#[test]
fn linked_slots_or_journal_directory_refuse_and_preserve_target() {
    use std::os::unix::fs::symlink;
    for slot in ["fleet.json", "Startup/Open BAT.lnk", "fleet-migrations"] {
        let t = Temp::new();
        let mut p = Fake::new();
        let preview = t.store().preview(&mut p, Backend::Powershell).unwrap();
        let path = t.0.join(slot);
        if path.exists() {
            std::fs::rename(&path, t.0.join("original")).unwrap();
        } else {
            std::fs::create_dir(t.0.join("original")).unwrap();
        }
        symlink(t.0.join("original"), &path).unwrap();
        assert!(t
            .store()
            .begin(
                &mut p,
                ID,
                &preview,
                Backend::Rust,
                &config(Backend::Rust),
                true
            )
            .is_err());
        assert_eq!(p.quit + p.launched, 0);
        assert!(t.0.join("original").exists());
    }
}

#[test]
fn review_snapshot_cannot_relabel_changed_owned_startup_or_new_owner() {
    for change_owner in [false, true] {
        let t = Temp::new();
        let mut p = Fake::new();
        let preview = t.store().preview(&mut p, Backend::Powershell).unwrap();
        if change_owner {
            p.owner = Some(owner(Backend::Powershell, 77));
        } else {
            std::fs::write(t.0.join("Startup/Open BAT.lnk"), b"rust").unwrap();
        }
        assert_eq!(
            t.store().begin(
                &mut p,
                ID,
                &preview,
                Backend::Rust,
                &config(Backend::Rust),
                true
            ),
            Err("MIGRATION_PREVIEW_CHANGED")
        );
        assert!(!t.journal().exists());
        assert_eq!(p.quit + p.launched, 0);
    }
}

#[test]
fn interrupted_initial_and_reverse_pointer_publication_recover_same_intent() {
    let t = Temp::new();
    let mut p = Fake::new();
    let preview = t.store().preview(&mut p, Backend::Powershell).unwrap();
    begin(&t, &mut p);
    std::fs::remove_file(t.0.join("fleet-migrations/active.json")).unwrap();
    t.store()
        .begin(
            &mut p,
            ID,
            &preview,
            Backend::Rust,
            &config(Backend::Rust),
            true,
        )
        .unwrap();
    assert_eq!(
        t.store().pending().unwrap(),
        Some((ID.into(), Phase::Prepared))
    );
    t.store().advance(&mut p, ID).unwrap();
    p.owner = None;
    t.store().advance(&mut p, ID).unwrap();
    t.store().advance(&mut p, ID).unwrap();
    t.store().restore(&mut p, ID, REVERSE).unwrap();
    std::fs::write(
        t.0.join("fleet-migrations/active.json"),
        serde_json::to_vec(ID).unwrap(),
    )
    .unwrap();
    assert_eq!(t.store().restore(&mut p, ID, REVERSE), Ok(Phase::Prepared));
    assert_eq!(
        t.store().pending().unwrap(),
        Some((REVERSE.into(), Phase::Prepared))
    );
}
#[test]
fn malformed_complete_receipt_and_changed_configuration_refuse_without_effects() {
    for malformed in [false, true] {
        let t = Temp::new();
        let mut p = Fake::new();
        begin(&t, &mut p);
        if malformed {
            let mut doc: Value =
                serde_json::from_slice(&std::fs::read(t.journal()).unwrap()).unwrap();
            doc["phase"] = json!("complete");
            std::fs::write(t.journal(), serde_json::to_vec(&doc).unwrap()).unwrap();
        } else {
            std::fs::write(t.0.join("fleet.json"), b"third-party config").unwrap();
        }
        assert!(t.store().advance(&mut p, ID).is_err());
        assert_eq!(p.quit + p.launched, 0);
    }
}
