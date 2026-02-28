use crate::controlroom::events::emit_video_event;
use crate::controlroom::types::{
    ControlRoomConfig, SafeCommandSpec, VideoEventPayload, VideoLaunchNativeInput,
    VideoLaunchNativeResult, VideoNativeLauncherConfig, VideoSnapshotAnalyzeInput,
    VideoSnapshotAnalyzeResult,
};
use base64::Engine;
use base64::engine::general_purpose::STANDARD;
use std::process::Stdio;
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use tauri::AppHandle;
use tokio::process::Command;

#[derive(Debug)]
pub struct VideoManager;

impl VideoManager {
    pub fn new() -> Self {
        Self
    }

    fn now_ms() -> u64 {
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|duration| duration.as_millis() as u64)
            .unwrap_or(0)
    }

    fn redact_url(url: &str) -> String {
        if url.is_empty() {
            return String::new();
        }

        if let Ok(mut parsed) = url::Url::parse(url) {
            if !parsed.username().is_empty() || parsed.password().is_some() {
                let _ = parsed.set_username("***");
                let _ = parsed.set_password(Some("***"));
            }
            return parsed.to_string();
        }

        url.replace("://", "://***:***@")
    }

    fn substitute_template(value: &str, vars: &[(&str, String)]) -> String {
        vars.iter().fold(value.to_string(), |acc, (key, replacement)| {
            acc.replace(&format!("{{{key}}}"), replacement)
        })
    }

    fn build_command(
        spec: &SafeCommandSpec,
        vars: &[(&str, String)],
    ) -> Result<Command, String> {
        if spec.program.trim().is_empty() {
            return Err("video command program cannot be empty".to_string());
        }

        let program = Self::substitute_template(&spec.program, vars);
        let mut command = Command::new(program);

        let args = spec
            .args
            .iter()
            .map(|value| Self::substitute_template(value, vars))
            .collect::<Vec<_>>();
        command.args(args);

        if let Some(cwd) = &spec.cwd {
            let resolved = Self::substitute_template(cwd, vars);
            command.current_dir(resolved);
        }

        if let Some(envs) = &spec.env {
            envs.iter().for_each(|(key, value)| {
                let resolved = Self::substitute_template(value, vars);
                command.env(key, resolved);
            });
        }

        Ok(command)
    }

    fn get_launchers(config: &ControlRoomConfig) -> Vec<VideoNativeLauncherConfig> {
        config
            .video_wall
            .as_ref()
            .and_then(|video| video.native_launchers.clone())
            .unwrap_or_default()
    }

    fn strip_data_url_prefix(input: &str) -> &str {
        if let Some((_, payload)) = input.split_once(",") {
            payload
        } else {
            input
        }
    }

    fn sanitize_name(input: &str) -> String {
        let filtered = input
            .chars()
            .map(|ch| {
                if ch.is_ascii_alphanumeric() || ch == '-' || ch == '_' {
                    ch
                } else {
                    '_'
                }
            })
            .collect::<String>();
        if filtered.is_empty() {
            "feed".to_string()
        } else {
            filtered
        }
    }

    pub async fn launch_native(
        &self,
        app: &AppHandle,
        input: &VideoLaunchNativeInput,
        config: &ControlRoomConfig,
    ) -> Result<VideoLaunchNativeResult, String> {
        let launchers = Self::get_launchers(config);
        let launcher = launchers
            .into_iter()
            .find(|entry| entry.id == input.launcher_id)
            .ok_or_else(|| format!("video launcher not allowed: {}", input.launcher_id))?;

        let feed_name = input
            .feed_name
            .clone()
            .unwrap_or_else(|| "feed".to_string());
        let feed_id = input.feed_id.clone().unwrap_or_else(|| "feed".to_string());
        let feed_url = input.feed_url.clone().unwrap_or_default();
        let feed_url_redacted = Self::redact_url(&feed_url);

        let vars = vec![
            ("feedName", feed_name.clone()),
            ("feedId", feed_id.clone()),
            ("feedUrl", feed_url),
            ("feedUrlRedacted", feed_url_redacted),
        ];

        let mut command = Self::build_command(&launcher.command, &vars)?;
        command.stdin(Stdio::null());
        command.stdout(Stdio::null());
        command.stderr(Stdio::null());

        command
            .spawn()
            .map_err(|error| format!("native launch failed: {error}"))?;

        emit_video_event(
            app,
            &VideoEventPayload {
                ts: Self::now_ms(),
                severity: "info".to_string(),
                source: "video-native".to_string(),
                message: format!("native launcher '{}' started", launcher.name),
                feed_id: input.feed_id.clone(),
                kind: Some("native-launch".to_string()),
                details: None,
                correlation_id: Some(format!("video-native:{feed_id}")),
            },
        );

        Ok(VideoLaunchNativeResult {
            ok: true,
            message: format!("Native launch started: {}", launcher.name),
        })
    }

    pub async fn snapshot_analyze(
        &self,
        app: &AppHandle,
        input: &VideoSnapshotAnalyzeInput,
        config: &ControlRoomConfig,
    ) -> Result<VideoSnapshotAnalyzeResult, String> {
        let video_config = config
            .video_wall
            .as_ref()
            .ok_or_else(|| "videoWall config missing".to_string())?;
        let snapshot = video_config
            .snapshot
            .as_ref()
            .ok_or_else(|| "videoWall.snapshot config missing".to_string())?;

        if !snapshot.enabled.unwrap_or(false) {
            return Ok(VideoSnapshotAnalyzeResult {
                ok: false,
                summary: String::new(),
                message: Some("Snapshot analyzer disabled".to_string()),
            });
        }

        let analyzer_command = snapshot
            .analyzer_command
            .as_ref()
            .ok_or_else(|| "videoWall.snapshot.analyzerCommand missing".to_string())?;

        let payload = Self::strip_data_url_prefix(&input.image_base64);
        let image_bytes = STANDARD
            .decode(payload)
            .map_err(|error| format!("invalid snapshot base64: {error}"))?;

        if image_bytes.is_empty() {
            return Err("snapshot image payload is empty".to_string());
        }

        if image_bytes.len() > 16 * 1024 * 1024 {
            return Err("snapshot image exceeds 16MB limit".to_string());
        }

        let feed_id = input
            .feed_id
            .clone()
            .unwrap_or_else(|| "feed".to_string());
        let feed_name = input
            .feed_name
            .clone()
            .unwrap_or_else(|| "feed".to_string());
        let safe_name = Self::sanitize_name(&feed_id);

        let snapshot_path = std::env::temp_dir().join(format!(
            "controlroom-video-snapshot-{}-{}.png",
            Self::now_ms(),
            safe_name
        ));

        tokio::fs::write(&snapshot_path, image_bytes)
            .await
            .map_err(|error| format!("failed writing snapshot temp file: {error}"))?;

        let vars = vec![
            ("snapshotPath", snapshot_path.to_string_lossy().to_string()),
            ("feedName", feed_name),
            ("feedId", feed_id),
        ];

        let timeout_ms = snapshot.timeout_ms.unwrap_or(20_000).max(2_000);
        let mut command = Self::build_command(analyzer_command, &vars)?;
        command.stdin(Stdio::null());
        command.stdout(Stdio::piped());
        command.stderr(Stdio::piped());
        command.kill_on_drop(true);

        let output = tokio::time::timeout(Duration::from_millis(timeout_ms), command.output()).await;

        let output = match output {
            Ok(Ok(value)) => value,
            Ok(Err(error)) => {
                let _ = tokio::fs::remove_file(&snapshot_path).await;
                return Err(format!("snapshot analyzer spawn failed: {error}"));
            }
            Err(_) => {
                let _ = tokio::fs::remove_file(&snapshot_path).await;
                let timeout_message = format!("snapshot analyzer timeout after {timeout_ms}ms");

                emit_video_event(
                    app,
                    &VideoEventPayload {
                        ts: Self::now_ms(),
                        severity: "error".to_string(),
                        source: "video-snapshot".to_string(),
                        message: timeout_message.clone(),
                        feed_id: input.feed_id.clone(),
                        kind: Some("snapshot".to_string()),
                        details: None,
                        correlation_id: Some(format!(
                            "video-snapshot:{}",
                            input.feed_id.as_deref().unwrap_or("feed")
                        )),
                    },
                );

                return Ok(VideoSnapshotAnalyzeResult {
                    ok: false,
                    summary: String::new(),
                    message: Some(timeout_message),
                });
            }
        };

        let _ = tokio::fs::remove_file(&snapshot_path).await;

        let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
        let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
        let mut summary = if !stdout.is_empty() {
            stdout
        } else if !stderr.is_empty() {
            stderr
        } else {
            format!("snapshot analyzer exited with code {:?}", output.status.code())
        };

        if summary.len() > 2000 {
            summary = summary.chars().take(2000).collect::<String>();
        }

        if output.status.success() {
            emit_video_event(
                app,
                &VideoEventPayload {
                    ts: Self::now_ms(),
                    severity: "info".to_string(),
                    source: "video-snapshot".to_string(),
                    message: summary.clone(),
                    feed_id: input.feed_id.clone(),
                    kind: Some("snapshot".to_string()),
                    details: None,
                    correlation_id: Some(format!(
                        "video-snapshot:{}",
                        input.feed_id.as_deref().unwrap_or("feed")
                    )),
                },
            );

            Ok(VideoSnapshotAnalyzeResult {
                ok: true,
                summary,
                message: None,
            })
        } else {
            let error_message = format!(
                "snapshot analyzer failed with code {:?}: {}",
                output.status.code(),
                summary
            );

            emit_video_event(
                app,
                &VideoEventPayload {
                    ts: Self::now_ms(),
                    severity: "error".to_string(),
                    source: "video-snapshot".to_string(),
                    message: error_message.clone(),
                    feed_id: input.feed_id.clone(),
                    kind: Some("snapshot".to_string()),
                    details: None,
                    correlation_id: Some(format!(
                        "video-snapshot:{}",
                        input.feed_id.as_deref().unwrap_or("feed")
                    )),
                },
            );

            Ok(VideoSnapshotAnalyzeResult {
                ok: false,
                summary: String::new(),
                message: Some(error_message),
            })
        }
    }
}
