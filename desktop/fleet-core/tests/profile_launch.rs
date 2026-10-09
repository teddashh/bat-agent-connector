mod support;
use bat_fleet_core::{
    configuration::Configuration,
    process_adapter::{LoginIdentity, ProcessSnapshot},
    profile_launch::{self, Executable, Outcome, Platform, State},
    selection::Choices,
    selection_io::{Snapshot, Store},
    tunnel::SpawnFailure,
    Result,
};
use serde_json::json;
use std::{
    cell::{Cell, RefCell},
    path::PathBuf,
};
use support::Fixture;

struct Mock {
    executable: PathBuf,
    spawns: usize,
    resolves: Cell<usize>,
    processes: RefCell<Vec<ProcessSnapshot>>,
    login: LoginIdentity,
    fail: u8,
    unknown: bool,
    edit_during_stage: Cell<bool>,
    manual_during_stage: Cell<bool>,
    directory: PathBuf,
}
impl Mock {
    fn process(&self, pid: u32) -> ProcessSnapshot {
        ProcessSnapshot {
            pid,
            created_filetime: 134000000000000000 + u64::from(pid),
            executable: self.executable.to_str().unwrap().into(),
            arguments: vec![],
            login: self.login.clone(),
        }
    }
}
impl Platform for Mock {
    fn verify(&self) -> Result<()> {
        let profiles = self.directory.join("profiles");
        let staging = std::fs::read_dir(&profiles).is_ok_and(|entries| {
            entries.filter_map(|e| e.ok()).any(|e| {
                e.file_name()
                    .to_string_lossy()
                    .starts_with("fleet-profile-")
            })
        });
        if staging && self.edit_during_stage.replace(false) {
            std::fs::write(profiles.join("index.json"), b"exact intervening edit").unwrap();
        }
        if staging && self.manual_during_stage.replace(false) {
            self.processes.borrow_mut().push(self.process(99));
        }
        Ok(())
    }
    fn login(&self) -> Result<LoginIdentity> {
        Ok(self.login.clone())
    }
    fn executable(&self) -> Result<Executable> {
        self.resolves.set(self.resolves.get() + 1);
        Executable::read(&self.executable)
    }
    fn running(&self) -> Result<Vec<ProcessSnapshot>> {
        if self.unknown {
            Err("BAT_PROCESS_UNPROVEN")
        } else {
            Ok(self.processes.borrow().clone())
        }
    }
    fn observe(&self, pid: u32) -> Result<Option<ProcessSnapshot>> {
        if self.unknown {
            Err("BAT_PROCESS_UNPROVEN")
        } else {
            Ok(self
                .processes
                .borrow()
                .iter()
                .find(|p| p.pid == pid)
                .cloned())
        }
    }
    fn spawn(
        &mut self,
        executable: &Executable,
    ) -> std::result::Result<ProcessSnapshot, SpawnFailure> {
        assert_eq!(executable.path(), self.executable);
        self.spawns += 1;
        match self.fail {
            1 => Err(SpawnFailure::NotStarted),
            2 => Err(SpawnFailure::Unconfirmed),
            3 => {
                let mut p = self.process(40);
                p.arguments.push("unexpected".into());
                Ok(p)
            }
            _ => {
                let p = self.process(40 + self.spawns as u32);
                self.processes.borrow_mut().push(p.clone());
                Ok(p)
            }
        }
    }
}
fn fixture(profiles: &[&str], dashboard: bool) -> (Fixture, Configuration, Store, Snapshot, Mock) {
    let f = Fixture::new();
    let path = f.0.join("kit/fleet-inventory.json");
    let mut inventory: serde_json::Value =
        serde_json::from_slice(&std::fs::read(&path).unwrap()).unwrap();
    inventory["connector"]["ssh_alias"] = "fixture-central".into();
    std::fs::write(path, serde_json::to_vec(&inventory).unwrap()).unwrap();
    let ssh = f.0.join("kit/ssh-config");
    let mut value = std::fs::read_to_string(&ssh).unwrap();
    value.push_str("\nHost fixture-central\n HostName example.invalid\n");
    std::fs::write(ssh, value).unwrap();
    let c = f.load();
    let store = Store::new(f.0.clone());
    let snapshot = store.read(&c).unwrap();
    let choice = store
        .preview_choices(
            &c,
            &snapshot,
            &Choices {
                connections: vec![],
                profiles: profiles.iter().map(|v| (*v).into()).collect(),
                dashboard,
            },
            None,
        )
        .unwrap();
    let snapshot = store.apply_choices(&c, &choice, || Ok(None)).unwrap();
    let dir = snapshot.directory().to_path_buf();
    std::fs::create_dir_all(dir.join("profiles")).unwrap();
    let mut index = c.profile_index.document().clone();
    index["profiles"]
        .as_array_mut()
        .unwrap()
        .push(json!({"id":"default","type":"local","name":"Local","layout":{"manual":true}}));
    for profile in index["profiles"].as_array_mut().unwrap() {
        if profile.get("name").is_none() {
            profile["name"] = profile["id"].clone();
        }
        profile["createdAt"] = 0.into();
        profile["updatedAt"] = 0.into();
    }
    index["profiles"][0]["customLocalMetadata"] = json!({"keep":"original"});
    index["windowLayout"] = json!({"columns":3});
    index["activeProfileIds"] = json!(["profile-5"]);
    std::fs::write(
        dir.join("profiles/index.json"),
        serde_json::to_vec(&index).unwrap(),
    )
    .unwrap();
    let exe = f.0.join("BetterAgentTerminal.exe");
    std::fs::write(&exe, b"synthetic executable fixture").unwrap();
    let mock = Mock {
        executable: exe,
        spawns: 0,
        resolves: Cell::new(0),
        processes: RefCell::new(vec![]),
        login: LoginIdentity {
            owner_sid: "S-1-5-21-111-222-333-1001".into(),
            session_id: 2,
        },
        fail: 0,
        unknown: false,
        edit_during_stage: Cell::new(false),
        manual_during_stage: Cell::new(false),
        directory: dir,
    };
    (f, c, store, snapshot, mock)
}
fn state(outcome: Outcome) -> State {
    match outcome {
        Outcome::Receipt(r) => r.state,
        _ => panic!("expected durable receipt"),
    }
}

