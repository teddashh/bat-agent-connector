//! Typed T10 diagnostics/recovery. Long-lived credentials and raw status never reach the WebView.
use crate::fleet_control::Control;
use bat_fleet_core::tailscale::id_valid;
use serde::Deserialize;
use serde_json::{json, Value};
use std::sync::Arc;
#[cfg(any(windows, test))]
static STATUS_BUSY: std::sync::atomic::AtomicBool = std::sync::atomic::AtomicBool::new(false);
#[cfg(any(windows, test))]
struct StatusGuard;
#[cfg(any(windows, test))]
impl StatusGuard {
    fn enter() -> bat_fleet_core::Result<Self> {
        STATUS_BUSY
            .compare_exchange(
                false,
                true,
                std::sync::atomic::Ordering::SeqCst,
                std::sync::atomic::Ordering::SeqCst,
            )
            .map_err(|_| "TAILSCALE_STATUS_BUSY")?;
        Ok(Self)
    }
}
#[cfg(any(windows, test))]
impl Drop for StatusGuard {
    fn drop(&mut self) {
        STATUS_BUSY.store(false, std::sync::atomic::Ordering::SeqCst);
    }
}
#[derive(Deserialize)]
#[serde(tag = "action", rename_all = "snake_case", deny_unknown_fields)]
pub enum Request {
    Status {},
    Open { request_id: String },
    Receipt { request_id: String },
}
impl Request {
    fn validate(&self) -> bat_fleet_core::Result<()> {
        if matches!(self,Self::Open{request_id}|Self::Receipt{request_id} if !id_valid(request_id))
        {
            Err("TAILSCALE_REQUEST_INVALID")
        } else {
            Ok(())
        }
    }
}
pub async fn request(control: Arc<Control>, input: Request) -> Result<Value, String> {
    input.validate().map_err(String::from)?;
    let ticket = control.ticket();
    #[cfg(windows)]
    {
        tokio::task::spawn_blocking(move || {
            windows_request(&control.config, input, &ticket).map_err(String::from)
        })
        .await
        .map_err(|_| "TAILSCALE_OUTCOME_UNKNOWN".to_string())?
    }
    #[cfg(not(windows))]
    {
        let _ = (control, ticket);
        match input {
            Request::Status {} => Ok(
                json!({"version":1,"supported":false,"scope":null,"installation":"unknown","login":"unknown","can_open":false,"latest":null}),
            ),
            _ => Err("TAILSCALE_WINDOWS_REQUIRED".into()),
        }
    }
}
#[cfg(windows)]
fn windows_request(
    config: &std::path::Path,
    input: Request,
    ticket: &crate::fleet_lifecycle::Ticket,
) -> bat_fleet_core::Result<Value> {
    use bat_fleet_core::{
        installation::Snapshot,
        tailscale::Store,
        windows::current_login,
        windows_launcher::LauncherMutex,
        windows_tailscale::{roaming_directory, Installation},
    };
    let login = current_login()?;
    let scope =
        bat_fleet_core::digest(format!("{}:{}", login.owner_sid, login.session_id).as_bytes());
    let store = Store::new(&roaming_directory()?, &scope)?;
    let receipt = |value| json!({"version":1,"scope":scope,"receipt":value});
    match input {
        Request::Receipt { request_id } => Ok(receipt(store.receipt(&request_id)?)),
        Request::Status {} => {
            let _serial = StatusGuard::enter()?;
            let latest = store.latest()?;
            let (installation, can_open, state) = if let Ok(installed) = Installation::load() {
                let runtime = tokio::runtime::Builder::new_current_thread()
                    .enable_all()
                    .build()
                    .map_err(|_| "TAILSCALE_STATUS_UNAVAILABLE")?;
                (
                    installed.installed(),
                    installed.can_open(),
                    runtime.block_on(installed.status()),
                )
            } else {
                (
                    "unknown",
                    false,
                    bat_fleet_core::tailscale::LoginState::Unknown,
                )
            };
            Ok(
                json!({"version":1,"supported":true,"scope":scope,"installation":installation,"login":state,"can_open":can_open,"latest":latest}),
            )
        }
        Request::Open { request_id } => {
            // Read original even when update/migration/install changes now forbid a new effect.
            if let Some(original) = store.receipt(&request_id)? {
                return Ok(receipt(Some(original)));
            }
            let _launcher =
                ticket.acquire(|| LauncherMutex::try_acquire()?.ok_or("LAUNCHER_BUSY"))?;
            let original = match config
                .try_exists()
                .map_err(|_| "FLEET_CONFIGURATION_UNPROVEN")?
            {
                true => Some(Snapshot::load(config)?),
                false => None,
            };
            let verify = || {
                ticket.verify()?;
                if current_login()? != login {
                    return Err("OWNER_CHANGED");
                }
                if bat_fleet_core::migration::Store::new(
                    config,
                    &bat_fleet_core::windows_startup::startup_directory()?,
                )?
                .pending()?
                .is_some()
                {
                    return Err("MIGRATION_PENDING");
                }
                if let Some(original) = &original {
                    original.verify_current()?;
                    crate::fleet_native::verify_no_migration(original)?;
                } else if config
                    .try_exists()
                    .map_err(|_| "FLEET_CONFIGURATION_UNPROVEN")?
                {
                    return Err("FLEET_CONFIGURATION_CHANGED");
                }
                Ok(())
            };
            verify()?;
            let installed = Installation::load()?;
            if !installed.can_open() {
                return Err("TAILSCALE_APP_MISSING");
            }
            Ok(receipt(Some(
                store.open(&request_id, verify, || installed.open())?,
            )))
        }
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn status_process_concurrency_is_bounded_and_guard_recovers() {
        let guard = StatusGuard::enter().unwrap();
        assert!(StatusGuard::enter().is_err());
        drop(guard);
        assert!(StatusGuard::enter().is_ok());
    }
    #[test]
    fn queued_open_ticket_remains_invalid_after_stop_then_reset() {
        let tickets = Arc::new(crate::fleet_lifecycle::Tickets::default());
        let ticket = tickets.capture();
        tickets.set_stopping(true);
        tickets.set_stopping(false);
        let reached = std::cell::Cell::new(false);
        let result = ticket.acquire(|| {
            reached.set(true);
            Ok(())
        });
        assert!(reached.get());
        assert_eq!(result.unwrap_err(), "FLEET_STOP_REQUESTED");
        assert!(tickets.capture().verify().is_ok());
    }
    #[test]
    fn rejects_paths_urls_commands_and_malformed_ids() {
        for value in [
            json!({"action":"status","url":"secret"}),
            json!({"action":"open","request_id":"a".repeat(32),"args":[]}),
            json!({"action":"login"}),
            json!({"action":"open","request_id":"../x"}),
            json!({"action":"receipt","request_id":"A".repeat(32)}),
        ] {
            assert!(
                serde_json::from_value::<Request>(value).map_or(true, |v| v.validate().is_err())
            );
        }
        assert!(serde_json::from_value::<Request>(
            json!({"action":"open","request_id":"a".repeat(32)})
        )
        .unwrap()
        .validate()
        .is_ok());
    }
}
