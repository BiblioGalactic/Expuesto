use crate::controlroom::events::{emit_backend_error, emit_service_log, emit_service_state};
use crate::controlroom::types::{
    SafeCommandSpec, ServiceConfig, ServiceLogEvent, ServiceState, ServiceStatus,
};
use std::collections::{HashMap, VecDeque};
use std::path::PathBuf;
use std::process::Stdio;
use std::sync::Arc;
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use tauri::AppHandle;
use tokio::io::{AsyncBufReadExt, AsyncRead, BufReader};
use tokio::process::{Child, Command};
use tokio::sync::{Mutex, RwLock};

#[derive(Debug)]
struct ServiceRuntime {
    status: ServiceStatus,
    child: Option<Arc<Mutex<Child>>>,
    started_at: Option<SystemTime>,
    logs: VecDeque<ServiceLogEvent>,
}

impl ServiceRuntime {
    fn new(service_id: &str) -> Self {
        Self {
            status: ServiceStatus::stopped(service_id),
            child: None,
            started_at: None,
            logs: VecDeque::new(),
        }
    }
}

#[derive(Debug)]
pub struct ControlRoomProcessManager {
    services: RwLock<HashMap<String, ServiceConfig>>,
    runtimes: Mutex<HashMap<String, ServiceRuntime>>,
    max_logs_per_service: usize,
}

impl ControlRoomProcessManager {
    pub fn new(max_logs_per_service: usize) -> Self {
        Self {
            services: RwLock::new(HashMap::new()),
            runtimes: Mutex::new(HashMap::new()),
            max_logs_per_service,
        }
    }

    pub async fn set_services(&self, services: Vec<ServiceConfig>) {
        let mut service_map = HashMap::new();
        for service in services {
            service_map.insert(service.id.clone(), service);
        }

        {
            let mut guard = self.services.write().await;
            *guard = service_map.clone();
        }

        let mut runtimes = self.runtimes.lock().await;
        runtimes.retain(|service_id, _| service_map.contains_key(service_id));
        for service_id in service_map.keys() {
            runtimes
                .entry(service_id.clone())
                .or_insert_with(|| ServiceRuntime::new(service_id));
        }
    }

    pub async fn get_services(&self) -> Vec<ServiceConfig> {
        let guard = self.services.read().await;
        let mut values = guard.values().cloned().collect::<Vec<_>>();
        values.sort_by(|a, b| a.name.to_lowercase().cmp(&b.name.to_lowercase()));
        values
    }

    async fn get_service(&self, service_id: &str) -> Result<ServiceConfig, String> {
        let guard = self.services.read().await;
        guard
            .get(service_id)
            .cloned()
            .ok_or_else(|| format!("service not found: {service_id}"))
    }