#[test]
fn choices_preview_is_explicit_cancel_changes_nothing_and_cas_preserves_independence() {
    let (f, c, store, original, _m) = fixture(&[], false);
    let path = original.directory().join("fleet-client.json");
    let before = std::fs::read(&path).unwrap();
    let choice = store
        .preview_choices(
            &c,
            &original,
            &Choices {
                connections: vec!["node-2".into()],
                profiles: vec!["profile-1".into()],
                dashboard: true,
            },
            None,
        )
        .unwrap();
    let summary = choice.summary(&c).unwrap();
    assert_eq!(summary.added_connections, ["node-1", "connector"]);
    assert_eq!(
        summary.effective_connections,
        ["node-2", "node-1", "connector"]
    );
    drop(choice);
    assert_eq!(std::fs::read(&path).unwrap(), before);
    let choice = store
        .preview_choices(&c, &original, &summary.choices, None)
        .unwrap();
    let accepted = store.apply_choices(&c, &choice, || Ok(None)).unwrap();
    assert_eq!(accepted.preferences().connections, ["node-2"]);
    assert_eq!(accepted.preferences().profiles, ["profile-1"]);
    assert!(accepted.preferences().dashboard);
    assert!(matches!(
        store.apply_choices(&c, &choice, || Ok(None)),
        Err("SELECTION_CHANGED")
    ));
    assert!(f.0.exists());
}
#[test]
fn full_choice_apply_rechecks_original_config_private_bytes_and_owner() {
    let (_f, c, store, original, _m) = fixture(&[], false);
    let choice = store
        .preview_choices(
            &c,
            &original,
            &Choices {
                connections: vec![],
                profiles: vec!["default".into()],
                dashboard: false,
            },
            None,
        )
        .unwrap();
    let path = original.directory().join("fleet-client.json");
    let before = std::fs::read(&path).unwrap();
    assert!(matches!(
        store.apply_choices(&c, &choice, || Ok(Some("a".repeat(32)))),
        Err("MONITOR_EPOCH_CHANGED")
    ));
    assert_eq!(std::fs::read(&path).unwrap(), before);
    std::fs::write(&path, b"edited preferences").unwrap();
    assert!(store.apply_choices(&c, &choice, || Ok(None)).is_err());
    assert_eq!(std::fs::read(&path).unwrap(), b"edited preferences");
    assert!(store
        .preview_choices(
            &c,
            &original,
            &Choices {
                connections: vec![],
                profiles: vec!["default".into(), "default".into()],
                dashboard: false
            },
            None
        )
        .is_err());
}
#[test]
fn exact_profile_launch_preserves_metadata_and_replays_after_bat_changes_its_index() {
    let (f, c, store, selection, mut m) = fixture(&["profile-1", "default"], false);
    let path = selection.directory().join("profiles/index.json");
    let before: serde_json::Value = serde_json::from_slice(&std::fs::read(&path).unwrap()).unwrap();
    let preview = profile_launch::preview(&c, &store, &selection, &f.0, &m).unwrap();
    assert!(!preview.summary().bat_may_open_local_window);
    assert_eq!(
        state(profile_launch::apply(&c, &store, &preview, &mut m).unwrap()),
        State::Started
    );
    let mut expected = before;
    expected["activeProfileIds"] = json!(["profile-1", "default"]);
    let after: serde_json::Value = serde_json::from_slice(&std::fs::read(&path).unwrap()).unwrap();
    assert_eq!(after, expected);
    std::fs::write(path, b"new BAT-owned runtime bytes").unwrap();
    assert_eq!(
        state(profile_launch::apply(&c, &store, &preview, &mut m).unwrap()),
        State::Started
    );
    let receipt = profile_launch::read_receipt(&f.0, &preview.summary().launch_id, &m)
        .unwrap()
        .unwrap();
    let safe = serde_json::to_string(&receipt).unwrap();
    for private in [
        "executable",
        "owner_sid",
        "remoteFingerprint",
        "remoteHost",
        "created_filetime",
    ] {
        assert!(!safe.contains(private));
    }
    assert_eq!(m.spawns, 1);
}
#[test]
fn dashboard_and_connections_only_do_not_need_bat_or_a_profile_index() {
    for dashboard in [true, false] {
        let (f, c, store, selection, mut m) = fixture(&[], dashboard);
        std::fs::remove_file(&m.executable).unwrap();
        std::fs::remove_dir_all(selection.directory().join("profiles")).unwrap();
        let preview = profile_launch::preview(&c, &store, &selection, &f.0, &m).unwrap();
        assert!(!preview.summary().opens_bat);
        assert!(matches!(
            profile_launch::apply(&c, &store, &preview, &mut m),
            Ok(Outcome::NoBat(_))
        ));
        assert_eq!(m.resolves.get(), 0);
        assert_eq!(m.spawns, 0);
        assert!(!f.0.join("bat-fleet-profile-launch.json").exists());
        std::fs::write(
            f.0.join("bat-fleet-profile-launch.json"),
            b"unknown BAT receipt",
        )
        .unwrap();
        assert!(matches!(
            profile_launch::apply(&c, &store, &preview, &mut m),
            Ok(Outcome::NoBat(_))
        ));
        assert_eq!(
            std::fs::read(f.0.join("bat-fleet-profile-launch.json")).unwrap(),
            b"unknown BAT receipt"
        );
    }
}

