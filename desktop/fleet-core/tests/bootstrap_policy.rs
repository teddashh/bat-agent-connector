mod support;
use bat_fleet_core::{
    bootstrap_policy::{route, unavailable},
    discovery::{Backend, MonitorIdentity, Observation, Ownership},
    ownership::{ProbeGeneration, ProcessState},
    process_adapter::{LoginIdentity, ProcessSnapshot, TunnelRecord},
    selection_io::Store,
    supervisor_status::Snapshot,
    tunnel::Plan,
    Result,
};
use serde_json::json;
use support::Fixture;
struct Observe {
    login: LoginIdentity,
    child: ProcessSnapshot,
}
impl Observation for Observe {
    fn current_login(&self) -> Result<LoginIdentity> {
        Ok(self.login.clone())
    }
    fn state(&self, _: u32) -> ProcessState {
        ProcessState::Unknown
    }
    fn observe(&self, pid: u32) -> Result<Option<ProcessSnapshot>> {
        Ok((pid == self.child.pid).then(|| self.child.clone()))
    }
    fn legacy_candidates(&self) -> Result<Vec<ProcessSnapshot>> {
        Ok(vec![])
    }
}
#[test]
fn exact_owned_route_is_required_not_an_open_port_or_old_epoch() {
    let f = Fixture::new();
    let path = f.0.join("kit/fleet-inventory.json");
    let mut document: serde_json::Value =
        serde_json::from_slice(&std::fs::read(&path).unwrap()).unwrap();
    document["connector"]["ssh_alias"] = json!("fixture-connector");
    std::fs::write(path, serde_json::to_vec(&document).unwrap()).unwrap();
    let ssh = f.0.join("kit/ssh-config");
    let mut text = std::fs::read_to_string(&ssh).unwrap();
    text.push_str("\nHost fixture-connector\n HostName example.invalid\n");
    std::fs::write(ssh, text).unwrap();
    let c = f.load();
    let store = Store::new(f.0.clone());
    let before = store.read(&c).unwrap();
    let selected = store
        .set_connections(&c, &before, &["connector".into()], None, || Ok(None))
        .unwrap();
    let login = LoginIdentity {
        owner_sid: "S-1-5-21-1".into(),
        session_id: 1,
    };
    let parent = ProcessSnapshot {
        pid: 12,
        created_filetime: 1_000_000,
        executable: "C:\\fixture\\dashboard.exe".into(),
        arguments: vec![],
        login: login.clone(),
    };
    let epoch = "a".repeat(32);
    let owner = MonitorIdentity {
        process: parent.clone(),
        backend: Backend::Rust,
        instance: Some(epoch.clone()),
        ownership: Ownership::CurrentLogin,
        directories: vec![f.0.join("BetterAgentTerminal")],
        legacy: false,
        record: None,
    };
    let alias = c.inventory.connector()["ssh_alias"].as_str().unwrap();
    let plan = Plan::new(&c, &selected, "connector", alias, &epoch).unwrap();
    let executable = "C:\\Windows\\System32\\OpenSSH\\ssh.exe";
    let child = ProcessSnapshot {
        pid: 24,
        created_filetime: 2_000_000,
        executable: executable.into(),
        arguments: plan.arguments().to_vec(),
        login: login.clone(),
    };
    let mut observer = Observe {
        login,
        child: child.clone(),
    };
    assert!(route(&c, &selected, &owner, &observer, executable).is_err());
    let dir = owner.directories[0].join("fleet-tunnel-owners");
    std::fs::create_dir_all(&dir).unwrap();
    let raw = serde_json::to_vec(
        &TunnelRecord::from_snapshot(&child, &parent)
            .unwrap()
            .document()
            .unwrap(),
    )
    .unwrap();
    std::fs::write(dir.join("connector.json"), &raw).unwrap();
    route(&c, &selected, &owner, &observer, executable).unwrap();
    observer.child.created_filetime += 1;
    assert!(route(&c, &selected, &owner, &observer, executable).is_err());
    observer.child = child;
    let mut changed = owner.clone();
    changed.instance = Some("b".repeat(32));
    assert!(route(&c, &selected, &changed, &observer, executable).is_err());
    changed = owner.clone();
    changed.ownership = Ownership::OtherLogin;
    assert!(route(&c, &selected, &changed, &observer, executable).is_err());
    observer.child.arguments.push("unreviewed".into());
    assert!(route(&c, &selected, &owner, &observer, executable).is_err());
}
#[test]
fn healthy_auth_unknown_old_or_wrong_generation_never_authorize_ensure() {
    let f = Fixture::new();
    let c = f.load();
    let selected = Store::new(f.0.clone()).read(&c).unwrap();
    let original = json!({"schema_version":1,"monitor_epoch":"a".repeat(32),"configuration_binding":c.binding(),"observed_at":"1970-01-01T00:01:00Z","applied_selection_revision":selected.revision,"lifecycle":"running","entries":[{"name":"connector","label":"Synthetic","selected":true,"level":"down","blocking":"connector","code":"CONNECTOR_UNAVAILABLE","observed_at":"1970-01-01T00:01:00Z","stale":false,"layers":{}}]});
    let generation = ProbeGeneration {
        epoch: "a".repeat(32),
        configuration_binding: c.binding().into(),
        selection_revision: selected.revision.clone(),
        generation: 0,
    };
    let parse = |value| serde_json::from_value::<Snapshot>(value).unwrap();
    unavailable(&parse(original.clone()), &selected, &generation, 60_000).unwrap();
    for (pointer, value) in [
        ("/entries/0/level", json!("ready")),
        ("/entries/0/code", json!("CONNECTOR_AUTH_REFUSED")),
        ("/entries/0/code", json!("CONNECTOR_CONTRACT_MISMATCH")),
        ("/entries/0/code", json!("CREDENTIAL_MISSING")),
        ("/entries/0/stale", json!(true)),
        ("/entries/0/observed_at", json!("1969-12-31T23:59:59Z")),
        ("/entries/0/observed_at", json!("1970-01-01T00:01:01Z")),
        ("/entries/0/selected", json!(false)),
        ("/applied_selection_revision", json!("f".repeat(64))),
        ("/monitor_epoch", json!("b".repeat(32))),
        ("/configuration_binding", json!("e".repeat(64))),
        ("/lifecycle", json!("selection_pending")),
    ] {
        let mut changed = original.clone();
        *changed.pointer_mut(pointer).unwrap() = value;
        assert!(
            unavailable(&parse(changed), &selected, &generation, 60_000).is_err(),
            "{pointer}"
        );
    }
}
