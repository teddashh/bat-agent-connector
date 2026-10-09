//! Fleet local contracts. This crate contains no central task authority and no IPC.
//! Configuration is native-only; callers project an explicitly safe status model.
pub mod configuration;
pub mod inventory;
pub mod ownership;
pub mod process_adapter;
pub mod selection;
pub mod selection_io;
pub mod strict_json;
#[cfg(windows)]
pub mod windows;

pub type Result<T> = std::result::Result<T, &'static str>;

pub fn digest(bytes: &[u8]) -> String {
    use sha2::{Digest, Sha256};
    format!("{:x}", Sha256::digest(bytes))
}
