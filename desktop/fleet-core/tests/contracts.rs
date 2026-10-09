use bat_fleet_core::{
    inventory::{self, Inventory, ProfileIndex},
    ownership::*,
    selection::{launch_plan, Preferences},
    strict_json,
};
use serde_json::{json, Value};

fn inventory_value() -> Value {
    serde_json::from_str(include_str!("fixtures/inventory.json")).unwrap()
}
fn parse(value: &Value) -> Inventory {
    Inventory::parse(&serde_json::to_vec(value).unwrap()).unwrap()
}

#[test]
fn reviewed_synthetic_inventory_index_and_ssh_remain_compatible() {
    let inv = parse(&inventory_value());
    assert_eq!(inv.hosts().len(), 5);
    assert_eq!(inv.hosts()[1]["target"], "192.0.2.2:9000");
    let index = ProfileIndex::parse(include_bytes!("fixtures/profile-index.json"), &[]).unwrap();
    assert!(inventory::configuration_issues(
        &inv,
        &index,
        &index,
        include_str!("fixtures/ssh-config")
    )
    .is_empty());
    assert_eq!(inv.document()["provisioning_profiles"][0], "profile-5");
}

#[test]
fn duplicate_case_escape_nested_keys_and_noncanonical_endpoints_are_refused() {
    for bytes in [
        r#"{"host":1,"host":2}"#,
        r#"{"host":1,"HOST":2}"#,
        r#"{"host":1,"\u0068ost":2}"#,
        r#"{"outer":[{"a":1,"A":2}]}"#,
        r#"{} {}"#,
    ] {
        assert!(strict_json::parse(bytes.as_bytes(), 1024).is_err());
    }
    for endpoint in [
        "127.1:22",
        "127.000.0.1:22",
        "localhost:22",
        "192.0.2.1:22",
        "127.0.0.1:0",
        "127.0.0.1:65536",
        "[::1]:22",
        "127.0.0.1:22\n",
    ] {
        assert!(inventory::endpoint(endpoint, true).is_err(), "{endpoint}");
    }
    assert!(strict_json::parse(&[b' '; 1025], 1024).is_err());
}

#[test]
fn rejects_unknowns_route_reordering_identity_collisions_and_credential_drift() {
    for (pointer, bad) in [
        ("/hosts/0/name", json!("NODE-2")),
        ("/hosts/0/profile", json!("PROFILE-2")),
        ("/hosts/0/local", json!("127.0.0.2:12345")),
        ("/hosts/0/bat/credential_ref", json!("connector-observe")),
        ("/hosts/0/bat/protocol", json!("bat-remote/v1")),
        ("/hosts/0/provision_route", json!("lan")),
        ("/connector/local", json!("127.0.0.1:19001")),
        ("/connector/dashboard_path", json!("//evil")),
        ("/connector/supported_api_versions", json!([true])),
        ("/connector/min_contract_version", json!("2026-02-30")),
        ("/direct_probe_ms", json!(5001)),
        (
            "/hosts/0/workspace_bindings",
            json!([{"id":"a","workspace_id":"w","required":1}]),
        ),
    ] {
        let mut inv = inventory_value();
        *inv.pointer_mut(pointer).unwrap() = bad;
        assert!(
            Inventory::parse(&serde_json::to_vec(&inv).unwrap()).is_err(),
            "{pointer}"
        );
    }
    let mut inv = inventory_value();
    inv["hosts"][0]["force"] = json!(true);
    assert!(Inventory::parse(&serde_json::to_vec(&inv).unwrap()).is_err());
    let mut inv = inventory_value();
    inv["hosts"][0]["routes"].as_array_mut().unwrap().reverse();
    assert!(Inventory::parse(&serde_json::to_vec(&inv).unwrap()).is_err());
    for value in [
        "100.63.255.255:22",
        "100.128.0.0:22",
        "node.example.invalid:22",
        "100.064.0.1:22",
    ] {
        let mut inv = inventory_value();
        inv["hosts"][0]["probe"] = json!(value);
        inv["hosts"][0]["routes"][0]["probe"] = json!(value);
        assert!(
            Inventory::parse(&serde_json::to_vec(&inv).unwrap()).is_err(),
            "{value}"
        );
    }
}

#[test]
fn changed_profiles_pins_and_missing_ssh_alias_never_validate() {
    let inv = parse(&inventory_value());
    let original = ProfileIndex::parse(include_bytes!("fixtures/profile-index.json"), &[]).unwrap();
    for (field, bad) in [
        ("remoteFingerprint", json!("CD".repeat(32))),
        ("remoteProfileId", Value::Null),
        ("remotePort", json!(19002)),
    ] {
        let mut doc = original.document().clone();
        doc["profiles"][0][field] = bad;
        let changed = ProfileIndex::parse(&serde_json::to_vec(&doc).unwrap(), &[]).unwrap();
        assert!(
            inventory::configuration_issues(
                &inv,
                &changed,
                &original,
                include_str!("fixtures/ssh-config")
            )
            .iter()
            .any(|i| i.code == "PROFILE_DRIFT"),
            "{field}"
        );
    }
    assert!(
        inventory::configuration_issues(&inv, &original, &original, "Host *")
            .iter()
            .any(|i| i.code == "SSH_ALIAS_MISSING")
    );
}