#[test]
fn local_default_and_remote_default_alias_match_pinned_bat_startup_semantics() {
    for remote in [false, true] {
        for absent in [false, true] {
            let profiles = if remote {
                vec!["profile-1"]
            } else {
                vec!["default"]
            };
            let (f, c, store, selection, mut m) = fixture(&profiles, false);
            let path = selection.directory().join("profiles/index.json");
            let mut doc: serde_json::Value =
                serde_json::from_slice(&std::fs::read(&path).unwrap()).unwrap();
            if absent {
                doc["profiles"][0]
                    .as_object_mut()
                    .unwrap()
                    .remove("remoteProfileId");
            } else {
                doc["profiles"][0]["remoteProfileId"] = serde_json::Value::Null;
            }
            std::fs::write(&path, serde_json::to_vec(&doc).unwrap()).unwrap();
            let preview = profile_launch::preview(&c, &store, &selection, &f.0, &m).unwrap();
            assert_eq!(preview.summary().bat_may_open_local_window, remote);
            assert_eq!(
                state(profile_launch::apply(&c, &store, &preview, &mut m).unwrap()),
                State::Started
            );
            let after: serde_json::Value =
                serde_json::from_slice(&std::fs::read(path).unwrap()).unwrap();
            doc["activeProfileIds"] = serde_json::to_value(&profiles).unwrap();
            assert_eq!(after, doc);
        }
    }
}

