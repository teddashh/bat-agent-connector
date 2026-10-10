use std::path::Path;

/// Only the shipped public example and synthetic trusted pin; never a user's files.
pub fn write(root: &Path, trusted_fixture_pin: bool) {
    let client = root.join("client");
    std::fs::create_dir_all(client.join("bat-profiles")).unwrap();
    std::fs::write(
        client.join("fleet-inventory.json"),
        include_bytes!("../../../fleet.example/client/fleet-inventory.json"),
    )
    .unwrap();
    std::fs::write(
        client.join("ssh-config"),
        include_bytes!("../../../fleet.example/client/ssh-config"),
    )
    .unwrap();
    let index = include_str!("../../../fleet.example/client/bat-profiles/index.json");
    let index = if trusted_fixture_pin {
        index.replace("REPLACE_WITH_TRUSTED_SHA256_FINGERPRINT", &"AB".repeat(32))
    } else {
        index.to_owned()
    };
    std::fs::write(client.join("bat-profiles/index.json"), index).unwrap();
    let mut config: serde_json::Value =
        serde_json::from_str(include_str!("../../../fleet.example.json")).unwrap();
    config["kit_root"] = serde_json::json!(root);
    std::fs::write(
        root.join("fleet.json"),
        serde_json::to_vec(&config).unwrap(),
    )
    .unwrap();
}
