//! Absence proof when the installation file is missing. Never adopts, clears or stops anything.
//! Caller must retain the shared Launcher and Monitor mutexes through this check and its effect.
use crate::{discovery::Observation, monitor_launch, supervisor_io, Result};
use std::path::Path;

fn plain_directory(path: &Path) -> Result<bool> {
    let metadata = match path.symlink_metadata() {
        Ok(value) => value,
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => return Ok(false),
        Err(_) => return Err("FLEET_ABSENCE_UNPROVEN"),
    };
    if !metadata.is_dir() || metadata.file_type().is_symlink() {
        return Err("FLEET_ABSENCE_UNPROVEN");
    }
    #[cfg(windows)]
    {
        use std::os::windows::fs::MetadataExt;
        if metadata.file_attributes() & 0x400 != 0 {
            return Err("FLEET_ABSENCE_UNPROVEN");
        }
    }
    Ok(true)
}

fn installation_absent(path: &Path) -> Result<()> {
    match path.symlink_metadata() {
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => Ok(()),
        _ => Err("FLEET_CONFIGURATION_UNPROVEN"),
    }
}

fn migration_absent(installation: &Path) -> Result<()> {
    let parent = installation.parent().ok_or("INSTALLATION_INVALID")?;
    if !plain_directory(parent)? {
        return Ok(());
    }
    let directory = parent.join("fleet-migrations");
    if !plain_directory(&directory)? {
        return Ok(());
    }
    // Even an apparently complete pointer needs its original configuration for recovery.
    // Do not construct migration::Store: reading it can create persistence directories.
    match directory.join("active.json").symlink_metadata() {
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => Ok(()),
        Ok(_) => Err("MIGRATION_PENDING"),
        Err(_) => Err("FLEET_ABSENCE_UNPROVEN"),
    }
}

fn ownership_absent(roaming: &Path) -> Result<()> {
    for directory in supervisor_io::directories(roaming)? {
        if !plain_directory(&directory)? {
            continue;
        }
        if supervisor_io::read(&directory.join("fleet-monitor.json"))?.is_some() {
            return Err("FLEET_OWNERSHIP_REQUIRES_CONFIGURATION");
        }
        for name in [
            "fleet-tunnel-owners",
            "fleet-tunnel-intents",
            "fleet-tunnel-stop-intents",
        ] {
            let path = directory.join(name);
            if plain_directory(&path)? {
                let mut entries = std::fs::read_dir(&path).map_err(|_| "FLEET_ABSENCE_UNPROVEN")?;
                // Any residue is evidence, not permission to infer a dead or unsent child.
                if entries.next().is_some() {
                    return Err("FLEET_OWNERSHIP_REQUIRES_CONFIGURATION");
                }
                plain_directory(&path)?;
            }
        }
        plain_directory(&directory)?;
    }
    Ok(())
}

/// Only fixed account-local evidence is read. Remaining ownership files, including stale or
/// malformed ones, require restoring configuration and using ordinary ownership recovery.
pub fn verify_absence(
    installation: &Path,
    roaming: &Path,
    observation: &impl Observation,
) -> Result<()> {
    if !installation.is_absolute() || !roaming.is_absolute() || !plain_directory(roaming)? {
        return Err("FLEET_ABSENCE_UNPROVEN");
    }
    installation_absent(installation)?;
    migration_absent(installation)?;
    let login = observation.current_login()?;
    if !login.valid() {
        return Err("OWNER_UNPROVEN");
    }
    ownership_absent(roaming)?;
    monitor_launch::verify_absence(&roaming.join("bat-fleet-monitor-launch.json"), observation)?;
    let candidates = observation.legacy_candidates()?;
    if candidates.len() > 1024 {
        return Err("OWNER_UNPROVEN");
    }
    for process in candidates {
        if !process.valid() {
            return Err("OWNER_UNPROVEN");
        }
        if process.login.owner_sid == login.owner_sid
            && process.arguments.iter().any(|argument| {
                argument.rsplit(['\\', '/']).next().is_some_and(|name| {
                    name.eq_ignore_ascii_case("bat-connect.ps1")
                        || name.eq_ignore_ascii_case("fleet-monitor.ps1")
                })
            })
        {
            return Err("FLEET_OWNERSHIP_REQUIRES_CONFIGURATION");
        }
    }
    if observation.current_login()? != login || !plain_directory(roaming)? {
        return Err("OWNER_UNPROVEN");
    }
    ownership_absent(roaming)?;
    monitor_launch::verify_absence(&roaming.join("bat-fleet-monitor-launch.json"), observation)?;
    migration_absent(installation)?;
    installation_absent(installation)
}
