//! Fleet local contracts. This crate contains no central task authority and no IPC.
//! Configuration is native-only; callers project an explicitly safe status model.
pub mod configuration;
pub mod credential;
pub mod discovery;
pub mod installation;
pub mod inventory;
pub mod ownership;
pub mod probe;
mod probe_wire;
pub mod process_adapter;
pub mod route;
mod route_probe;
pub mod selection;
pub mod selection_io;
pub mod strict_json;
pub mod supervisor;
pub mod supervisor_control;
pub mod supervisor_io;
pub mod supervisor_probe;
pub mod supervisor_status;
pub mod tunnel;
#[cfg(windows)]
pub mod windows;
#[cfg(windows)]
pub mod windows_launcher;
#[cfg(windows)]
pub mod windows_supervisor;
#[cfg(windows)]
pub mod windows_tunnel;

pub type Result<T> = std::result::Result<T, &'static str>;

pub fn digest(bytes: &[u8]) -> String {
    use sha2::{Digest, Sha256};
    format!("{:x}", Sha256::digest(bytes))
}
