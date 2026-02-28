use crate::controlroom::events::{emit_backend_error, emit_runner_exit, emit_runner_output};
use crate::controlroom::types::{
    ControlRoomConfig, RunnerCommandInput, RunnerExitEvent, RunnerOutputEvent, RunnerStartResponse,
};
use std::collections::HashMap;
use std::path::PathBuf;
use std::process::Stdio;
use std::sync::Arc;
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use tauri::AppHandle;
use tokio::io::{AsyncBufReadExt, AsyncRead, BufReader};
use tokio::process::{Child, Command};
use tokio::sync::Mutex;

#[derive(Debug)]
struct RunnerRuntime {
    child: Arc<Mutex<Child>>,
}

#[derive(Debug)]
pub struct RunnerManager {
    runs: Mutex<HashMap<String, RunnerRuntime>>,
    seq: AtomicU64,
}

impl RunnerManager {
    pub fn new() -> Self {
        Self {
            runs: Mutex::new(HashMap::new()),
            seq: AtomicU64::new(1),
        }
    }

    fn now_ms() -> u64 {
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|duration| duration.as_millis() as u64)
            .unwrap_or(0)
    }

    fn next_run_id(&self) -> String {
        let seq = self.seq.fetch_add(1, Ordering::SeqCst);
        format!("run-{}-{seq}", Self::now_ms())
    }

    fn resolve_workspace_cwd(config: &ControlRoomConfig, workspace_id: Option<&str>) -> Option<PathBuf> {
        workspace_id.and_then(|id| {
            config
                .workspaces
                .iter()
                .find(|workspace| workspace.id == id)
                .map(|workspace| PathBuf::from(&workspace.path))
        })
    }

    fn spawn_output_reader<R>(app: AppHandle, run_id: String, stream: &'static str, reader: R)
    where
        R: AsyncRead + Unpin + Send + 'static,
    {
        tokio::spawn(async move {
            let mut lines = BufReader::new(reader).lines();
            while let Ok(Some(line)) = lines.next_line().await {
                let payload = RunnerOutputEvent {
                    run_id: run_id.clone(),
                    stream: stream.to_string(),
                    ts: Self::now_ms(),
                    line,
                    correlation_id: Some(run_id.clone()),
                };
                emit_runner_output(&app, &payload);
            }
        });
    }

    fn spawn_exit_watcher(self: &Arc<Self>, app: AppHandle, run_id: String, child: Arc<Mutex<Child>>) {
        let manager = self.clone();
        tokio::spawn(async move {
            loop {
                tokio::time::sleep(Duration::from_millis(500)).await;
                let exit = {
                    let mut guard = child.lock().await;
                    match guard.try_wait() {
                        Ok(status) => status,
                        Err(error) => {
                            emit_backend_error(&app, "runner-watcher", error.to_string());
                            None
                        }
                    }
                };

                if let Some(status) = exit {
                    {
                        let mut runs = manager.runs.lock().await;
                        runs.remove(&run_id);
                    }

                    let event = RunnerExitEvent {
                        run_id: run_id.clone(),
                        code: status.code(),
                        signal: None,
                        correlation_id: Some(run_id.clone()),
                    };
                    emit_runner_exit(&app, &event);
                    break;
                }
            }
        });
    }

    pub async fn execute(
        self: &Arc<Self>,
        app: &AppHandle,
        input: &RunnerCommandInput,
        config: &ControlRoomConfig,
    ) -> Result<RunnerStartResponse, String> {
        if input.program.trim().is_empty() {
            return Err("runner program cannot be empty".to_string());
        }

        let run_id = self.next_run_id();

        let mut command = Command::new(&input.program);
        command.args(&input.args);
        command.stdin(Stdio::null());
        command.stdout(Stdio::piped());
        command.stderr(Stdio::piped());

        if let Some(cwd) = Self::resolve_workspace_cwd(config, input.workspace_id.as_deref()) {
            command.current_dir(cwd);
        }

        let mut child = command
            .spawn()
            .map_err(|e| format!("runner spawn failed: {e}"))?;

        let stdout = child.stdout.take();
        let stderr = child.stderr.take();
        let child = Arc::new(Mutex::new(child));

        {
            let mut runs = self.runs.lock().await;
            runs.insert(run_id.clone(), RunnerRuntime { child: child.clone() });
        }

        if let Some(stdout) = stdout {
            Self::spawn_output_reader(app.clone(), run_id.clone(), "stdout", stdout);
        }
        if let Some(stderr) = stderr {
            Self::spawn_output_reader(app.clone(), run_id.clone(), "stderr", stderr);
        }

        self.spawn_exit_watcher(app.clone(), run_id.clone(), child);

        Ok(RunnerStartResponse { run_id })
    }

    pub async fn cancel(&self, run_id: &str) -> Result<bool, String> {
        let child = {
            let runs = self.runs.lock().await;
            runs.get(run_id).map(|runtime| runtime.child.clone())
        };

        if let Some(child) = child {
            let mut guard = child.lock().await;
            let _ = guard.start_kill();
            let _ = tokio::time::timeout(Duration::from_secs(3), guard.wait()).await;
            Ok(true)
        } else {
            Ok(false)
        }
    }
}
