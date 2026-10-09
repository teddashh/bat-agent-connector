use bat_fleet_core::{ownership::ProcessState, process_adapter::*, Result};
use std::{
    cell::{Cell, RefCell},
    rc::Rc,
};
fn snapshot() -> ProcessSnapshot {
    ProcessSnapshot {
        pid: 42,
        created_filetime: 133_456_789_012_345_678,
        executable: r"C:\Windows\System32\OpenSSH\ssh.exe".into(),
        arguments: vec![
            "-N".into(),
            "-o".into(),
            "SetEnv=BAT_FLEET_MONITOR=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa".into(),
            "synthetic".into(),
        ],
        login: LoginIdentity {
            owner_sid: "S-1-5-21-1-2-3-1001".into(),
            session_id: 7,
        },
    }
}
fn record() -> TunnelRecord {
    let child = snapshot();
    let mut parent = child.clone();
    parent.pid = 41;
    parent.arguments.clear();
    TunnelRecord::from_snapshot(&child, &parent).unwrap()
}
struct Fake {
    snapshot: RefCell<ProcessSnapshot>,
    login: LoginIdentity,
    parent: ProcessState,
    absent: bool,
    denied: bool,
    stops: Rc<Cell<usize>>,
    snapshots: Rc<Cell<usize>>,
    mutate_final: bool,
    unknown_exit: bool,
}
impl Default for Fake {
    fn default() -> Self {
        Self {
            snapshot: RefCell::new(snapshot()),
            login: snapshot().login,
            parent: ProcessState::Dead,
            absent: false,
            denied: false,
            stops: Rc::new(Cell::new(0)),
            snapshots: Rc::new(Cell::new(0)),
            mutate_final: false,
            unknown_exit: false,
        }
    }
}
struct Held {
    data: ProcessSnapshot,
    stops: Rc<Cell<usize>>,
    snapshots: Rc<Cell<usize>>,
    mutate_final: bool,
    unknown_exit: bool,
}
impl HeldProcess for Held {
    fn snapshot(&self) -> Result<ProcessSnapshot> {
        let n = self.snapshots.get();
        self.snapshots.set(n + 1);
        let mut s = self.data.clone();
        if self.mutate_final && n > 0 {
            s.created_filetime += 1;
        }
        Ok(s)
    }
    fn terminate_and_wait(&mut self) -> Result<()> {
        self.stops.set(self.stops.get() + 1);
        if self.unknown_exit {
            Err("STOP_UNCONFIRMED")
        } else {
            Ok(())
        }
    }
}
impl ProcessAccess for Fake {
    type Held = Held;
    fn current_login(&self) -> Result<LoginIdentity> {
        Ok(self.login.clone())
    }
    fn open_for_stop(&self, _: u32) -> Result<Option<Held>> {
        if self.denied {
            return Err("OWNER_UNPROVEN");
        }
        if self.absent {
            return Ok(None);
        }
        Ok(Some(Held {
            data: self.snapshot.borrow().clone(),
            stops: self.stops.clone(),
            snapshots: self.snapshots.clone(),
            mutate_final: self.mutate_final,
            unknown_exit: self.unknown_exit,
        }))
    }
    fn state(&self, _: u32) -> ProcessState {
        // Simulate a PID being reused while the origin query runs. The held child remains fixed.
        self.snapshot.borrow_mut().pid = 999;
        self.parent.clone()
    }
}
fn stop(fake: &Fake, rec: &TunnelRecord) -> Result<StopOutcome> {
    stop_tunnel(
        fake,
        rec,
        StopMode::Owned {
            current_epoch: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        },
    )
}
#[test]
fn exact_filetime_conversion_and_cim_precision() {
    assert_eq!(datetime_ticks(1).unwrap(), 504_911_232_000_000_001);
    assert_eq!(
        legacy_created(133_456_789_012_345_678).unwrap(),
        "638368021012345670"
    );
    assert!(datetime_ticks(0).is_err());
    assert!(datetime_ticks(u64::MAX).is_err());
    assert!(datetime_ticks(MAX_DATETIME_TICKS - FILETIME_EPOCH_TICKS + 1).is_err());
}
#[test]
fn record_roundtrip_preserves_native_birth_and_parent() {
    let original = record();
    let parsed = TunnelRecord::parse(
        &serde_json::to_vec(&original.document().unwrap()).unwrap(),
        None,
    )
    .unwrap();
    assert_eq!(parsed.created_filetime, original.created_filetime);
    assert_eq!(parsed.origin.unwrap().pid, 41);
    assert!(parsed.process.matches(&original.process));
}
#[test]
fn legacy_record_uses_exact_epoch_parent_fallback() {
    let mut doc = record().document().unwrap();
    for key in ["created_filetime", "monitor_pid", "monitor_created"] {
        doc.as_object_mut().unwrap().remove(key);
    }
    let bytes = serde_json::to_vec(&doc).unwrap();
    let pointer = MonitorPointer {
        pid: 41,
        created: doc["created"].as_str().unwrap().into(),
        instance: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa".into(),
    };
    assert_eq!(
        TunnelRecord::parse(&bytes, Some(&pointer))
            .unwrap()
            .origin
            .unwrap()
            .pid,
        41
    );
    let mut bad = pointer;
    bad.instance = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb".into();
    assert!(TunnelRecord::parse(&bytes, Some(&bad))
        .unwrap()
        .origin
        .is_none());
}
#[test]
fn damaged_partial_parent_never_falls_back() {
    let mut doc = record().document().unwrap();
    doc.as_object_mut().unwrap().remove("monitor_created");
    assert!(TunnelRecord::parse(&serde_json::to_vec(&doc).unwrap(), None).is_err());
}
#[test]
fn duplicate_and_unknown_record_fields_refused() {
    let doc = serde_json::to_string(&record().document().unwrap()).unwrap();
    assert!(TunnelRecord::parse(doc.replacen('{', "{\"PID\":42,", 1).as_bytes(), None).is_err());
    assert!(
        TunnelRecord::parse(doc.replacen('{', "{\"unknown\":42,", 1).as_bytes(), None).is_err()
    );
}
#[test]
fn inconsistent_native_legacy_birth_refused() {
    let mut doc = record().document().unwrap();
    doc["created_filetime"] = "133456789012345688".into();
    assert!(TunnelRecord::parse(&serde_json::to_vec(&doc).unwrap(), None).is_err());
}
#[test]
fn owned_exact_record_stops_after_two_held_reads() {
    let fake = Fake::default();
    assert_eq!(stop(&fake, &record()), Ok(StopOutcome::Stopped));
    assert_eq!(fake.stops.get(), 1);
    assert_eq!(fake.snapshots.get(), 2);
}
#[test]
fn wrong_pid_birth_exe_arguments_epoch_or_login_never_stops() {
    for field in 0..8 {
        let fake = Fake::default();
        {
            let mut s = fake.snapshot.borrow_mut();
            match field {
                0 => s.pid += 1,
                1 => s.created_filetime += 1,
                2 => s.executable.push('x'),
                3 => s.arguments.reverse(),
                4 => {
                    s.arguments[2] =
                        "SetEnv=BAT_FLEET_MONITOR=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb".into()
                }
                5 => s.login.owner_sid.push('2'),
                6 => s.login.session_id += 1,
                _ => {
                    let duplicate = s.arguments[2].clone();
                    s.arguments.push(duplicate);
                }
            }
        }
        assert!(stop(&fake, &record()).is_err());
        assert_eq!(fake.stops.get(), 0);
    }
}
#[test]
fn executable_case_matches_but_argument_case_does_not() {
    let fake = Fake::default();
    let lower = fake.snapshot.borrow().executable.to_ascii_lowercase();
    fake.snapshot.borrow_mut().executable = lower;
    assert_eq!(stop(&fake, &record()), Ok(StopOutcome::Stopped));
}
#[test]
fn other_login_is_readonly() {
    let mut fake = Fake::default();
    fake.login.session_id += 1;
    assert_eq!(stop(&fake, &record()), Err("OTHER_LOGIN_OWNER"));
    assert_eq!(fake.snapshots.get(), 0);
    assert_eq!(fake.stops.get(), 0);
}
#[test]
fn wrong_current_epoch_refused() {
    let fake = Fake::default();
    assert_eq!(
        stop_tunnel(
            &fake,
            &record(),
            StopMode::Owned {
                current_epoch: "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
            }
        ),
        Err("OWNER_UNPROVEN")
    );
    assert_eq!(fake.stops.get(), 0);
}
#[test]
fn access_denied_is_not_death() {
    let fake = Fake {
        denied: true,
        ..Default::default()
    };
    assert_eq!(stop(&fake, &record()), Err("OWNER_UNPROVEN"));
    assert_eq!(fake.stops.get(), 0);
}
#[test]
fn proven_absence_has_no_termination() {
    let fake = Fake {
        absent: true,
        ..Default::default()
    };
    assert_eq!(stop(&fake, &record()), Ok(StopOutcome::AlreadyGone));
    assert_eq!(fake.stops.get(), 0);
}
#[test]
fn parent_live_unknown_or_missing_refuses_orphan() {
    for state in [
        ProcessState::Unknown,
        ProcessState::Live {
            created: record().origin.unwrap().created,
        },
    ] {
        let fake = Fake {
            parent: state,
            ..Default::default()
        };
        assert_eq!(
            stop_tunnel(&fake, &record(), StopMode::Orphan),
            Err("ORIGIN_NOT_DEAD")
        );
        assert_eq!(fake.stops.get(), 0);
    }
    let mut rec = record();
    rec.origin = None;
    assert_eq!(
        stop_tunnel(&Fake::default(), &rec, StopMode::Orphan),
        Err("OWNER_UNPROVEN")
    );
}
#[test]
fn parent_dead_or_reused_allows_only_held_child() {
    for parent in [
        ProcessState::Dead,
        ProcessState::Live {
            created: "638368021012345680".into(),
        },
    ] {
        let fake = Fake {
            parent,
            ..Default::default()
        };
        assert_eq!(
            stop_tunnel(&fake, &record(), StopMode::Orphan),
            Ok(StopOutcome::Stopped)
        );
        assert_eq!(fake.snapshot.borrow().pid, 999);
        assert_eq!(fake.stops.get(), 1);
    }
}
#[test]
fn changed_final_handle_evidence_refuses() {
    let fake = Fake {
        mutate_final: true,
        ..Default::default()
    };
    assert_eq!(stop(&fake, &record()), Err("OWNER_UNPROVEN"));
    assert_eq!(fake.stops.get(), 0);
}
#[test]
fn uncertain_exit_never_claims_stopped_or_retries() {
    let fake = Fake {
        unknown_exit: true,
        ..Default::default()
    };
    assert_eq!(stop(&fake, &record()), Err("STOP_UNCONFIRMED"));
    assert_eq!(fake.stops.get(), 1);
}