    fn now_ms() -> u64 {
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|duration| duration.as_millis() as u64)
            .unwrap_or(0)
    }

    fn parse_embedded_level(lower: &str) -> Option<&'static str> {
        if lower.contains("] error ")
            || lower.starts_with("error ")
            || lower.starts_with("error:")
        {
            Some("error")
        } else if lower.contains("] warn ")
            || lower.contains("] warning ")
            || lower.starts_with("warn ")
            || lower.starts_with("warn:")
            || lower.starts_with("warning ")
            || lower.starts_with("warning:")
        {
            Some("warn")
        } else if lower.contains("] info ")
            || lower.starts_with("info ")
            || lower.starts_with("info:")
        {
            Some("info")
        } else {
            None
        }
    }

    fn looks_like_error(lower: &str) -> bool {
        lower.starts_with("error:")
            || lower.contains(" error:")
            || lower.contains("fatal:")
            || lower.contains("panic")
            || lower.contains("traceback")
            || lower.contains("uncaught exception")
            || lower.contains("exception:")
            || lower.contains("errored out")
            || lower.contains("failed to")
            || lower.contains("spawn failed")
            || lower.contains("connection refused")
            || lower.contains("no such file or directory")
            || lower.contains("permission denied")
            || lower.contains("segmentation fault")
            || lower.contains("out of memory")
            || lower.contains("timed out")
            || lower.contains(" econnrefused")
            || lower.contains(" enoent")
            || lower.contains(" eacces")
    }

    fn looks_like_warning(lower: &str) -> bool {
        lower.starts_with("warn:")
            || lower.starts_with("warning:")
            || lower.contains(" warning ")
            || lower.contains(" deprecated")
    }

    fn is_known_informational_stderr(lower: &str) -> bool {
        let prefixes = [
            "ggml_",
            "main:",
            "srv ",
            "slot ",
            "llama_",
            "load_tensors:",
            "print_info:",
            "system info:",
            "system_info:",
            "common_init_from_params:",
            "load:",
            "build:",
            "prompt eval time",
            "eval time",
            "total time",
        ];

        prefixes.iter().any(|prefix| lower.starts_with(prefix))
            || lower.contains("http server is listening")
            || lower.contains("model loaded")
            || lower.contains("all slots are idle")
    }

    fn detect_level(line: &str, stream: &str) -> String {
        let lower = line.trim().to_lowercase();
        if lower.is_empty() {
            return "info".to_string();
        }

        if let Some(level) = Self::parse_embedded_level(&lower) {
            return level.to_string();
        }

        if Self::looks_like_error(&lower) {
            return "error".to_string();
        }

        if Self::looks_like_warning(&lower) {
            return "warn".to_string();
        }

        if stream == "stderr" {
            if Self::is_known_informational_stderr(&lower) {
                return "info".to_string();
            }
            return "warn".to_string();
        }

        "info".to_string()
    }

    fn resolve_cwd(service_cwd: Option<&str>, cmd_cwd: Option<&str>) -> Option<PathBuf> {
        if let Some(cwd) = cmd_cwd {
            return Some(PathBuf::from(cwd));
        }
        service_cwd.map(PathBuf::from)
    }

    fn build_command(spec: &SafeCommandSpec, service_cwd: Option<&str>) -> Result<Command, String> {
        if spec.program.trim().is_empty() {
            return Err("command program cannot be empty".to_string());
        }

        let mut command = Command::new(&spec.program);
        command.args(&spec.args);
        command.stdin(Stdio::null());
        command.stdout(Stdio::piped());
        command.stderr(Stdio::piped());

        if let Some(cwd) = Self::resolve_cwd(service_cwd, spec.cwd.as_deref()) {
            command.current_dir(cwd);
        }

        if let Some(envs) = &spec.env {
            command.envs(envs);
        }

        Ok(command)
    }

    async fn run_oneshot_command(spec: &SafeCommandSpec, service_cwd: Option<&str>) -> Result<(), String> {
        let mut command = Self::build_command(spec, service_cwd)?;
        let output = command
            .output()
            .await
            .map_err(|e| format!("oneshot command spawn failed: {e}"))?;

        if output.status.success() {
            Ok(())
        } else {
            let stderr = String::from_utf8_lossy(&output.stderr).to_string();
            Err(format!(
                "oneshot command failed (code {:?}): {}",
                output.status.code(),
                stderr
            ))
        }
    }

    async fn append_log(&self, event: ServiceLogEvent) {
        let mut runtimes = self.runtimes.lock().await;
        if let Some(runtime) = runtimes.get_mut(&event.service_id) {
            runtime.logs.push_back(event);
            while runtime.logs.len() > self.max_logs_per_service {
                runtime.logs.pop_front();
            }
        }
    }

    async fn mark_status(&self, app: &AppHandle, status: ServiceStatus) {
        {
            let mut runtimes = self.runtimes.lock().await;
            let runtime = runtimes
                .entry(status.service_id.clone())
                .or_insert_with(|| ServiceRuntime::new(&status.service_id));
            runtime.status = status.clone();
            if runtime.status.state != ServiceState::Running {
                runtime.started_at = None;
                runtime.status.uptime_sec = None;
            }
        }
        emit_service_state(app, &status);
    }

    fn spawn_log_reader<R>(
        self: &Arc<Self>,
        app: AppHandle,
        service_id: String,
        stream: &'static str,
        reader: R,
    ) where
        R: AsyncRead + Unpin + Send + 'static,
    {
        let manager = self.clone();
        tokio::spawn(async move {
            let correlation_id = format!("service:{service_id}");
            let mut lines = BufReader::new(reader).lines();
            while let Ok(Some(line)) = lines.next_line().await {
                let event = ServiceLogEvent {
                    service_id: service_id.clone(),
                    stream: stream.to_string(),
                    ts: Self::now_ms(),
                    level: Self::detect_level(&line, stream),
                    line,
                    correlation_id: Some(correlation_id.clone()),
                };

                manager.append_log(event.clone()).await;
                emit_service_log(&app, &event);
            }
        });
    }

    fn spawn_exit_watcher(self: &Arc<Self>, app: AppHandle, service_id: String, child: Arc<Mutex<Child>>) {
        let manager = self.clone();
        tokio::spawn(async move {
            let correlation_id = format!("service:{service_id}");
            loop {
                tokio::time::sleep(Duration::from_millis(700)).await;
                let exit = {
                    let mut guard = child.lock().await;
                    match guard.try_wait() {
                        Ok(status) => status,
                        Err(error) => {
                            emit_backend_error(&app, "service-watcher", error.to_string());
                            None
                        }
                    }
                };

                if let Some(exit_status) = exit {
                    let next = ServiceStatus {
                        service_id: service_id.clone(),
                        state: if exit_status.success() {
                            ServiceState::Stopped
                        } else {
                            ServiceState::Error
                        },
                        pid: None,
                        uptime_sec: None,
                        last_error: if exit_status.success() {
                            None
                        } else {
                            Some(format!("process exited with code {:?}", exit_status.code()))
                        },
                        correlation_id: Some(correlation_id.clone()),
                    };

                    {
                        let mut runtimes = manager.runtimes.lock().await;
                        if let Some(runtime) = runtimes.get_mut(&service_id) {
                            runtime.child = None;
                            runtime.started_at = None;
                            runtime.status = next.clone();
                        }
                    }

                    emit_service_state(&app, &next);
                    break;
                }
            }
        });
    }

    async fn refresh_status_if_needed(&self, service_id: &str) -> Option<ServiceStatus> {
        let mut runtimes = self.runtimes.lock().await;
        let runtime = runtimes.get_mut(service_id)?;

        let child = runtime.child.clone();

        if let Some(child) = child {
            let wait_result = {
                let mut guard = child.lock().await;
                guard.try_wait()
            };

            match wait_result {
                Ok(Some(exit)) => {
                    runtime.child = None;
                    runtime.started_at = None;
                    runtime.status.state = if exit.success() {
                        ServiceState::Stopped
                    } else {
                        ServiceState::Error
                    };
                    runtime.status.pid = None;
                    runtime.status.uptime_sec = None;
                    runtime.status.last_error = if exit.success() {
                        None
                    } else {
                        Some(format!("process exited with code {:?}", exit.code()))
                    };
                }
                Ok(None) => {
                    runtime.status.state = ServiceState::Running;
                    if let Some(started) = runtime.started_at {
                        runtime.status.uptime_sec = started.elapsed().ok().map(|d| d.as_secs());
                    }
                }
                Err(error) => {
                    runtime.status.state = ServiceState::Error;
                    runtime.status.last_error = Some(error.to_string());
                }
            }
        }

        Some(runtime.status.clone())
    }

    pub async fn start_service(self: &Arc<Self>, app: &AppHandle, service_id: &str) -> Result<ServiceStatus, String> {
        let service = self.get_service(service_id).await?;

        if let Some(status) = self.refresh_status_if_needed(service_id).await {
            if status.state == ServiceState::Running {
                return Ok(status);
            }
        }

        self.mark_status(
            app,
            ServiceStatus {
                service_id: service_id.to_string(),
                state: ServiceState::Starting,
                pid: None,
                uptime_sec: None,
                last_error: None,
                correlation_id: Some(format!("service:{service_id}")),
            },
        )
        .await;

        let mut command = Self::build_command(&service.start, service.cwd.as_deref())?;
        let mut child = command
            .spawn()
            .map_err(|e| format!("failed to spawn service {}: {e}", service.name))?;

        let pid = child.id();
        let stdout = child.stdout.take();
        let stderr = child.stderr.take();
        let child = Arc::new(Mutex::new(child));

        {
            let mut runtimes = self.runtimes.lock().await;
            let runtime = runtimes
                .entry(service_id.to_string())
                .or_insert_with(|| ServiceRuntime::new(service_id));
            runtime.child = Some(child.clone());
            runtime.started_at = Some(SystemTime::now());
            runtime.status = ServiceStatus {
                service_id: service_id.to_string(),
                state: ServiceState::Running,
                pid,
                uptime_sec: Some(0),
                last_error: None,
                correlation_id: Some(format!("service:{service_id}")),
            };
        }

        if let Some(stdout) = stdout {
            self.spawn_log_reader(app.clone(), service_id.to_string(), "stdout", stdout);
        }
        if let Some(stderr) = stderr {
            self.spawn_log_reader(app.clone(), service_id.to_string(), "stderr", stderr);
        }

        self.spawn_exit_watcher(app.clone(), service_id.to_string(), child);

        let status = ServiceStatus {
            service_id: service_id.to_string(),
            state: ServiceState::Running,
            pid,
            uptime_sec: Some(0),
            last_error: None,
            correlation_id: Some(format!("service:{service_id}")),
        };
        emit_service_state(app, &status);
        Ok(status)
    }

    pub async fn stop_service(self: &Arc<Self>, app: &AppHandle, service_id: &str) -> Result<ServiceStatus, String> {
        let service = self.get_service(service_id).await?;

        self.mark_status(
            app,
            ServiceStatus {
                service_id: service_id.to_string(),
                state: ServiceState::Stopping,
                pid: None,
                uptime_sec: None,
                last_error: None,
                correlation_id: Some(format!("service:{service_id}")),
            },
        )
        .await;

        if let Some(stop_spec) = &service.stop {
            if let Err(error) = Self::run_oneshot_command(stop_spec, service.cwd.as_deref()).await {
                emit_backend_error(app, "service-stop-cmd", error);
            }
        }

        let child = {
            let mut runtimes = self.runtimes.lock().await;
            runtimes
                .get_mut(service_id)
                .and_then(|runtime| runtime.child.take())
        };

        if let Some(child) = child {
            let mut guard = child.lock().await;
            let _ = guard.start_kill();
            let _ = tokio::time::timeout(Duration::from_secs(4), guard.wait()).await;
        }

        let status = ServiceStatus {
            service_id: service_id.to_string(),
            state: ServiceState::Stopped,
            pid: None,
            uptime_sec: None,
            last_error: None,
            correlation_id: Some(format!("service:{service_id}")),
        };

        self.mark_status(app, status.clone()).await;
        Ok(status)
    }

    pub async fn restart_service(self: &Arc<Self>, app: &AppHandle, service_id: &str) -> Result<ServiceStatus, String> {
        let _ = self.stop_service(app, service_id).await;
        self.start_service(app, service_id).await
    }

    pub async fn service_status(self: &Arc<Self>, app: &AppHandle, service_id: &str) -> Result<ServiceStatus, String> {
        self.get_service(service_id).await?;
        if let Some(status) = self.refresh_status_if_needed(service_id).await {
            emit_service_state(app, &status);
            return Ok(status);
        }
        let status = ServiceStatus::stopped(service_id);
        emit_service_state(app, &status);
        Ok(status)
    }

    pub async fn service_status_all(self: &Arc<Self>, app: &AppHandle) -> Result<Vec<ServiceStatus>, String> {
        let services = self.get_services().await;
        let mut statuses = Vec::new();
        for service in services {
            statuses.push(self.service_status(app, &service.id).await?);
        }
        Ok(statuses)
    }

    pub async fn clear_logs(&self, service_id: &str) -> Result<bool, String> {
        let mut runtimes = self.runtimes.lock().await;
        let runtime = runtimes
            .get_mut(service_id)
            .ok_or_else(|| format!("service runtime not found: {service_id}"))?;
        runtime.logs.clear();
        Ok(true)
    }

    pub async fn service_logs(
        &self,
        service_id: &str,
        limit: Option<usize>,
    ) -> Result<Vec<ServiceLogEvent>, String> {
        let runtimes = self.runtimes.lock().await;
        let runtime = runtimes
            .get(service_id)
            .ok_or_else(|| format!("service runtime not found: {service_id}"))?;
        let max = limit.unwrap_or(self.max_logs_per_service).max(1);
        let len = runtime.logs.len();
        let start = len.saturating_sub(max);
        Ok(runtime.logs.iter().skip(start).cloned().collect())
    }

    pub async fn export_logs(&self, service_id: &str, target_path: &str) -> Result<bool, String> {
        let lines = {
            let runtimes = self.runtimes.lock().await;
            let runtime = runtimes
                .get(service_id)
                .ok_or_else(|| format!("service runtime not found: {service_id}"))?;
            runtime
                .logs
                .iter()
                .map(|entry| {
                    format!(
                        "[{}] {} {} {}",
                        entry.ts,
                        entry.stream,
                        entry.level.to_uppercase(),
                        entry.line
                    )
                })
                .collect::<Vec<_>>()
        };

        let target = PathBuf::from(target_path);
        let resolved = if target.is_absolute() {
            target
        } else {
            std::env::current_dir()
                .map_err(|e| format!("failed to read cwd: {e}"))?
                .join(target)
        };

        if let Some(parent) = resolved.parent() {
            tokio::fs::create_dir_all(parent)
                .await
                .map_err(|e| format!("failed to create export parent {}: {e}", parent.display()))?;
        }

        tokio::fs::write(&resolved, lines.join("\n"))
            .await
            .map_err(|e| format!("failed writing logs to {}: {e}", resolved.display()))?;

        Ok(true)
    }
}
