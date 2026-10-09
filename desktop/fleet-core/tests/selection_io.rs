use bat_fleet_core::{selection::launch_plan, selection_io::Store};
mod support;
use support::Fixture;

#[test]
fn fixed_preferences_roundtrip_independent_choices_and_no_unseen_reenable() {
    let fixture = Fixture::new();
    let configuration = fixture.load();
    let store = Store::new(fixture.0.clone());
    let before = store.read(&configuration).unwrap();
    let after = store
        .set_connections(&configuration, &before, &["node-2".into()], None, || {
            Ok(None)
        })
        .unwrap();
    assert_ne!(before.revision, after.revision);
    assert_eq!(after.preferences().connections, ["node-2"]);
    assert_eq!(after.preferences().profiles, ["profile-2"]);
    assert!(!after.preferences().dashboard);
    let reloaded = store.read(&configuration).unwrap();
    assert_eq!(after.revision, reloaded.revision);
    assert_eq!(
        launch_plan(&configuration.inventory, reloaded.preferences()).connect,
        ["node-2"]
    );
    assert!(matches!(
        store.set_connections(&configuration, &before, &[], None, || Ok(None)),
        Err("SELECTION_CHANGED")
    ));
}

#[test]
fn legacy_edit_cannot_hide_behind_same_missing_primary_revision() {
    let fixture = Fixture::new();
    let configuration = fixture.load();
    let directory = fixture.0.join("BetterAgentTerminal");
    std::fs::create_dir(&directory).unwrap();
    let legacy = directory.join("open-bat-selection.json");
    std::fs::write(&legacy, br#"{"profile-2":true}"#).unwrap();
    let store = Store::new(fixture.0.clone());
    let first = store.read(&configuration).unwrap();
    std::fs::write(&legacy, br#"{"profile-3":true}"#).unwrap();
    let second = store.read(&configuration).unwrap();
    assert_eq!(first.revision, second.revision); // PowerShell compatibility hash of missing primary bytes.
    assert_ne!(first.preferences(), second.preferences());
    assert!(matches!(
        store.set_connections(&configuration, &first, &[], None, || Ok(None)),
        Err("SELECTION_CHANGED")
    ));
    assert!(!directory.join("fleet-client.json").exists());
    let after = store
        .set_connections(&configuration, &second, &["node-3".into()], None, || {
            Ok(None)
        })
        .unwrap();
    assert_eq!(after.preferences().profiles, ["profile-3"]);
    assert_eq!(std::fs::read(&legacy).unwrap(), br#"{"profile-3":true}"#);
}

#[test]
fn configuration_and_owner_are_rechecked_after_preparation_before_publication() {
    for late in [false, true] {
        let fixture = Fixture::new();
        let configuration = fixture.load();
        let store = Store::new(fixture.0.clone());
        let before = store.read(&configuration).unwrap();
        let mut checks = 0;
        let outcome = store.set_connections(&configuration, &before, &[], None, || {
            checks += 1;
            if !late || checks == 2 {
                Ok(Some("a".repeat(32)))
            } else {
                Ok(None)
            }
        });
        assert!(matches!(outcome, Err("MONITOR_EPOCH_CHANGED")));
        let names: Vec<_> = std::fs::read_dir(fixture.0.join("BetterAgentTerminal"))
            .unwrap()
            .map(|e| e.unwrap().file_name())
            .collect();
        assert_eq!(names, ["fleet-client.json.lock"]);
    }
}

#[test]
fn unknown_owner_and_changed_configuration_refuse_without_publication() {
    let fixture = Fixture::new();
    let configuration = fixture.load();
    let store = Store::new(fixture.0.clone());
    let before = store.read(&configuration).unwrap();
    assert!(matches!(
        store.set_connections(&configuration, &before, &[], None, || Err("OWNER_UNPROVEN")),
        Err("OWNER_UNPROVEN")
    ));
    std::fs::write(fixture.0.join("kit/ssh-config"), b"changed").unwrap();
    assert!(matches!(
        store.set_connections(&configuration, &before, &[], None, || panic!(
            "old config must refuse first"
        )),
        Err("CONFIGURATION_CHANGED")
    ));
    assert!(!fixture
        .0
        .join("BetterAgentTerminal/fleet-client.json")
        .exists());
}

#[test]
fn configuration_changes_during_final_owner_probe_cannot_publish_old_selection() {
    let fixture = Fixture::new();
    let configuration = fixture.load();
    let store = Store::new(fixture.0.clone());
    let before = store.read(&configuration).unwrap();
    let mut probes = 0;
    let outcome = store.set_connections(&configuration, &before, &[], None, || {
        probes += 1;
        if probes == 2 {
            std::fs::write(fixture.0.join("kit/ssh-config"), b"changed").unwrap();
        }
        Ok(None)
    });
    assert!(matches!(outcome, Err("CONFIGURATION_CHANGED")));
    assert!(!fixture
        .0
        .join("BetterAgentTerminal/fleet-client.json")
        .exists());
}

#[test]
fn data_directory_migration_refuses_old_snapshot_and_preserves_both_selections() {
    let fixture = Fixture::new();
    let old = fixture.0.join("org.tonyq.better-agent-terminal");
    let new = fixture.0.join("BetterAgentTerminal");
    std::fs::create_dir(&old).unwrap();
    let configuration = fixture.load();
    let store = Store::new(fixture.0.clone());
    let before = store.read(&configuration).unwrap();
    std::fs::create_dir(&new).unwrap();
    assert!(matches!(
        store.set_connections(&configuration, &before, &[], None, || Ok(None)),
        Err("DATA_DIRECTORY_CHANGED")
    ));
    assert!(!old.join("fleet-client.json").exists());
    assert!(!new.join("fleet-client.json").exists());
}

#[test]
fn malformed_existing_preferences_never_fall_back_to_all_enabled() {
    let fixture = Fixture::new();
    let configuration = fixture.load();
    let store = Store::new(fixture.0.clone());
    store.read(&configuration).unwrap();
    let path = fixture.0.join("BetterAgentTerminal/fleet-client.json");
    for bad in [
        b"{broken".as_slice(),
        b"[]",
        br#"{"version":1,"VERSION":1}"#,
    ] {
        std::fs::write(&path, bad).unwrap();
        assert!(store.read(&configuration).is_err());
        assert_eq!(std::fs::read(&path).unwrap(), bad);
    }
}

#[cfg(not(windows))]
#[test]
fn lock_contention_is_bounded_and_never_removes_another_writers_lock() {
    let fixture = Fixture::new();
    let configuration = fixture.load();
    let store = Store::new(fixture.0.clone());
    let before = store.read(&configuration).unwrap();
    let path = fixture.0.join("BetterAgentTerminal/fleet-client.json.lock");
    let file = std::fs::OpenOptions::new()
        .read(true)
        .write(true)
        .open(&path)
        .unwrap();
    file.lock().unwrap();
    let now = std::time::Instant::now();
    assert!(matches!(
        store.set_connections(&configuration, &before, &[], None, || panic!(
            "lock must be held first"
        )),
        Err("SELECTION_BUSY")
    ));
    assert!(now.elapsed() < std::time::Duration::from_secs(4));
    assert!(path.exists());
    drop(file);
    store
        .set_connections(&configuration, &before, &[], None, || Ok(None))
        .unwrap();
}

#[test]
fn freshly_loaded_configuration_cannot_retarget_an_older_selection_snapshot() {
    for published in [false, true] {
        let fixture = Fixture::new();
        let original = fixture.load();
        let store = Store::new(fixture.0.clone());
        let read = store.read(&original).unwrap();
        let before = if published {
            store
                .set_connections(&original, &read, &["node-2".into()], None, || Ok(None))
                .unwrap()
        } else {
            read
        };
        let path = fixture.0.join("BetterAgentTerminal/fleet-client.json");
        let bytes = std::fs::read(&path).ok();
        let ssh = fixture.0.join("kit/ssh-config");
        let changed = std::fs::read_to_string(&ssh)
            .unwrap()
            .replace("192.0.2.1", "192.0.2.2");
        std::fs::write(ssh, changed).unwrap();
        let current = fixture.load();
        assert!(current.issues.is_empty());
        assert_ne!(original.binding(), current.binding());
        let fresh = store.read(&current).unwrap();
        assert_eq!(fresh.revision, before.revision); // Same stored preferences; only the route changed.
        assert!(matches!(
            store.set_connections(&current, &before, &["node-3".into()], None, || {
                panic!("stale configuration intent must refuse before probing an owner")
            }),
            Err("CONFIGURATION_CHANGED")
        ));
        assert_eq!(std::fs::read(&path).ok(), bytes);
        assert!(!std::fs::read_dir(path.parent().unwrap())
            .unwrap()
            .any(|entry| entry
                .unwrap()
                .file_name()
                .to_string_lossy()
                .ends_with(".tmp")));
        let accepted = store
            .set_connections(&current, &fresh, &["node-3".into()], None, || Ok(None))
            .unwrap();
        assert_eq!(accepted.preferences().connections, ["node-3"]);
    }
}
