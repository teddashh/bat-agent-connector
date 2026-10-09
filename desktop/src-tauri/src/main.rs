#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod bridge;
mod credentials;
mod files;
mod fleet;

use bridge::{Bridge, ConnectorRequest, ConnectorResponse, NativeStatus};
use std::sync::Arc;
use tauri::{
    menu::{Menu, MenuItem},
    tray::{TrayIconBuilder, TrayIconEvent},
    Manager, State, WebviewWindow,
};
use tauri_plugin_dialog::DialogExt;
use tauri_plugin_opener::OpenerExt;
use zeroize::Zeroizing;

#[tauri::command]
fn fleet_availability(
    window: WebviewWindow,
    state: State<'_, fleet::FleetBridge>,
) -> Result<fleet::FleetAvailability, String> {
    local_main(&window)?;
    Ok(state.availability())
}

#[tauri::command]
async fn fleet_request(
    window: WebviewWindow,
    state: State<'_, fleet::FleetBridge>,
    input: fleet::FleetRequest,
) -> Result<serde_json::Value, String> {
    local_main(&window)?;
    state.request(input).await
}

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
fn native_status(
    window: WebviewWindow,
    state: State<'_, Arc<Bridge>>,
) -> Result<NativeStatus, String> {
    local_main(&window)?;
    Ok(state.status())
}

#[tauri::command]
async fn connector_connect(
    window: WebviewWindow,
    state: State<'_, Arc<Bridge>>,
) -> Result<serde_json::Value, String> {
    local_main(&window)?;
    state.connect().await
}

#[tauri::command]
fn connector_disconnect(
    window: WebviewWindow,
    state: State<'_, Arc<Bridge>>,
) -> Result<(), String> {
    local_main(&window)?;
    state.disconnect();
    Ok(())
}

#[tauri::command]
fn connector_reload_configuration(
    window: WebviewWindow,
    state: State<'_, Arc<Bridge>>,
) -> Result<NativeStatus, String> {
    local_main(&window)?;
    state.reload_configuration()
}

#[tauri::command]
fn connector_forget_credential(
    window: WebviewWindow,
    state: State<'_, Arc<Bridge>>,
) -> Result<(), String> {
    local_main(&window)?;
    state.forget_credential()
}

#[tauri::command]
async fn connector_enroll(
    window: WebviewWindow,
    state: State<'_, Arc<Bridge>>,
    locale: credentials::Locale,
) -> Result<Option<serde_json::Value>, String> {
    local_main(&window)?;
    #[cfg(windows)]
    let parent = window.hwnd().map_err(|_| "Native window unavailable")?.0 as isize;
    #[cfg(not(windows))]
    let parent = 0;
    state.enroll(locale, parent).await
}

#[tauri::command]
async fn connector_request(
    window: WebviewWindow,
    state: State<'_, Arc<Bridge>>,
    input: ConnectorRequest,
) -> Result<ConnectorResponse, String> {
    local_main(&window)?;
    state.request(input).await
}

struct NativeFiles(Result<Arc<files::Files>, String>);
impl NativeFiles {
    fn get(&self) -> Result<Arc<files::Files>, String> {
        self.0.clone()
    }
}

