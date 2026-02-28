use crate::controlroom::git_provider::get_commits;
use crate::controlroom::types::{
    ControlRoomConfig, GitCommit, RunnerCommandInput, RunnerStartResponse, ServiceConfig,
    ServiceLogEvent, ServiceStatus, VideoLaunchNativeInput, VideoLaunchNativeResult,
    VideoSnapshotAnalyzeInput, VideoSnapshotAnalyzeResult, WorkspaceEntry,
};
use crate::controlroom::workspace::{list_workspace_entries, read_workspace_file, write_workspace_file};
use crate::controlroom::ControlRoomState;
use tauri::{AppHandle, State};

async fn ensure_config(state: &ControlRoomState) -> Result<ControlRoomConfig, String> {
    state.load_config().await
}

#[tauri::command]
pub async fn controlroom_load_config(
    state: State<'_, ControlRoomState>,
) -> Result<ControlRoomConfig, String> {
    state.load_config().await
}

#[tauri::command]
pub async fn controlroom_get_services(
    state: State<'_, ControlRoomState>,
) -> Result<Vec<ServiceConfig>, String> {
    let config = ensure_config(&state).await?;
    Ok(config.services)
}

#[tauri::command]
pub async fn controlroom_service_start(
    service_id: String,
    app: AppHandle,
    state: State<'_, ControlRoomState>,
) -> Result<ServiceStatus, String> {
    ensure_config(&state).await?;
    state
        .process_manager()
        .start_service(&app, &service_id)
        .await
}

#[tauri::command]
pub async fn controlroom_service_stop(
    service_id: String,
    app: AppHandle,
    state: State<'_, ControlRoomState>,
) -> Result<ServiceStatus, String> {
    ensure_config(&state).await?;
    state
        .process_manager()
        .stop_service(&app, &service_id)
        .await
}

#[tauri::command]
pub async fn controlroom_service_restart(
    service_id: String,
    app: AppHandle,
    state: State<'_, ControlRoomState>,
) -> Result<ServiceStatus, String> {
    ensure_config(&state).await?;
    state
        .process_manager()
        .restart_service(&app, &service_id)
        .await
}

#[tauri::command]
pub async fn controlroom_service_status(
    service_id: String,
    app: AppHandle,
    state: State<'_, ControlRoomState>,
) -> Result<ServiceStatus, String> {
    ensure_config(&state).await?;
    state
        .process_manager()
        .service_status(&app, &service_id)
        .await
}

#[tauri::command]
pub async fn controlroom_service_status_all(
    app: AppHandle,
    state: State<'_, ControlRoomState>,
) -> Result<Vec<ServiceStatus>, String> {
    ensure_config(&state).await?;
    state.process_manager().service_status_all(&app).await
}

#[tauri::command]
pub async fn controlroom_service_clear_logs(
    service_id: String,
    state: State<'_, ControlRoomState>,
) -> Result<bool, String> {
    ensure_config(&state).await?;
    state.process_manager().clear_logs(&service_id).await
}

#[tauri::command]
pub async fn controlroom_service_logs(
    service_id: String,
    limit: Option<u32>,
    state: State<'_, ControlRoomState>,
) -> Result<Vec<ServiceLogEvent>, String> {
    ensure_config(&state).await?;
    state
        .process_manager()
        .service_logs(&service_id, limit.map(|value| value as usize))
        .await
}

#[tauri::command]
pub async fn controlroom_runner_execute(
    input: RunnerCommandInput,
    app: AppHandle,
    state: State<'_, ControlRoomState>,
) -> Result<RunnerStartResponse, String> {
    let config = ensure_config(&state).await?;
    state
        .runner_manager()
        .execute(&app, &input, &config)
        .await
}

#[tauri::command]
pub async fn controlroom_runner_cancel(
    run_id: String,
    state: State<'_, ControlRoomState>,
) -> Result<bool, String> {
    ensure_config(&state).await?;
    state.runner_manager().cancel(&run_id).await
}

#[tauri::command]
pub async fn controlroom_workspace_list(
    workspace_id: String,
    relative_path: Option<String>,
    state: State<'_, ControlRoomState>,
) -> Result<Vec<WorkspaceEntry>, String> {
    let config = ensure_config(&state).await?;
    list_workspace_entries(&config, &workspace_id, relative_path.as_deref().unwrap_or(""))
}

#[tauri::command]
pub async fn controlroom_workspace_read_file(
    workspace_id: String,
    relative_path: String,
    state: State<'_, ControlRoomState>,
) -> Result<String, String> {
    let config = ensure_config(&state).await?;
    read_workspace_file(&config, &workspace_id, &relative_path, 512 * 1024)
}

#[tauri::command]
pub async fn controlroom_workspace_write_file(
    workspace_id: String,
    relative_path: String,
    content: String,
    state: State<'_, ControlRoomState>,
) -> Result<bool, String> {
    let config = ensure_config(&state).await?;
    write_workspace_file(&config, &workspace_id, &relative_path, &content, 2 * 1024 * 1024)
}

#[tauri::command]
pub async fn controlroom_git_commits(
    workspace_id: String,
    limit: Option<u32>,
    skip: Option<u32>,
    state: State<'_, ControlRoomState>,
) -> Result<Vec<GitCommit>, String> {
    let config = ensure_config(&state).await?;
    get_commits(
        &config,
        &workspace_id,
        limit.unwrap_or(config.git.max_commits),
        skip.unwrap_or(0),
    )
    .await
}

#[tauri::command]
pub async fn controlroom_export_logs(
    service_id: String,
    target_path: String,
    state: State<'_, ControlRoomState>,
) -> Result<bool, String> {
    ensure_config(&state).await?;
    state
        .process_manager()
        .export_logs(&service_id, &target_path)
        .await
}

#[tauri::command]
pub async fn controlroom_video_launch_native(
    input: VideoLaunchNativeInput,
    app: AppHandle,
    state: State<'_, ControlRoomState>,
) -> Result<VideoLaunchNativeResult, String> {
    let config = ensure_config(&state).await?;
    state
        .video_manager()
        .launch_native(&app, &input, &config)
        .await
}

#[tauri::command]
pub async fn controlroom_video_snapshot_analyze(
    input: VideoSnapshotAnalyzeInput,
    app: AppHandle,
    state: State<'_, ControlRoomState>,
) -> Result<VideoSnapshotAnalyzeResult, String> {
    let config = ensure_config(&state).await?;
    state
        .video_manager()
        .snapshot_analyze(&app, &input, &config)
        .await
}
