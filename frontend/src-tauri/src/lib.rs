use serde_json::{json, Value};
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use tauri::{AppHandle, Emitter, Manager, State};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;
use tokio::sync::{oneshot, Mutex};
use uuid::Uuid;

struct SidecarState {
    child: Mutex<Option<CommandChild>>,
    pending: Mutex<HashMap<String, oneshot::Sender<Result<Value, String>>>>,
}

impl SidecarState {
    fn new() -> Self {
        Self { child: Mutex::new(None), pending: Mutex::new(HashMap::new()) }
    }
}

async fn ensure_sidecar(app: &AppHandle, state: &SidecarState) -> Result<(), String> {
    let mut child_guard = state.child.lock().await;
    if child_guard.is_some() {
        return Ok(());
    }
    let sidecar = app.shell().sidecar("pdf2word-sidecar").map_err(|error| error.to_string())?;
    let (mut receiver, child) = sidecar.spawn().map_err(|error| error.to_string())?;
    *child_guard = Some(child);
    drop(child_guard);

    let app_handle = app.clone();
    tauri::async_runtime::spawn(async move {
        let mut buffered = String::new();
        while let Some(event) = receiver.recv().await {
            match event {
                CommandEvent::Stdout(bytes) => {
                    buffered.push_str(&String::from_utf8_lossy(&bytes));
                    while let Some(position) = buffered.find('\n') {
                        let line = buffered[..position].trim().to_string();
                        buffered.drain(..=position);
                        if let Ok(message) = serde_json::from_str::<Value>(&line) {
                            if let Some(request_id) = message.get("request_id").and_then(Value::as_str) {
                                let state = app_handle.state::<Arc<SidecarState>>();
                                let sender = {
                                    let mut pending = state.pending.lock().await;
                                    pending.remove(request_id)
                                };
                                if let Some(sender) = sender {
                                    let response = if message.get("ok").and_then(Value::as_bool) == Some(false) {
                                        Err(message.get("error").and_then(Value::as_str).unwrap_or("后端错误").to_string())
                                    } else {
                                        Ok(message.get("data").cloned().unwrap_or(message.clone()))
                                    };
                                    let _ = sender.send(response);
                                }
                            }
                            let _ = app_handle.emit("sidecar-message", message);
                        }
                    }
                }
                CommandEvent::Stderr(bytes) => {
                    let _ = app_handle.emit("sidecar-message", json!({
                        "type": "diagnostic",
                        "message": String::from_utf8_lossy(&bytes).trim()
                    }));
                }
                CommandEvent::Error(message) => {
                    let _ = app_handle.emit("sidecar-message", json!({"type": "error", "message": message}));
                }
                CommandEvent::Terminated(payload) => {
                    let _ = app_handle.emit("sidecar-message", json!({
                        "type": "engine_stopped",
                        "code": payload.code,
                        "signal": payload.signal
                    }));
                    break;
                }
                _ => {}
            }
        }
    });
    Ok(())
}

async fn request(app: &AppHandle, state: &SidecarState, mut payload: Value) -> Result<Value, String> {
    ensure_sidecar(app, state).await?;
    let request_id = Uuid::new_v4().to_string();
    payload.as_object_mut().ok_or("IPC 请求必须是对象")?.insert("request_id".into(), json!(request_id));
    let (sender, receiver) = oneshot::channel();
    state.pending.lock().await.insert(request_id, sender);
    let command = format!("{}\n", serde_json::to_string(&payload).map_err(|error| error.to_string())?);
    let mut child_guard = state.child.lock().await;
    child_guard.as_mut().ok_or("本地处理引擎未启动")?.write(command.as_bytes()).map_err(|error| error.to_string())?;
    drop(child_guard);
    receiver.await.map_err(|_| "本地处理引擎未响应".to_string())?
}

fn safe_output_path(input_path: &str, output_directory: &str) -> Result<PathBuf, String> {
    let input = Path::new(input_path);
    let output = Path::new(output_directory);
    if !input.is_file() || input.extension().and_then(|value| value.to_str()).map(|value| value.eq_ignore_ascii_case("pdf")) != Some(true) {
        return Err("请选择可访问的 PDF 文件".into());
    }
    if !output.is_dir() {
        return Err("请选择可访问的输出目录".into());
    }
    let stem = input.file_stem().and_then(|value| value.to_str()).unwrap_or("document");
    Ok(output.join(format!("{stem}.docx")))
}

#[tauri::command]
async fn preflight(app: AppHandle, state: State<'_, Arc<SidecarState>>, input_path: String, password: Option<String>) -> Result<Value, String> {
    request(&app, &state, json!({"command": "preflight", "input_path": input_path, "password": password})).await
}

#[tauri::command]
async fn start_conversion(
    app: AppHandle,
    state: State<'_, Arc<SidecarState>>,
    input_path: String,
    output_directory: String,
    password: Option<String>,
    mut config: Value,
) -> Result<String, String> {
    let docx = safe_output_path(&input_path, &output_directory)?;
    if let Some(object) = config.as_object_mut() {
        object.insert("password".into(), json!(password));
    }
    let job_id = Uuid::new_v4().to_string();
    request(&app, &state, json!({
        "command": "start", "job_id": job_id, "input_path": input_path,
        "output_docx": docx, "config": config
    })).await?;
    Ok(job_id)
}

#[tauri::command]
async fn send_sidecar_command(app: AppHandle, state: State<'_, Arc<SidecarState>>, payload: Value) -> Result<Value, String> {
    request(&app, &state, payload).await
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(Arc::new(SidecarState::new()))
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![preflight, start_conversion, send_sidecar_command])
        .run(tauri::generate_context!())
        .expect("error while running Benzhen PDF");
}
