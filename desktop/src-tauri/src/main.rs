#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod bridge;

use bridge::{Bridge, ConnectorRequest, ConnectorResponse, NativeStatus};
use tauri::{
    menu::{Menu, MenuItem},
    tray::{TrayIconBuilder, TrayIconEvent},
    Manager, State, WebviewWindow,
};
use tauri_plugin_opener::OpenerExt;
use zeroize::Zeroizing;

#[tauri::command]
fn open_external(window: WebviewWindow, app: tauri::AppHandle, url: String) -> Result<(), String> {
    local_main(&window)?;
    let target = bridge::external_url(&url)?;
    app.opener()
        .open_url(target.as_str(), None::<&str>)
        .map_err(|_| "Unable to open the system browser".into())
}

fn local_main(window: &WebviewWindow) -> Result<(), String> {
    if window.label() != "main" {
        return Err("Only the main Dashboard may use this command".into());
    }
    let url = window.url().map_err(|_| "Window origin unavailable")?;
    let bundled = url.scheme() == "tauri" && url.host_str() == Some("localhost")
        || matches!(url.scheme(), "http" | "https") && url.host_str() == Some("tauri.localhost");
    let dev = cfg!(debug_assertions)
        && url.scheme() == "http"
        && url.host_str() == Some("127.0.0.1")
        && url.port() == Some(1420);
    if !bundled && !dev {
        return Err("Remote content cannot use native commands".into());
    }
    Ok(())
}

#[tauri::command]
fn native_status(window: WebviewWindow, state: State<'_, Bridge>) -> Result<NativeStatus, String> {
    local_main(&window)?;
    Ok(state.status())
}

#[tauri::command]
async fn connector_connect(
    window: WebviewWindow,
    state: State<'_, Bridge>,
) -> Result<serde_json::Value, String> {
    local_main(&window)?;
    state.connect().await
}

#[tauri::command]
fn connector_disconnect(window: WebviewWindow, state: State<'_, Bridge>) -> Result<(), String> {
    local_main(&window)?;
    state.disconnect();
    Ok(())
}

#[tauri::command]
async fn connector_request(
    window: WebviewWindow,
    state: State<'_, Bridge>,
    input: ConnectorRequest,
) -> Result<ConnectorResponse, String> {
    local_main(&window)?;
    state.request(input).await
}

#[tauri::command]
async fn connector_upload_artifact(
    window: WebviewWindow,
    state: State<'_, Bridge>,
    request: tauri::ipc::Request<'_>,
) -> Result<ConnectorResponse, String> {
    local_main(&window)?;
    let tauri::ipc::InvokeBody::Raw(bytes) = request.body() else {
        return Err("Artifact upload requires raw binary IPC bytes".into());
    };
    let operation_id = request
        .headers()
        .get("x-batc-upload-operation")
        .and_then(|value| value.to_str().ok())
        .ok_or("Upload operation ID is required")?;
    // The one IPC metadata field is validated; no IPC header is forwarded to HTTP.
    bridge::validate_artifact_upload(operation_id, bytes.len())?;
    state.upload_artifact(operation_id, bytes).await
}

fn show(app: &tauri::AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.show();
        let _ = window.unminimize();
        let _ = window.set_focus();
    }
}

fn main() {
    // Read/remove before GTK, WebView or async runtime starts any helper threads/processes.
    let token = Zeroizing::new(std::env::var("BATC_DESKTOP_TOKEN").unwrap_or_default());
    std::env::remove_var("BATC_DESKTOP_TOKEN");
    tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _, _| show(app)))
        .plugin(tauri_plugin_opener::init())
        .setup(move |app| {
            app.manage(Bridge::load(&app.path().app_config_dir()?, token));
            let config = app.config().app.windows[0].clone();
            tauri::WebviewWindowBuilder::from_config(app, &config)?
                .on_navigation(|url| {
                    url.scheme() == "tauri" && url.host_str() == Some("localhost")
                        || matches!(url.scheme(), "http" | "https")
                            && url.host_str() == Some("tauri.localhost")
                        || cfg!(debug_assertions)
                            && url.scheme() == "http"
                            && url.host_str() == Some("127.0.0.1")
                            && url.port() == Some(1420)
                })
                .build()?;
            let open = MenuItem::with_id(app, "open", "Open Dashboard", true, None::<&str>)?;
            let quit = MenuItem::with_id(app, "quit", "Quit Dashboard", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&open, &quit])?;
            let mut tray = TrayIconBuilder::new()
                .menu(&menu)
                .tooltip("Better Agent Dashboard")
                .on_menu_event(|app, event| match event.id.as_ref() {
                    "open" => show(app),
                    "quit" => app.exit(0),
                    _ => {}
                })
                .on_tray_icon_event(|tray, event| {
                    if matches!(event, TrayIconEvent::DoubleClick { .. }) {
                        show(tray.app_handle());
                    }
                });
            if let Some(icon) = app.default_window_icon() {
                tray = tray.icon(icon.clone());
            }
            tray.build(app)?;
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                // Never stop central tasks: this app has no daemon or Fleet ownership.
                if window.hide().is_ok() {
                    api.prevent_close();
                }
            }
        })
        .invoke_handler(tauri::generate_handler![
            native_status,
            connector_connect,
            connector_disconnect,
            connector_request,
            connector_upload_artifact,
            open_external
        ])
        .run(tauri::generate_context!())
        .expect("desktop application startup");
}
