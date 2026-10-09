//! Typed local control. No WebView-supplied filesystem paths, commands or process IDs.
use bat_fleet_core::{discovery::Backend, selection::Choices};
use serde::Deserialize;
use serde_json::Value;
use std::{path::PathBuf, sync::Arc};
#[cfg_attr(not(windows), allow(dead_code))]
#[derive(Deserialize)]
#[serde(tag = "action", rename_all = "snake_case", deny_unknown_fields)]
pub enum Request {
    Overview {},
    PreviewChoices {
        choices: Choices,
        configuration_binding: String,
        selection_revision: String,
        monitor_epoch: Option<String>,
    },
    ApplyChoices {
        preview_id: String,
    },
    PreviewLaunch {},
    Launch {
        preview_id: String,
    },
    LaunchStatus {
        launch_id: String,
    },
    PreviewMigration {
        backend: Backend,
        autostart: bool,
    },
    ApplyMigration {
        preview_id: String,
        fingerprint: String,
    },
    AdvanceMigration {
        migration_id: String,
    },
    MigrationStatus {
        migration_id: String,
    },
    RestoreMigration {
        source_id: String,
        restore_id: String,
    },
    SaveLogin {
        expected_revision: String,
        show_picker: bool,
    },
    Discard {
        preview_id: String,
    },
}
fn hex(value: &str, n: usize) -> bool {
    value.len() == n
        && value
            .bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
}
impl Request {
    pub fn validate(&self) -> Result<(), String> {
        let valid = match self {
            Self::PreviewChoices {
                choices,
                configuration_binding,
                selection_revision,
                monitor_epoch,
            } => {
                choices.connections.len() <= 1000
                    && choices.profiles.len() <= 1000
                    && choices
                        .connections
                        .iter()
                        .chain(&choices.profiles)
                        .all(|v| {
                            !v.is_empty()
                                && v.len() <= 128
                                && v.bytes()
                                    .all(|b| b.is_ascii_alphanumeric() || b"_-.:".contains(&b))
                        })
                    && hex(configuration_binding, 64)
                    && hex(selection_revision, 64)
                    && monitor_epoch.as_ref().is_none_or(|v| hex(v, 32))
            }
            Self::ApplyChoices { preview_id }
            | Self::Launch { preview_id }
            | Self::Discard { preview_id } => hex(preview_id, 32),
            Self::LaunchStatus { launch_id } => hex(launch_id, 32),
            Self::ApplyMigration {
                preview_id,
                fingerprint,
            } => hex(preview_id, 32) && hex(fingerprint, 64),
            Self::AdvanceMigration { migration_id } | Self::MigrationStatus { migration_id } => {
                hex(migration_id, 32)
            }
            Self::RestoreMigration {
                source_id,
                restore_id,
            } => hex(source_id, 32) && hex(restore_id, 32) && source_id != restore_id,
            Self::SaveLogin {
                expected_revision, ..
            } => hex(expected_revision, 64),
            _ => true,
        };
        if valid {
            Ok(())
        } else {
            Err("INVALID_FLEET_CONTROL".into())
        }
    }
}
#[cfg_attr(not(windows), allow(dead_code))]
pub struct Control {
    login: std::sync::Mutex<Value>,
    tickets: Arc<crate::fleet_lifecycle::Tickets>,
    configured_seen: std::sync::atomic::AtomicBool,
    stopping: std::sync::atomic::AtomicBool,
    generation: std::sync::atomic::AtomicU64,
    login_running: std::sync::atomic::AtomicBool,
    pub config: PathBuf,
    #[cfg(windows)]
    state: std::sync::Mutex<crate::fleet_native::Controller>,
}
impl Control {
    pub fn new(config: PathBuf) -> Self {
        let seen = config.try_exists().unwrap_or(true);
        Self {
            config,
            configured_seen: std::sync::atomic::AtomicBool::new(seen),
            login: std::sync::Mutex::new(Value::Null),
            tickets: Arc::new(crate::fleet_lifecycle::Tickets::default()),
            stopping: std::sync::atomic::AtomicBool::new(false),
            generation: std::sync::atomic::AtomicU64::new(0),
            login_running: std::sync::atomic::AtomicBool::new(false),
            #[cfg(windows)]
            state: std::sync::Mutex::new(crate::fleet_native::Controller::default()),
        }
    }

