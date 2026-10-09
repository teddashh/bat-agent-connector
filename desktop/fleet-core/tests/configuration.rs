use bat_fleet_core::{
    configuration::{data_directory, Configuration, Paths},
    digest,
};
use std::path::Path;
mod support;
use support::Fixture;

#[test]
fn default_binding_matches_powershell_bytes_and_utf16_path_lengths_without_writes() {
    let fixture = Fixture::new();
    let mut expected = String::from("desktop-configuration-v1\n");
    for relative in [
        "kit/fleet-inventory.json",
        "kit/bat-profiles/index.json",
        "kit/ssh-config",
        "使用者🦀/.ssh/config",
    ] {
        let path = fixture.0.join(relative);
        let full = path.to_str().unwrap();
        expected.push_str(&format!("{}:{full}:", full.encode_utf16().count()));
        if path.exists() {
            expected.push_str(&format!(
                "present:{}\n",
                digest(&std::fs::read(path).unwrap())
            ));
        } else {
            expected.push_str("absent\n");
        }
    }
    let before = std::fs::read(fixture.0.join("kit/fleet-inventory.json")).unwrap();
    let configuration = fixture.load();
    assert_eq!(configuration.binding(), digest(expected.as_bytes()));
    assert!(configuration.issues.is_empty());
    assert_eq!(configuration.inventory.hosts().len(), 5);
    configuration.verify_current().unwrap();
    assert!(!fixture.0.join("使用者🦀/.ssh").exists());
    assert_eq!(
        before,
        std::fs::read(fixture.0.join("kit/fleet-inventory.json")).unwrap()
    );
}

#[test]
fn changing_any_bound_bytes_or_creating_user_ssh_invalidates_old_results() {
    for relative in [
        "kit/fleet-inventory.json",
        "kit/bat-profiles/index.json",
        "kit/ssh-config",
        "使用者🦀/.ssh/config",
    ] {
        let fixture = Fixture::new();
        let configuration = fixture.load();
        let file = fixture.0.join(relative);
        let mut bytes = std::fs::read(&file).unwrap_or_default();
        bytes.extend_from_slice(b"\n");
        std::fs::create_dir_all(file.parent().unwrap()).unwrap();
        std::fs::write(file, bytes).unwrap();
        assert_eq!(configuration.verify_current(), Err("CONFIGURATION_CHANGED"));
        assert_ne!(configuration.binding(), fixture.load().binding());
    }
}

#[test]
fn alternate_inventory_requires_paired_index_and_binds_trusted_schema_and_pins() {
    let fixture = Fixture::new();
    let kit = fixture.0.join("kit");
    let user = fixture.0.join("使用者🦀");
    let alternate = fixture.0.join("other.json");
    std::fs::copy(kit.join("fleet-inventory.json"), &alternate).unwrap();
    assert!(matches!(
        Paths::new(&kit, &user, Some(&alternate), None),
        Err("PROFILE_INDEX_REQUIRED")
    ));
    let index = fixture.0.join("other-index.json");
    std::fs::copy(kit.join("bat-profiles/index.json"), &index).unwrap();
    let configuration =
        Configuration::load(Paths::new(&kit, &user, Some(&alternate), Some(&index)).unwrap())
            .unwrap();
    assert!(configuration.issues.is_empty());
    let trusted = kit.join("bat-profiles/index.json");
    let changed = std::fs::read_to_string(&trusted)
        .unwrap()
        .replace(&"AB".repeat(32), &"CD".repeat(32));
    std::fs::write(trusted, changed).unwrap();
    assert_eq!(configuration.verify_current(), Err("CONFIGURATION_CHANGED"));
    let fresh =
        Configuration::load(Paths::new(&kit, &user, Some(&alternate), Some(&index)).unwrap())
            .unwrap();
    assert!(fresh.issues.iter().any(|i| i.code == "PROFILE_DRIFT"));
}

#[test]
fn bom_is_parsed_but_still_changes_binding_and_oversized_or_malformed_data_refuses() {
    let fixture = Fixture::new();
    let previous = fixture.load();
    let path = fixture.0.join("kit/fleet-inventory.json");
    let mut bytes = b"\xef\xbb\xbf".to_vec();
    bytes.extend_from_slice(include_bytes!("fixtures/inventory.json"));
    std::fs::write(&path, bytes).unwrap();
    assert_ne!(previous.binding(), fixture.load().binding());
    assert_eq!(previous.verify_current(), Err("CONFIGURATION_CHANGED"));
    for bad in [
        vec![b' '; 1_048_577],
        br#"{"schema_version":1,"SCHEMA_VERSION":1}"#.to_vec(),
        vec![0xff],
    ] {
        std::fs::write(&path, bad).unwrap();
        assert!(Configuration::load(fixture.paths()).is_err());
    }
}

#[test]
fn data_directory_rechecks_migration_and_refuses_file_instead_of_directory() {
    let fixture = Fixture::new();
    let old = fixture.0.join("org.tonyq.better-agent-terminal");
    let new = fixture.0.join("BetterAgentTerminal");
    assert_eq!(data_directory(&fixture.0).unwrap(), new);
    assert!(!new.exists());
    std::fs::create_dir(&old).unwrap();
    assert_eq!(data_directory(&fixture.0).unwrap(), old);
    std::fs::create_dir(&new).unwrap();
    assert_eq!(data_directory(&fixture.0).unwrap(), new);
    std::fs::remove_dir(&new).unwrap();
    std::fs::write(&new, b"not a directory").unwrap();
    assert_eq!(data_directory(&fixture.0), Err("DATA_DIRECTORY_INVALID"));
}

#[test]
fn missing_required_files_refuse_and_normalized_default_path_needs_no_alternate_pair() {
    let fixture = Fixture::new();
    let kit = fixture.0.join("kit");
    let alias = kit.join(Path::new("bat-profiles/../fleet-inventory.json"));
    let paths = Paths::new(&kit, &fixture.0.join("使用者🦀"), Some(&alias), None).unwrap();
    assert_eq!(
        Configuration::load(paths).unwrap().binding(),
        fixture.load().binding()
    );
    std::fs::remove_file(kit.join("ssh-config")).unwrap();
    assert!(matches!(
        Configuration::load(fixture.paths()),
        Err("CONFIGURATION_UNREADABLE")
    ));
}
