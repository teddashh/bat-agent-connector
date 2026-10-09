//! Separate local bootstrap worker. Read-only status never waits for its SSH budget.
use crate::fleet_control::Control;
use serde::Deserialize;
use serde_json::Value;
use std::sync::{
    atomic::{AtomicBool, Ordering},
    Arc,
};
#[derive(Deserialize)]
#[serde(tag = "action", rename_all = "snake_case", deny_unknown_fields)]
pub enum Request {
    Overview {},
    Prepare {
        recipe_binding: String,
    },
    Advance {
        request_id: String,
        recipe_binding: String,
    },
    Receipt {
        request_id: String,
    },
}
impl Request {
    pub fn validate(&self) -> bat_fleet_core::Result<()> {
        let hex = |s: &str, n| {
            s.len() == n
                && s.bytes()
                    .all(|c| c.is_ascii_digit() || (b'a'..=b'f').contains(&c))
        };
        let valid = match self {
            Self::Overview {} => true,
            Self::Prepare { recipe_binding } => hex(recipe_binding, 64),
            Self::Advance {
                request_id,
                recipe_binding,
            } => hex(request_id, 32) && hex(recipe_binding, 64),
            Self::Receipt { request_id } => hex(request_id, 32),
        };
        if valid {
            Ok(())
        } else {
            Err("BOOTSTRAP_REQUEST_INVALID")
        }
    }
    fn readonly(&self) -> bool {
        matches!(self, Self::Overview {} | Self::Receipt { .. })
    }
}
#[derive(Default)]
pub struct Bootstrap {
    busy: AtomicBool,
}
struct Busy(Arc<Bootstrap>);
impl Drop for Busy {
    fn drop(&mut self) {
        self.0.busy.store(false, Ordering::SeqCst);
    }
}
impl Bootstrap {
    fn enter(self: &Arc<Self>) -> bat_fleet_core::Result<Busy> {
        self.busy
            .compare_exchange(false, true, Ordering::SeqCst, Ordering::SeqCst)
            .map_err(|_| "BOOTSTRAP_BUSY")?;
        Ok(Busy(self.clone()))
    }
    pub async fn request(
        self: Arc<Self>,
        control: Arc<Control>,
        input: Request,
    ) -> Result<Value, String> {
        input.validate().map_err(String::from)?;
        let ticket = control.ticket();
        let guard = if input.readonly() {
            None
        } else {
            Some(self.enter().map_err(String::from)?)
        };
        #[cfg(windows)]
        {
            tokio::task::spawn_blocking(move || {
                let _guard = guard;
                crate::fleet_native::bootstrap::request(&control.config, input, &ticket)
                    .map_err(String::from)
            })
            .await
            .map_err(|_| "BOOTSTRAP_OUTCOME_UNKNOWN".to_owned())?
        }
        #[cfg(not(windows))]
        {
            let _ = (guard, ticket, control, input);
            Err("BOOTSTRAP_WINDOWS_REQUIRED".into())
        }
    }
    #[cfg(windows)]
    pub fn start_auto(self: Arc<Self>, control: Arc<Control>) {
        let ticket = control.ticket();
        std::thread::spawn(move || {
            // Readiness belongs to the independent supervisor. This worker neither
            // owns its mutex nor blocks the frontend/central connection runtime.
            while ticket.verify().is_ok() {
                if let Ok(_guard) = self.enter() {
                    let _ = crate::fleet_native::bootstrap::automatic(&control.config, &ticket);
                }
                std::thread::sleep(std::time::Duration::from_secs(5));
            }
        });
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    #[test]
    fn only_fixed_actions_and_bound_native_ids_cross_ipc() {
        for body in [
            json!({"action":"ensure","command":"bad"}),
            json!({"action":"overview","path":"C:\\bad"}),
            json!({"action":"prepare","recipe_binding":"x"}),
            json!({"action":"advance","request_id":"../bad","recipe_binding":"a".repeat(64)}),
            json!({"action":"receipt","request_id":"a".repeat(32),"token":"bad"}),
        ] {
            assert!(serde_json::from_value::<Request>(body).map_or(true, |v| v.validate().is_err()));
        }
        let input: Request = serde_json::from_value(
            json!({"action":"advance","request_id":"a".repeat(32),"recipe_binding":"b".repeat(64)}),
        )
        .unwrap();
        assert!(input.validate().is_ok());
    }
    #[test]
    fn one_worker_guard_retained_until_finish_without_blocking_status() {
        let control = Arc::new(Bootstrap::default());
        let first = control.enter().unwrap();
        assert!(control.enter().is_err());
        assert!(Request::Overview {}.readonly());
        assert!(Request::Receipt {
            request_id: "a".repeat(32)
        }
        .readonly());
        drop(first);
        assert!(control.enter().is_ok());
    }
}
