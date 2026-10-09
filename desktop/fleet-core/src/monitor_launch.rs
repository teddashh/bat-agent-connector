//! Durable native monitor launch fence. Caller retains the shared launcher mutex.
//! A missing monitor record does not prove a prior spawn never happened.
use crate::{
    discovery::{Backend, MonitorIdentity, NativeIdentity, Observation, Ownership},
    process_adapter::{LoginIdentity, ProcessSnapshot},
    strict_json, supervisor_io as files,
    tunnel::SpawnFailure,
    Result,
};
use serde::{Deserialize, Serialize};
use std::path::Path;

/// Native routing environment only; never inherit app tokens or generic proxy credentials.
pub fn environment(
    values: impl IntoIterator<Item = (std::ffi::OsString, std::ffi::OsString)>,
) -> Vec<(std::ffi::OsString, std::ffi::OsString)> {
    values
        .into_iter()
        .filter(|(key, _)| {
            key.to_str().is_some_and(|key| {
                [
                    "APPDATA",
                    "LOCALAPPDATA",
                    "USERPROFILE",
                    "USERNAME",
                    "TEMP",
                    "TMP",
                    "SYSTEMROOT",
                    "WINDIR",
                    "PATH",
                ]
                .contains(&key.to_ascii_uppercase().as_str())
            })
        })
        .collect()
}

pub trait Platform: Observation {
    /// Recheck installation/configuration and the retained launcher guard's login.
    fn verify(&self) -> Result<()>;
    fn owner(&self) -> Result<Option<MonitorIdentity>>;
    /// Fixed native executable/argv; retain the launch handle through identity capture.
    fn spawn(&mut self) -> std::result::Result<ProcessSnapshot, SpawnFailure>;
}

#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Intent {
    schema_version: u32,
    configuration_binding: String,
    executable: String,
    arguments: Vec<String>,
    owner_sid: String,
    session_id: u32,
    child: Option<Birth>,
}
#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Birth {
    pid: u32,
    created_filetime: String,
}
impl Intent {
    fn parse(bytes: &[u8]) -> Result<Self> {
        let value: Self = serde_json::from_value(strict_json::parse(bytes, 262144)?)
            .map_err(|_| "MONITOR_LAUNCH_UNPROVEN")?;
        if value.schema_version != 1
            || value.configuration_binding.len() != 64
            || !value
                .configuration_binding
                .bytes()
                .all(|c| c.is_ascii_hexdigit())
            || !crate::ownership::sid_valid(&value.owner_sid)
            || value.arguments.len() != 3
            || value.arguments[0] != "--fleet-supervisor"
            || value.arguments[1] != "--fleet-config"
            || NativeIdentity::new(&value.executable, &value.arguments[2]).is_err()
            || value.child.as_ref().is_some_and(|child| {
                child.pid == 0
                    || !child
                        .created_filetime
                        .parse::<u64>()
                        .is_ok_and(|n| crate::process_adapter::datetime_ticks(n).is_ok())
            })
        {
            return Err("MONITOR_LAUNCH_UNPROVEN");
        }
        Ok(value)
    }
    fn login(&self) -> LoginIdentity {
        LoginIdentity {
            owner_sid: self.owner_sid.clone(),
            session_id: self.session_id,
        }
    }
    fn matches(&self, child: &ProcessSnapshot) -> bool {
        child.valid()
            && child.login == self.login()
            && child.executable.eq_ignore_ascii_case(&self.executable)
            && child.arguments == self.arguments
            && self.child.as_ref().is_none_or(|birth| {
                birth.pid == child.pid
                    && birth.created_filetime == child.created_filetime.to_string()
            })
    }
    fn bytes(&self) -> Result<Vec<u8>> {
        serde_json::to_vec(self).map_err(|_| "MONITOR_LAUNCH_UNPROVEN")
    }
    fn record(&mut self, child: &ProcessSnapshot) {
        self.child = Some(Birth {
            pid: child.pid,
            created_filetime: child.created_filetime.to_string(),
        });
    }
}

pub enum Outcome {
    Running(Box<MonitorIdentity>),
    /// This proves only process creation. Facade must read the supervisor's own record/status.
    Started(ProcessSnapshot),
}

