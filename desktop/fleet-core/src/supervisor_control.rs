//! Readonly facade and normal exact-owner quit; neither acquires another owner's mutex.
use crate::{
    configuration::Configuration,
    discovery::{self, DiscoveryConfig, MonitorIdentity, Observation, Ownership},
    supervisor_io as files,
    supervisor_status::Snapshot,
    Result,
};
use std::path::Path;

fn same(a: &MonitorIdentity, b: &MonitorIdentity) -> bool {
    a.process == b.process
        && a.backend == b.backend
        && a.instance == b.instance
        && a.ownership == b.ownership
        && a.legacy == b.legacy
        && a.directories == b.directories
}
/// Callers obtain `expected` from trusted native discovery, never a PID supplied by IPC.
/// Both native and recorded PS owners may exit normally; unrecorded legacy owners cannot.
pub fn request_quit(
    configuration: &Configuration,
    discovery: &DiscoveryConfig,
    observation: &impl Observation,
    quit_file: &Path,
    expected: &MonitorIdentity,
) -> Result<()> {
    if !quit_file.is_absolute()
        || expected.legacy
        || expected.ownership != Ownership::CurrentLogin
        || expected.instance.is_none()
    {
        return Err("OWNER_UNPROVEN");
    }
    let verify = || {
        configuration.verify_current()?;
        let owner = discovery::discover(discovery, observation)?.ok_or("MONITOR_EPOCH_CHANGED")?;
        if !same(&owner, expected) {
            return Err("MONITOR_EPOCH_CHANGED");
        }
        Ok(())
    };
    verify()?;
    let bytes = serde_json::to_vec(
        &serde_json::json!({"pid":expected.process.pid,"instance":expected.instance}),
    )
    .map_err(|_| "QUIT_UNPROVEN")?;
    if let Some(existing) = files::read(quit_file)? {
        if existing == bytes {
            verify()?;
            return Ok(());
        }
        return Err("QUIT_REQUEST_PENDING");
    }
    files::replace(quit_file, None, &bytes, verify)
}
/// Status does not own or stop a monitor. Missing/stale/malformed status is never ready.
/// Cross-login monitor observations may be displayed but cannot be passed to quit.
pub fn read_snapshot(
    configuration: &Configuration,
    discovery: &DiscoveryConfig,
    observation: &impl Observation,
    now_ms: u64,
) -> Result<Option<Snapshot>> {
    configuration.verify_current()?;
    let Some(owner) = discovery::discover(discovery, observation)? else {
        return Ok(None);
    };
    let Some(epoch) = owner.instance.as_deref() else {
        return Ok(None);
    };
    let mut result = None;
    for directory in &owner.directories {
        let Some(bytes) = files::read(&directory.join("fleet-desktop-status.json"))? else {
            continue;
        };
        let snapshot = Snapshot::parse(&bytes, configuration, epoch, now_ms)?;
        // Multiple different copies are not an atomic snapshot; retain no ambiguous readiness.
        if result.as_ref().is_some_and(|prior: &Snapshot| {
            serde_json::to_value(prior).ok() != serde_json::to_value(&snapshot).ok()
        }) {
            return Err("STATUS_UNPROVEN");
        }
        result = Some(snapshot);
    }
    configuration.verify_current()?;
    if !discovery::discover(discovery, observation)?
        .as_ref()
        .is_some_and(|current| same(&owner, current))
    {
        return Err("MONITOR_EPOCH_CHANGED");
    }
    Ok(result)
}
