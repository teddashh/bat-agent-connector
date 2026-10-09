use bat_fleet_core::configuration::{Configuration, Paths};
use std::{
    path::PathBuf,
    sync::atomic::{AtomicU64, Ordering},
};
pub struct Fixture(pub PathBuf);
impl Fixture {
    pub fn new() -> Self {
        static NEXT: AtomicU64 = AtomicU64::new(0);
        let root = std::env::temp_dir().join(format!(
            "bac-fleet-config-{}-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        ));
        std::fs::create_dir(&root).unwrap();
        std::fs::create_dir_all(root.join("kit/bat-profiles")).unwrap();
        std::fs::create_dir(root.join("使用者🦀")).unwrap();
        std::fs::write(
            root.join("kit/fleet-inventory.json"),
            include_bytes!("../fixtures/inventory.json"),
        )
        .unwrap();
        std::fs::write(
            root.join("kit/bat-profiles/index.json"),
            include_bytes!("../fixtures/profile-index.json"),
        )
        .unwrap();
        std::fs::write(
            root.join("kit/ssh-config"),
            include_bytes!("../fixtures/ssh-config"),
        )
        .unwrap();
        Self(root)
    }
    pub fn paths(&self) -> Paths {
        Paths::new(&self.0.join("kit"), &self.0.join("使用者🦀"), None, None).unwrap()
    }
    pub fn load(&self) -> Configuration {
        Configuration::load(self.paths()).unwrap()
    }
}
impl Drop for Fixture {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.0);
    }
}