/// Read-only migration guard after ordinary discovery has positively found no owner.
/// A missing record cannot exclude an unpublished child from an earlier launch.
/// Keep the journal unchanged; only ensure() may settle its own exact receipt.
pub fn verify_absence(path: &Path, observation: &impl Observation) -> Result<()> {
    let Some(bytes) = files::read(path)? else {
        return Ok(());
    };
    let intent = Intent::parse(&bytes)?;
    if intent.login() != observation.current_login()? {
        return Err("OTHER_LOGIN_OWNER");
    }
    let child = intent.child.ok_or("MONITOR_LAUNCH_UNCONFIRMED")?;
    if observation
        .observe(child.pid)?
        .is_some_and(|current| current.created_filetime.to_string() == child.created_filetime)
    {
        return Err("MONITOR_STARTING");
    }
    if files::read(path)?.as_deref() != Some(&bytes) {
        return Err("MONITOR_LAUNCH_UNPROVEN");
    }
    Ok(())
}

/// `path` is the fixed account-wide roaming launch journal, independent of BAT directory choice.
/// Existing unknown intent is never discarded or reissued, even if discovery finds no owner.
pub fn ensure(
    path: &Path,
    native: &NativeIdentity,
    binding: &str,
    platform: &mut impl Platform,
) -> Result<Outcome> {
    platform.verify()?;
    let login = platform.current_login()?;
    let original = files::read(path)?;
    let mut previous = original.as_deref().map(Intent::parse).transpose()?;
    if previous
        .as_ref()
        .is_some_and(|intent| intent.login() != login)
    {
        return Err("OTHER_LOGIN_OWNER");
    }
    if let Some(owner) = platform.owner()? {
        if owner.backend != Backend::Rust
            || owner.legacy
            || owner.ownership != Ownership::CurrentLogin
            || owner.instance.is_none()
            || !owner
                .process
                .executable
                .eq_ignore_ascii_case(native.executable())
            || owner.process.arguments != native.arguments()
        {
            return Err("MONITOR_ALREADY_RUNNING");
        }
        if let Some(intent) = previous.as_mut() {
            if !intent.matches(&owner.process)
                || intent.child.is_none() && intent.configuration_binding != binding
            {
                return Err("MONITOR_LAUNCH_UNPROVEN");
            }
            // The child may publish before its launcher records the retained launch handle.
            // Readback adopts that exact owner without another spawn; retain its birth for exit recovery.
            if intent.child.is_none() {
                intent.record(&owner.process);
                files::replace(path, original.as_deref(), &intent.bytes()?, || {
                    platform.verify()
                })?;
            }
        }
        platform.verify()?;
        return Ok(Outcome::Running(Box::new(owner)));
    }
    if let Some(intent) = previous {
        let child = intent.child.ok_or("MONITOR_LAUNCH_UNCONFIRMED")?;
        if platform
            .observe(child.pid)?
            .is_some_and(|current| current.created_filetime.to_string() == child.created_filetime)
        {
            return Err("MONITOR_STARTING");
        }
        // Positive absence or a different incarnation permits forgetting this ended launch only.
        // It grants no authority over the process now using that PID.
        platform.verify()?;
        if platform.owner()?.is_some() {
            return Err("MONITOR_ALREADY_RUNNING");
        }
        files::remove(path, original.as_deref().unwrap())?;
    }
    let mut intent = Intent {
        schema_version: 1,
        configuration_binding: binding.into(),
        executable: native.executable().into(),
        arguments: native.arguments().to_vec(),
        owner_sid: login.owner_sid,
        session_id: login.session_id,
        child: None,
    };
    let bytes = intent.bytes()?;
    Intent::parse(&bytes)?;
    files::replace(path, None, &bytes, || {
        platform.verify()?;
        if platform.owner()?.is_some() {
            return Err("MONITOR_ALREADY_RUNNING");
        }
        Ok(())
    })?;
    // Failure before invoking spawn is positively unsent; remove only our exact intent.
    if let Err(error) = platform.verify().and_then(|_| {
        if platform.owner()?.is_some() {
            Err("MONITOR_ALREADY_RUNNING")
        } else {
            Ok(())
        }
    }) {
        files::remove(path, &bytes)?;
        return Err(error);
    }
    match platform.spawn() {
        Ok(child) if intent.matches(&child) => {
            intent.record(&child);
            // Keep the born-child fence even if installation drifts immediately after spawn.
            files::replace(path, Some(&bytes), &intent.bytes()?, || Ok(()))?;
            platform.verify()?;
            Ok(Outcome::Started(child))
        }
        Err(SpawnFailure::NotStarted | SpawnFailure::RolledBack) => {
            files::remove(path, &bytes)?;
            Err("MONITOR_START_FAILED")
        }
        _ => Err("MONITOR_LAUNCH_UNCONFIRMED"),
    }
}
