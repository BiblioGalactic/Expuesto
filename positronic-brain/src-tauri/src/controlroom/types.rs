use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SafeCommandSpec {
    pub program: String,
    pub args: Vec<String>,
    pub cwd: Option<String>,
    pub env: Option<HashMap<String, String>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ServiceHealthSpec {
    pub program: String,
    pub args: Vec<String>,
    pub interval_sec: Option<u64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ServiceConfig {
    pub id: String,
    pub name: String,
    pub tier: Option<String>,
    pub cwd: Option<String>,
    pub start: SafeCommandSpec,
    pub stop: Option<SafeCommandSpec>,
    pub restart: Option<SafeCommandSpec>,
    pub health: Option<ServiceHealthSpec>,
    pub log_sources: Option<Vec<String>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct WorkspaceConfig {
    pub id: String,
    pub name: String,
    pub path: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct FeatureFlags {
    pub control_room_enabled: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct UiShortcuts {
    pub command_palette: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct UiLayout {
    pub show_left_sidebar: bool,
    pub show_top_bar: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct UiConfig {
    pub default_view: String,
    pub remember_last_view: bool,
    pub shortcuts: UiShortcuts,
    pub layout: UiLayout,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct GitConfig {
    pub enabled: bool,
    pub max_commits: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct VideoAutoPauseConfig {
    pub when_mode_not_multimedia: Option<bool>,
    pub when_panel_hidden: Option<bool>,
    pub when_app_hidden: Option<bool>,
    pub when_high_load: Option<bool>,
    pub high_load_latency_ms: Option<u64>,
    pub high_load_consecutive_samples: Option<u32>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct VideoNativeLauncherConfig {
    pub id: String,
    pub name: String,
    pub command: SafeCommandSpec,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct VideoSnapshotConfig {
    pub enabled: Option<bool>,
    pub timeout_ms: Option<u64>,
    pub analyzer_command: Option<SafeCommandSpec>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct VideoWallConfig {
    pub enabled: Option<bool>,
    pub max_active_feeds: Option<u32>,
    pub auto_pause: Option<VideoAutoPauseConfig>,
    pub native_launchers: Option<Vec<VideoNativeLauncherConfig>>,
    pub snapshot: Option<VideoSnapshotConfig>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ControlRoomConfig {
    pub feature_flags: FeatureFlags,
    pub ui: UiConfig,
    pub services: Vec<ServiceConfig>,
    pub workspaces: Vec<WorkspaceConfig>,
    pub git: GitConfig,
    pub video_wall: Option<VideoWallConfig>,
}

impl Default for ControlRoomConfig {
    fn default() -> Self {
        Self {
            feature_flags: FeatureFlags {
                control_room_enabled: false,
            },
            ui: UiConfig {
                default_view: "classic".to_string(),
                remember_last_view: true,
                shortcuts: UiShortcuts {
                    command_palette: "Meta+K".to_string(),
                },
                layout: UiLayout {
                    show_left_sidebar: true,
                    show_top_bar: true,
                },
            },
            services: Vec::new(),
            workspaces: Vec::new(),
            git: GitConfig {
                enabled: true,
                max_commits: 30,
            },
            video_wall: None,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum ServiceState {
    Running,
    Stopped,
    Error,
    Starting,
    Stopping,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ServiceStatus {
    pub service_id: String,
    pub state: ServiceState,
    pub pid: Option<u32>,
    pub uptime_sec: Option<u64>,
    pub last_error: Option<String>,
    pub correlation_id: Option<String>,
}

impl ServiceStatus {
    pub fn stopped(service_id: &str) -> Self {
        Self {
            service_id: service_id.to_string(),
            state: ServiceState::Stopped,
            pid: None,
            uptime_sec: None,
            last_error: None,
            correlation_id: None,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ServiceLogEvent {
    pub service_id: String,
    pub stream: String,
    pub ts: u64,
    pub level: String,
    pub line: String,
    pub correlation_id: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RunnerCommandInput {
    pub workspace_id: Option<String>,
    pub program: String,
    pub args: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RunnerStartResponse {
    pub run_id: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RunnerOutputEvent {
    pub run_id: String,
    pub stream: String,
    pub ts: u64,
    pub line: String,
    pub correlation_id: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RunnerExitEvent {
    pub run_id: String,
    pub code: Option<i32>,
    pub signal: Option<String>,
    pub correlation_id: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct WorkspaceEntry {
    pub name: String,
    pub path: String,
    pub is_directory: bool,
    pub size: Option<u64>,
    pub modified_ms: Option<u64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct GitCommit {
    pub hash: String,
    pub short_hash: String,
    pub author: String,
    pub date: String,
    pub message: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ControlRoomBackendError {
    pub scope: String,
    pub message: String,
    pub correlation_id: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct VideoLaunchNativeInput {
    pub launcher_id: String,
    pub feed_id: Option<String>,
    pub feed_name: Option<String>,
    pub feed_url: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct VideoLaunchNativeResult {
    pub ok: bool,
    pub message: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct VideoSnapshotAnalyzeInput {
    pub feed_id: Option<String>,
    pub feed_name: Option<String>,
    pub image_base64: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct VideoSnapshotAnalyzeResult {
    pub ok: bool,
    pub summary: String,
    pub message: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct VideoEventPayload {
    pub ts: u64,
    pub severity: String,
    pub source: String,
    pub message: String,
    pub feed_id: Option<String>,
    pub kind: Option<String>,
    pub details: Option<String>,
    pub correlation_id: Option<String>,
}
