fn main() {
    tauri_build::try_build(tauri_build::Attributes::new().app_manifest(
        tauri_build::AppManifest::new().commands(&[
            "native_status",
            "connector_connect",
            "connector_disconnect",
            "connector_reload_configuration",
            "connector_forget_credential",
            "connector_enroll",
            "connector_request",
            "connector_upload_artifact",
            "open_external",
            "fleet_availability",
            "fleet_request",
        ]),
    ))
    .expect("desktop build configuration");
}
