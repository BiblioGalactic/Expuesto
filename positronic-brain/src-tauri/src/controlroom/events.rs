use crate::controlroom::types::{
    ControlRoomBackendError, RunnerExitEvent, RunnerOutputEvent, ServiceLogEvent, ServiceStatus,
    VideoEventPayload,
};
use tauri::{AppHandle, Emitter};

pub fn emit_service_log(app: &AppHandle, event: &ServiceLogEvent) {
    let _ = app.emit("controlroom://service-log", event);
}

pub fn emit_service_state(app: &AppHandle, event: &ServiceStatus) {
    let _ = app.emit("controlroom://service-state", event);
}

pub fn emit_runner_output(app: &AppHandle, event: &RunnerOutputEvent) {
    let _ = app.emit("controlroom://runner-output", event);
}

pub fn emit_runner_exit(app: &AppHandle, event: &RunnerExitEvent) {
    let _ = app.emit("controlroom://runner-exit", event);
}

pub fn emit_video_event(app: &AppHandle, event: &VideoEventPayload) {
    let _ = app.emit("controlroom://video-event", event);
}

pub fn emit_backend_error(app: &AppHandle, scope: &str, message: impl ToString) {
    let payload = ControlRoomBackendError {
        scope: scope.to_string(),
        message: message.to_string(),
        correlation_id: None,
    };
    let _ = app.emit("controlroom://backend-error", payload);
}