#[test]
fn selection_migration_and_dashboard_only_keep_choices_independent() {
    let mut raw = inventory_value();
    raw["connector"]["ssh_alias"] = json!("central-fixture");
    let inv = parse(&raw);
    let raw = br#"{"version":1,"connections":["connector"],"profiles":[],"dashboard":true,"known":["node-1","node-2","node-3","node-4","node-5"]}"#;
    let prefs = Preferences::load(&inv, Some(raw), None).unwrap();
    let plan = launch_plan(&inv, &prefs);
    assert!(plan.dashboard_only);
    assert_eq!(plan.connect, ["connector"]);
    assert!(plan.open.is_empty());
    let changed = prefs.set_connections(&inv, &[]).unwrap();
    assert!(!changed.dashboard);
    assert!(launch_plan(&inv, &changed).connect.is_empty());
    let legacy = Preferences::load(
        &inv,
        None,
        Some(br#"{"profile-2":true,"profile-3":false,"default":true}"#),
    )
    .unwrap();
    assert_eq!(legacy.connections.len(), 5);
    assert_eq!(legacy.profiles, ["default", "profile-2"]);
    assert!(Preferences::load(&inv, Some(b"{invalid"), None).is_err());
}

#[test]
fn newly_added_hosts_default_on_but_explicit_disconnect_never_reopens_via_profile() {
    let inv = parse(&inventory_value());
    let prefs = Preferences::load(&inv, Some(br#"{"version":1,"connections":[],"profiles":[],"dashboard":false,"known":["node-1","node-2","node-3","node-4"]}"#), None).unwrap();
    assert_eq!(prefs.connections, ["node-5"]);
    assert_eq!(prefs.profiles, ["profile-5"]);
    let off = prefs.set_connections(&inv, &[]).unwrap();
    assert!(launch_plan(&inv, &off).connect.is_empty());
    let roundtrip = Preferences::load(&inv, Some(&off.persisted(&inv).unwrap()), None).unwrap();
    assert_eq!(roundtrip, off);
    assert!(prefs
        .set_connections(&inv, &["node-5".into(), "NODE-5".into()])
        .is_err());
}

fn process() -> ProcessEvidence {
    ProcessEvidence {
        pid: 1234,
        created: "638000000000000000".into(),
        executable: "C:\\Windows\\System32\\OpenSSH\\ssh.exe".into(),
        arguments: vec![
            "-N".into(),
            "-o".into(),
            format!("SetEnv=BAT_FLEET_MONITOR={}", "a".repeat(32)),
            "fixture-alias".into(),
        ],
        monitor_instance: "a".repeat(32),
        owner_sid: "S-1-5-21-1-2-3-1001".into(),
        session_id: 2,
    }
}
#[test]
fn pid_reuse_unknown_identity_and_other_login_never_grant_ownership() {
    let expected = process();
    assert!(expected.matches(&expected));
    let mut reused = expected.clone();
    reused.created = "638000000000000001".into();
    assert!(!expected.matches(&reused));
    assert_eq!(
        origin_state(
            expected.pid,
            &expected.created,
            &ProcessState::Live {
                created: reused.created
            }
        ),
        ProcessState::Dead
    );
    assert_eq!(
        origin_state(expected.pid, &expected.created, &ProcessState::Unknown),
        ProcessState::Unknown
    );
    let mut login = expected.clone();
    login.session_id = 3;
    assert!(!expected.matches(&login));
    let mut argv = expected.clone();
    argv.arguments.push("extra".into());
    assert!(!expected.matches(&argv));
    let mut duplicate = expected.clone();
    duplicate.arguments.push(duplicate.arguments[2].clone());
    assert!(!duplicate.valid());
    assert_eq!(
        monitor_mutex(&expected.owner_sid).unwrap(),
        "Global\\BatFleetMonitor_S-1-5-21-1-2-3-1001"
    );
}

#[test]
fn independent_bounded_recovery_and_stale_probe_results() {
    let mut retry = Recovery::new(0);
    assert!(!retry.due(4999));
    retry.attempt(5000).unwrap();
    assert!(!retry.due(19999));
    retry.attempt(20000).unwrap();
    assert!(!retry.due(64999));
    retry.attempt(65000).unwrap();
    assert!(retry.exhausted());
    assert!(!retry.due(999999));
    let current = ProbeGeneration {
        epoch: "a".repeat(32),
        configuration_binding: "b".repeat(64),
        selection_revision: "c".repeat(64),
        generation: 4,
    };
    assert!(probe_current(&current, &current, 0, 60000));
    assert!(!probe_current(&current, &current, 0, 60001));
    let mut changed = current.clone();
    changed.generation += 1;
    assert!(!probe_current(&current, &changed, 0, 1));
}