#[test]
fn unknown_duplicate_or_unconfigured_choices_cannot_be_silently_normalized() {
    let (_f, c, store, selection, _m) = fixture(&[], false);
    let path = selection.directory().join("fleet-client.json");
    let original = std::fs::read(&path).unwrap();
    for choices in [
        Choices {
            connections: vec!["node-1".into(), "node-1".into()],
            profiles: vec![],
            dashboard: false,
        },
        Choices {
            connections: vec!["unknown".into()],
            profiles: vec![],
            dashboard: false,
        },
        Choices {
            connections: vec![],
            profiles: vec!["default".into(), "default".into()],
            dashboard: false,
        },
        Choices {
            connections: vec![],
            profiles: vec!["unknown".into()],
            dashboard: false,
        },
    ] {
        assert!(matches!(
            store.preview_choices(&c, &selection, &choices, None),
            Err("SELECTION_INVALID")
        ));
    }
    assert_eq!(std::fs::read(path).unwrap(), original);
}
#[test]
fn manual_or_late_bat_never_rewrites_profiles_and_unknown_or_other_login_refuses() {
    for late in [true, false] {
        let (f, c, store, selection, mut m) = fixture(&["profile-1"], false);
        let path = selection.directory().join("profiles/index.json");
        let original = std::fs::read(&path).unwrap();
        if !late {
            m.processes.borrow_mut().push(m.process(999));
        }
        let preview = profile_launch::preview(&c, &store, &selection, &f.0, &m).unwrap();
        if late {
            m.processes.borrow_mut().push(m.process(999));
        }
        assert!(matches!(
            profile_launch::apply(&c, &store, &preview, &mut m),
            Ok(Outcome::AlreadyRunning(_))
        ));
        assert_eq!(m.spawns, 0);
        assert_eq!(std::fs::read(path).unwrap(), original);
        m.processes.borrow_mut()[0].login.session_id += 1;
        assert!(matches!(
            profile_launch::preview(&c, &store, &selection, &f.0, &m),
            Err("OTHER_LOGIN_OWNER")
        ));
        m.unknown = true;
        assert!(matches!(
            profile_launch::preview(&c, &store, &selection, &f.0, &m),
            Err("BAT_PROCESS_UNPROVEN")
        ));
    }
}
#[test]
fn uncertain_and_misidentified_spawn_remain_fenced_without_repeated_effects() {
    for fail in [2, 3] {
        let (f, c, store, selection, mut m) = fixture(&["profile-1"], false);
        m.fail = fail;
        let preview = profile_launch::preview(&c, &store, &selection, &f.0, &m).unwrap();
        assert_eq!(
            state(profile_launch::apply(&c, &store, &preview, &mut m).unwrap()),
            State::Uncertain
        );
        let bytes = std::fs::read(f.0.join("bat-fleet-profile-launch.json")).unwrap();
        m.fail = 0;
        assert_eq!(
            state(profile_launch::apply(&c, &store, &preview, &mut m).unwrap()),
            State::Uncertain
        );
        let new = profile_launch::preview(&c, &store, &selection, &f.0, &m).unwrap();
        assert!(matches!(
            profile_launch::apply(&c, &store, &new, &mut m),
            Err("BAT_LAUNCH_UNCONFIRMED")
        ));
        assert_eq!(
            std::fs::read(f.0.join("bat-fleet-profile-launch.json")).unwrap(),
            bytes
        );
        assert_eq!(m.spawns, 1);
    }
}
#[test]
fn known_unsent_failure_restores_original_and_requires_new_explicit_intent() {
    let (f, c, store, selection, mut m) = fixture(&["profile-1"], false);
    m.fail = 1;
    let path = selection.directory().join("profiles/index.json");
    let before = std::fs::read(&path).unwrap();
    let preview = profile_launch::preview(&c, &store, &selection, &f.0, &m).unwrap();
    assert_eq!(
        state(profile_launch::apply(&c, &store, &preview, &mut m).unwrap()),
        State::NotStarted
    );
    assert_eq!(std::fs::read(&path).unwrap(), before);
    m.fail = 0;
    assert_eq!(
        state(profile_launch::apply(&c, &store, &preview, &mut m).unwrap()),
        State::NotStarted
    );
    assert_eq!(m.spawns, 1);
    let fresh = profile_launch::preview(&c, &store, &selection, &f.0, &m).unwrap();
    assert_eq!(
        state(profile_launch::apply(&c, &store, &fresh, &mut m).unwrap()),
        State::Started
    );
    assert_eq!(m.spawns, 2);
    assert_eq!(
        state(profile_launch::apply(&c, &store, &preview, &mut m).unwrap()),
        State::NotStarted
    );
    assert_eq!(m.spawns, 2);
}
#[test]
fn historical_started_id_never_relaunches_after_new_explicit_launch() {
    let (f, c, store, selection, mut m) = fixture(&["profile-1"], false);
    let original = profile_launch::preview(&c, &store, &selection, &f.0, &m).unwrap();
    assert_eq!(
        state(profile_launch::apply(&c, &store, &original, &mut m).unwrap()),
        State::Started
    );
    m.processes.borrow_mut().clear();
    let new = profile_launch::preview(&c, &store, &selection, &f.0, &m).unwrap();
    assert_eq!(
        state(profile_launch::apply(&c, &store, &new, &mut m).unwrap()),
        State::Started
    );
    assert_eq!(
        state(profile_launch::apply(&c, &store, &original, &mut m).unwrap()),
        State::Started
    );
    assert_eq!(m.spawns, 2);
}
#[test]
fn edits_after_preview_or_during_staging_preserve_exact_new_bytes_without_spawn() {
    for staged in [false, true] {
        let (f, c, store, selection, mut m) = fixture(&["profile-1"], false);
        let path = selection.directory().join("profiles/index.json");
        let preview = profile_launch::preview(&c, &store, &selection, &f.0, &m).unwrap();
        if staged {
            m.edit_during_stage.set(true);
        } else {
            std::fs::write(&path, b"exact intervening edit").unwrap();
        }
        let result = profile_launch::apply(&c, &store, &preview, &mut m);
        if staged {
            assert_eq!(state(result.unwrap()), State::NotStarted);
        } else {
            assert!(matches!(result, Err("PROFILE_INDEX_CHANGED")));
        }
        assert_eq!(std::fs::read(path).unwrap(), b"exact intervening edit");
        assert_eq!(m.spawns, 0);
    }
}
#[test]
fn manual_bat_appearing_during_staging_blocks_index_publication_and_launch() {
    let (f, c, store, selection, mut m) = fixture(&["profile-1"], false);
    let path = selection.directory().join("profiles/index.json");
    let before = std::fs::read(&path).unwrap();
    let preview = profile_launch::preview(&c, &store, &selection, &f.0, &m).unwrap();
    m.manual_during_stage.set(true);
    assert_eq!(
        state(profile_launch::apply(&c, &store, &preview, &mut m).unwrap()),
        State::NotStarted
    );
    assert_eq!(std::fs::read(path).unwrap(), before);
    assert_eq!(m.spawns, 0);
    assert_eq!(m.processes.borrow().len(), 1);
}
#[test]
fn same_length_image_edit_and_selected_live_profile_drift_refuse() {
    let (f, c, store, selection, mut m) = fixture(&["profile-1"], false);
    let preview = profile_launch::preview(&c, &store, &selection, &f.0, &m).unwrap();
    let old = std::fs::read(&m.executable).unwrap();
    std::fs::write(&m.executable, vec![b'x'; old.len()]).unwrap();
    assert!(matches!(
        profile_launch::apply(&c, &store, &preview, &mut m),
        Err("BAT_EXECUTABLE_CHANGED")
    ));
    assert_eq!(m.spawns, 0);
    let path = selection.directory().join("profiles/index.json");
    let mut doc: serde_json::Value =
        serde_json::from_slice(&std::fs::read(&path).unwrap()).unwrap();
    doc["profiles"][0]["remotePort"] = 19999.into();
    std::fs::write(&path, serde_json::to_vec(&doc).unwrap()).unwrap();
    assert!(matches!(
        profile_launch::preview(&c, &store, &selection, &f.0, &m),
        Err("PROFILE_DRIFT")
    ));
}
#[test]
fn changed_configuration_selection_login_or_directory_cannot_retarget_preview() {
    for change in [0, 1, 2, 3] {
        let (f, c, store, selection, mut m) = fixture(&["profile-1"], false);
        let preview = profile_launch::preview(&c, &store, &selection, &f.0, &m).unwrap();
        match change {
            0 => std::fs::write(f.0.join("kit/ssh-config"), b"changed").unwrap(),
            1 => {
                let new = store
                    .preview_choices(
                        &c,
                        &selection,
                        &Choices {
                            connections: vec![],
                            profiles: vec!["default".into()],
                            dashboard: false,
                        },
                        None,
                    )
                    .unwrap();
                store.apply_choices(&c, &new, || Ok(None)).unwrap();
            }
            2 => m.login.session_id += 1,
            _ => {
                let source = selection.directory();
                std::fs::rename(source, f.0.join("org.tonyq.better-agent-terminal")).unwrap();
            }
        }
        assert!(profile_launch::apply(&c, &store, &preview, &mut m).is_err());
        assert_eq!(m.spawns, 0);
        assert!(!f.0.join("bat-fleet-profile-launch.json").exists());
    }
}
#[cfg(unix)]
#[test]
fn linked_profile_index_and_image_are_never_followed() {
    use std::os::unix::fs::symlink;
    let (f, c, store, selection, m) = fixture(&["profile-1"], false);
    let path = selection.directory().join("profiles/index.json");
    let saved = f.0.join("original-index");
    std::fs::rename(&path, &saved).unwrap();
    symlink(&saved, &path).unwrap();
    assert!(matches!(
        profile_launch::preview(&c, &store, &selection, &f.0, &m),
        Err("PROFILE_INDEX_UNPROVEN")
    ));
    let real = f.0.join("real.exe");
    std::fs::rename(&m.executable, &real).unwrap();
    symlink(&real, &m.executable).unwrap();
    assert!(Executable::read(&m.executable).is_err());
}

