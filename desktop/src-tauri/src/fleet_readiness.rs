//! Per-profile readiness gate; Dashboard/Connector visibility never waits on this gate.
#![cfg_attr(not(any(windows, test)), allow(dead_code))]
use bat_fleet_core::{probe::Authentication, supervisor_status::Snapshot};
pub fn profiles_ready(
    snapshot: &Snapshot,
    names: &[&str],
    revision: &str,
    now: u64,
) -> bat_fleet_core::Result<()> {
    if !snapshot.is_fresh(now)?
        || snapshot.lifecycle != "running"
        || snapshot.applied_selection_revision != revision
    {
        return Err("BAT_READINESS_PENDING");
    }
    for name in names {
        if !snapshot.entries.iter().any(|r| {
            r.name == *name
                && r.selected
                && r.level == "ready"
                && !r.stale
                && r.layers.tunnel
                && r.layers.tls
                && r.layers.bat
                && r.layers.workspace
                && r.layers.auth == Some(Authentication::Ok)
        }) {
            return Err("BAT_READINESS_PENDING");
        }
    }
    Ok(())
}
#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    fn fixture() -> serde_json::Value {
        json!({"schema_version":1,"monitor_epoch":"a".repeat(32),"configuration_binding":"b".repeat(64),"observed_at":"1970-01-01T00:00:10Z","applied_selection_revision":"c".repeat(64),"lifecycle":"running","entries":[{"name":"node","label":"Fixture","selected":true,"level":"ready","blocking":null,"code":null,"observed_at":"1970-01-01T00:00:10Z","stale":false,"layers":{"tunnel":true,"tls":true,"bat":true,"workspace":true,"auth":"ok"}}]})
    }
    #[test]
    fn exact_selected_authenticated_fresh_generation_only() {
        let v = fixture();
        let snapshot: Snapshot = serde_json::from_value(v.clone()).unwrap();
        assert!(profiles_ready(&snapshot, &["node"], &"c".repeat(64), 10_000).is_ok());
        assert!(profiles_ready(&snapshot, &["other"], &"c".repeat(64), 10_000).is_err());
        assert!(profiles_ready(&snapshot, &["node"], &"d".repeat(64), 10_000).is_err());
        assert!(profiles_ready(&snapshot, &["node"], &"c".repeat(64), 71_000).is_err());
        for (path, value) in [
            ("/entries/0/selected", json!(false)),
            ("/entries/0/stale", json!(true)),
            ("/entries/0/layers/auth", json!("unknown")),
            ("/entries/0/layers/workspace", json!(false)),
            ("/lifecycle", json!("selection_pending")),
        ] {
            let mut changed = v.clone();
            *changed.pointer_mut(path).unwrap() = value;
            assert!(profiles_ready(
                &serde_json::from_value(changed).unwrap(),
                &["node"],
                &"c".repeat(64),
                10_000
            )
            .is_err());
        }
    }
}