#[tauri::command]
fn native_files_status(
    window: WebviewWindow,
    state: State<'_, NativeFiles>,
) -> Result<files::Status, String> {
    local_main(&window)?;
    state.get()?.status()
}
#[tauri::command]
async fn native_files_pick(
    window: WebviewWindow,
    state: State<'_, NativeFiles>,
    draft_id: String,
) -> Result<Vec<files::Receipt>, String> {
    local_main(&window)?;
    files::validate_draft(&draft_id)?;
    let files = state.get()?;
    let _dialog = files
        .dialog
        .try_lock()
        .map_err(|_| "A native file dialog is already open")?;
    let scope = files.scope()?;
    let (tx, rx) = tokio::sync::oneshot::channel();
    window
        .dialog()
        .file()
        .set_parent(&window)
        .pick_files(move |paths| {
            let _ = tx.send(paths);
        });
    let Some(paths) = rx.await.map_err(|_| "File dialog interrupted")? else {
        return Ok(Vec::new());
    };
    let paths = paths
        .into_iter()
        .map(|p| {
            p.into_path()
                .map_err(|_| "Only local regular files are supported".to_string())
        })
        .collect::<Result<Vec<_>, _>>()?;
    files.pick_paths(scope, &draft_id, paths).await
}
#[tauri::command]
fn native_files_drop_target(
    window: WebviewWindow,
    state: State<'_, NativeFiles>,
    draft_id: String,
    enabled: bool,
) -> Result<(), String> {
    local_main(&window)?;
    state.get()?.drop_target(draft_id, enabled)
}
#[tauri::command]
fn native_files_upload(
    window: WebviewWindow,
    state: State<'_, NativeFiles>,
    handle_id: String,
) -> Result<files::Receipt, String> {
    local_main(&window)?;
    state.get()?.start_upload(&handle_id)
}
async fn save_file(
    window: &WebviewWindow,
    files: Arc<files::Files>,
    reference: files::ArtifactRef,
    existing: Option<String>,
) -> Result<Option<files::Receipt>, String> {
    let _dialog = files
        .dialog
        .try_lock()
        .map_err(|_| "A native file dialog is already open")?;
    let scope = files.scope()?;
    let metadata = files.save_metadata(&scope, &reference).await?;
    let (tx, rx) = tokio::sync::oneshot::channel();
    let name = metadata["display_name"]
        .as_str()
        .filter(|name| !name.contains(['/', '\\', ':']))
        .unwrap_or("artifact");
    window
        .dialog()
        .file()
        .set_parent(window)
        .set_file_name(name)
        .save_file(move |path| {
            let _ = tx.send(path);
        });
    let Some(path) = rx.await.map_err(|_| "Save dialog interrupted")? else {
        return Ok(None);
    };
    let path = path
        .into_path()
        .map_err(|_| "Only local destinations are supported")?;
    let destination = files::Destination::from_selection(&path)?;
    files
        .save(scope, reference, metadata, destination, existing)
        .map(Some)
}
#[tauri::command]
async fn native_files_save(
    window: WebviewWindow,
    state: State<'_, NativeFiles>,
    reference: files::ArtifactRef,
) -> Result<Option<files::Receipt>, String> {
    local_main(&window)?;
    save_file(&window, state.get()?, reference, None).await
}
#[tauri::command]
async fn native_files_control(
    window: WebviewWindow,
    state: State<'_, NativeFiles>,
    transfer_id: String,
    action: files::Control,
) -> Result<(), String> {
    local_main(&window)?;
    let files = state.get()?;
    if matches!(action, files::Control::Retry) {
        if let Ok(reference) = files.download_reference(&transfer_id) {
            save_file(&window, files, reference, Some(transfer_id)).await?;
            return Ok(());
        }
    }
    files.control(&transfer_id, action).await
}
#[tauri::command]
async fn native_files_preview(
    window: WebviewWindow,
    state: State<'_, NativeFiles>,
    reference: files::ArtifactRef,
) -> Result<files::Preview, String> {
    local_main(&window)?;
    state.get()?.preview(&reference).await
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
        .plugin(tauri_plugin_dialog::init())
        .setup(move |app| {
            let bridge = Arc::new(Bridge::load(&app.path().app_config_dir()?, token));
            app.manage(NativeFiles(files::Files::open(
                &app.path().app_local_data_dir()?.join("file-transfers"),
                bridge.clone(),
            )));
            app.manage(bridge);
            app.manage(fleet::FleetBridge::load(&app.path().app_config_dir()?));
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
        .on_webview_event(|webview, event| {
            if webview.label() == "main" {
                if let tauri::WebviewEvent::DragDrop(tauri::DragDropEvent::Drop { paths, .. }) =
                    event
                {
                    if let Ok(files) = webview.state::<NativeFiles>().get() {
                        let paths = paths.clone();
                        tauri::async_runtime::spawn(files.dropped(paths));
                    }
                }
            }
        })
        .on_window_event(|window, event| {
            if window.label() == "main" {
                if let tauri::WindowEvent::DragDrop(tauri::DragDropEvent::Drop { paths, .. }) =
                    event
                {
                    if let Ok(files) = window.state::<NativeFiles>().get() {
                        let paths = paths.clone();
                        tauri::async_runtime::spawn(files.dropped(paths));
                    }
                }
            }
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                // Never stop central tasks: this app has no daemon or Fleet ownership.
                if window.hide().is_ok() {
                    api.prevent_close();
                }
            }
        })
        .invoke_handler(tauri::generate_handler![
            native_files_status,
            native_files_pick,
            native_files_drop_target,
            native_files_upload,
            native_files_save,
            native_files_control,
            native_files_preview,
            native_status,
            connector_connect,
            connector_disconnect,
            connector_reload_configuration,
            connector_forget_credential,
            connector_enroll,
            connector_request,
            fleet_availability,
            fleet_request,
            open_external
        ])
        .run(tauri::generate_context!())
        .expect("desktop application startup");
}