#[test]
fn selected_ssh_override_or_bat_invalid_metadata_never_starts_an_unreviewed_profile() {
    for case in [0, 1, 2, 3] {
        let (f, c, store, selection, m) = fixture(&["profile-1"], false);
        let path = selection.directory().join("profiles/index.json");
        let mut doc: serde_json::Value =
            serde_json::from_slice(&std::fs::read(&path).unwrap()).unwrap();
        match case {
            0 => doc["profiles"][0]["sshTarget"] = "unreviewed-alias".into(),
            1 => {
                doc["profiles"][0].as_object_mut().unwrap().remove("name");
            }
            2 => doc["profiles"][0]["createdAt"] = "invalid timestamp".into(),
            _ => {
                doc["profiles"][1]["remotePort"] =
                    "invalid unused record would trigger whole-index fallback".into()
            }
        }
        let bytes = serde_json::to_vec(&doc).unwrap();
        std::fs::write(&path, &bytes).unwrap();
        assert!(profile_launch::preview(&c, &store, &selection, &f.0, &m).is_err());
        assert_eq!(std::fs::read(path).unwrap(), bytes);
        assert_eq!(m.spawns, 0);
    }
}

#[test]
fn missing_or_retargeted_receipt_never_reissues_a_retained_preview() {
    let (f, c, store, selection, mut m) = fixture(&["profile-1"], false);
    let preview = profile_launch::preview(&c, &store, &selection, &f.0, &m).unwrap();
    assert_eq!(
        state(profile_launch::apply(&c, &store, &preview, &mut m).unwrap()),
        State::Started
    );
    let path = f.0.join("bat-fleet-profile-launch.json");
    let bytes = std::fs::read(&path).unwrap();
    let mut changed: serde_json::Value = serde_json::from_slice(&bytes).unwrap();
    changed["profiles"] = json!(["profile-2"]);
    std::fs::write(&path, serde_json::to_vec(&changed).unwrap()).unwrap();
    assert!(matches!(
        profile_launch::apply(&c, &store, &preview, &mut m),
        Err("BAT_LAUNCH_UNPROVEN")
    ));
    std::fs::remove_file(path).unwrap();
    m.processes.borrow_mut().clear();
    assert!(matches!(
        profile_launch::apply(&c, &store, &preview, &mut m),
        Err("BAT_LAUNCH_UNCONFIRMED")
    ));
    assert_eq!(m.spawns, 1);
}

#[test]
fn receipt_readback_refuses_another_login_and_malformed_fixed_id() {
    let (f, c, store, selection, mut m) = fixture(&["profile-1"], false);
    let preview = profile_launch::preview(&c, &store, &selection, &f.0, &m).unwrap();
    profile_launch::apply(&c, &store, &preview, &mut m).unwrap();
    m.login.session_id += 1;
    assert!(matches!(
        profile_launch::read_receipt(&f.0, &preview.summary().launch_id, &m),
        Err("OTHER_LOGIN_OWNER")
    ));
    assert!(matches!(
        profile_launch::read_receipt(&f.0, "../untrusted.json", &m),
        Err("INVALID_REQUEST")
    ));
}
