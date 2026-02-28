pub mod config;
pub mod events;
pub mod git_provider;
pub mod process_manager;
pub mod runner_manager;
pub mod types;
pub mod video_manager;
pub mod workspace;

use crate::controlroom::config::load_controlroom_config;
use crate::controlroom::process_manager::ControlRoomProcessManager;
use crate::controlroom::runner_manager::RunnerManager;
use crate::controlroom::types::ControlRoomConfig;
use crate::controlroom::video_manager::VideoManager;
use std::sync::Arc;
use tokio::sync::RwLock;

#[derive(Debug)]
pub struct ControlRoomState {
    config: Arc<RwLock<ControlRoomConfig>>,
    process_manager: Arc<ControlRoomProcessManager>,
    runner_manager: Arc<RunnerManager>,
    video_manager: Arc<VideoManager>,
}

impl ControlRoomState {
    pub fn new() -> Self {
        Self {
            config: Arc::new(RwLock::new(ControlRoomConfig::default())),
            process_manager: Arc::new(ControlRoomProcessManager::new(5000)),
            runner_manager: Arc::new(RunnerManager::new()),
            video_manager: Arc::new(VideoManager::new()),
        }
    }

    pub async fn load_config(&self) -> Result<ControlRoomConfig, String> {
        let config = load_controlroom_config()?;
        self.process_manager.set_services(config.services.clone()).await;
        {
            let mut guard = self.config.write().await;
            *guard = config.clone();
        }
        Ok(config)
    }

    pub async fn get_config(&self) -> ControlRoomConfig {
        self.config.read().await.clone()
    }

    pub fn process_manager(&self) -> Arc<ControlRoomProcessManager> {
        self.process_manager.clone()
    }

    pub fn runner_manager(&self) -> Arc<RunnerManager> {
        self.runner_manager.clone()
    }

    pub fn video_manager(&self) -> Arc<VideoManager> {
        self.video_manager.clone()
    }
}