    pub fn observe_configuration(&self) {
        if self.config.try_exists().unwrap_or(true) {
            self.configured_seen
                .store(true, std::sync::atomic::Ordering::SeqCst);
        }
    }
    pub fn never_configured(&self) -> bool {
        !self
            .configured_seen
            .load(std::sync::atomic::Ordering::SeqCst)
    }
    pub fn ticket(&self) -> crate::fleet_lifecycle::Ticket {
        self.tickets.capture()
    }
    pub fn set_stopping(&self, value: bool) {
        self.tickets.set_stopping(value);
        self.stopping
            .store(value, std::sync::atomic::Ordering::SeqCst);
        if value {
            self.cancel_login();
        }
    }
    pub fn cancel_login(&self) {
        self.generation
            .fetch_add(1, std::sync::atomic::Ordering::SeqCst);
    }
    pub fn is_stopping(&self) -> bool {
        self.stopping.load(std::sync::atomic::Ordering::SeqCst)
    }
    /// Each attempt owns the same Rust preview. Slow readiness does not hold the UI/controller lock.
    #[cfg(windows)]
    pub fn start_login(self: Arc<Self>) {
        use std::sync::atomic::Ordering;
        if self.login_running.swap(true, Ordering::SeqCst) {
            return;
        }
        // A previous login result is read back, never implicitly replaced by another invocation.
        if self.login.lock().is_ok_and(|v| !v.is_null()) {
            self.login_running.store(false, Ordering::SeqCst);
            return;
        }
        let generation = self.generation.load(Ordering::SeqCst);
        let ticket = self.ticket();
        std::thread::spawn(move || {
            let result = (|| -> Result<Value, &'static str> {
                let preview = self.state.lock().map_err(|_| "FLEET_CONTROL_BUSY")?
                    .request(&self.config, Request::PreviewLaunch {}, &ticket)?;
                let id = preview["preview_id"].as_str().ok_or("FLEET_RESPONSE_INVALID")?.to_owned();
                *self.login.lock().map_err(|_| "FLEET_CONTROL_BUSY")? = serde_json::json!({"preview_id":id,"summary":preview["summary"],"configuration_binding":preview["configuration_binding"],"state":"waiting"});
                let until = std::time::Instant::now() + std::time::Duration::from_secs(30);
                loop {
                    if self.stopping.load(Ordering::SeqCst) || generation != self.generation.load(Ordering::SeqCst) { return Ok(serde_json::json!({"preview_id":id,"summary":preview["summary"],"configuration_binding":preview["configuration_binding"],"state":"attention","code":"FLEET_STOP_REQUESTED"})); }
                    let result = {
                        let mut state = self.state.lock().map_err(|_| "FLEET_CONTROL_BUSY")?;
                        if self.stopping.load(Ordering::SeqCst) || generation != self.generation.load(Ordering::SeqCst) { return Ok(serde_json::json!({"preview_id":id,"summary":preview["summary"],"configuration_binding":preview["configuration_binding"],"state":"attention","code":"FLEET_STOP_REQUESTED"})); }
                        state.request(&self.config, Request::Launch {preview_id:id.clone()}, &ticket)
                    };
                    match result {
                        Err("BAT_READINESS_PENDING" | "MONITOR_STARTING") if std::time::Instant::now() < until =>
                            std::thread::sleep(std::time::Duration::from_millis(500)),
                        Ok(receipt) => return Ok(serde_json::json!({"preview_id":id,"summary":preview["summary"],"configuration_binding":preview["configuration_binding"],"receipt":receipt,"state":"complete"})),
                        Err(code) => return Ok(serde_json::json!({"preview_id":id,"summary":preview["summary"],"configuration_binding":preview["configuration_binding"],"state":"attention","code":code})),
                    }
                }
            })().unwrap_or_else(|code| serde_json::json!({"state":"attention","code":code}));
            if let Ok(mut value) = self.login.lock() {
                *value = result;
            }
            self.login_running.store(false, Ordering::SeqCst);
        });
    }
    pub async fn request(self: Arc<Self>, input: Request) -> Result<Value, String> {
        let ticket = self.ticket();
        input.validate()?;
        self.observe_configuration();
        if self.stopping.load(std::sync::atomic::Ordering::SeqCst)
            && !matches!(
                input,
                Request::Overview {}
                    | Request::LaunchStatus { .. }
                    | Request::MigrationStatus { .. }
            )
        {
            return Err("FLEET_STOP_REQUESTED".into());
        }
        #[cfg(windows)]
        {
            tokio::task::spawn_blocking(move || {
                if self.stopping.load(std::sync::atomic::Ordering::SeqCst)
                    && !matches!(
                        input,
                        Request::Overview {}
                            | Request::LaunchStatus { .. }
                            | Request::MigrationStatus { .. }
                    )
                {
                    return Err("FLEET_STOP_REQUESTED".into());
                }
                let mut state = self.state.try_lock().map_err(|_| "FLEET_CONTROL_BUSY")?;
                let overview = matches!(input, Request::Overview {});
                let mut value = state
                    .request(&self.config, input, &ticket)
                    .map_err(|code| {
                        format!("Fleet refused ({code}); read the original receipt before retrying")
                    })?;
                if overview {
                    value["login_launch"] =
                        self.login.lock().map_err(|_| "FLEET_CONTROL_BUSY")?.clone();
                }
                Ok(value)
            })
            .await
            .map_err(|_| "FLEET_OUTCOME_UNKNOWN".to_string())?
        }
        #[cfg(not(windows))]
        {
            let _ = (&self.config, ticket);
            Err("Fleet desktop control requires Windows".into())
        }
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    #[test]
    fn removed_configuration_never_becomes_unconfigured_quit() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("fleet.json");
        let control = Control::new(path.clone());
        assert!(control.never_configured());
        std::fs::write(&path, b"{}").unwrap();
        control.observe_configuration();
        std::fs::remove_file(path).unwrap();
        control.observe_configuration();
        assert!(!control.never_configured());
    }
    #[test]
    fn bounded_typed_control_refuses_paths_pids_commands_and_extra_fields() {
        for body in [
            json!({"action":"launch","preview_id":"../other"}),
            json!({"action":"overview","path":"C:\\other"}),
            json!({"action":"launch","preview_id":"a".repeat(32),"pid":3}),
            json!({"action":"preview_migration","backend":"other","autostart":true}),
        ] {
            assert!(serde_json::from_value::<Request>(body).map_or(true, |v| v.validate().is_err()));
        }
    }
    #[test]
    fn valid_shape_still_checks_opaque_identifiers() {
        let value: Request =
            serde_json::from_value(json!({"action":"launch","preview_id":"../other"})).unwrap();
        assert!(value.validate().is_err());
        let value:Request=serde_json::from_value(json!({"action":"apply_migration","preview_id":"a".repeat(32),"fingerprint":"b".repeat(64)})).unwrap();
        assert!(value.validate().is_ok());
    }
}
