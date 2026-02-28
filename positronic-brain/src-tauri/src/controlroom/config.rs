use crate::controlroom::types::ControlRoomConfig;
use std::path::PathBuf;

fn resolve_config_path() -> Result<PathBuf, String> {
    if let Ok(path) = std::env::var("CONTROLROOM_CONFIG_PATH") {
        return Ok(PathBuf::from(path));
    }

    let cwd = std::env::current_dir().map_err(|e| format!("failed to read cwd: {e}"))?;
    let mut candidates = vec![cwd.join("controlroom.config.json")];
    if let Some(parent) = cwd.parent() {
        candidates.push(parent.join("controlroom.config.json"));
    }

    if let Some(found) = candidates.iter().find(|path| path.is_file()) {
        return Ok(found.clone());
    }

    let looked_up = candidates
        .iter()
        .map(|path| path.display().to_string())
        .collect::<Vec<_>>()
        .join(", ");

    Err(format!(
        "controlroom.config.json not found. Looked in: {looked_up}. You can also set CONTROLROOM_CONFIG_PATH."
    ))
}

pub fn load_controlroom_config() -> Result<ControlRoomConfig, String> {
    let path = resolve_config_path()?;
    let raw = std::fs::read_to_string(&path)
        .map_err(|e| format!("failed reading {}: {e}", path.display()))?;

    let config: ControlRoomConfig =
        serde_json::from_str(&raw).map_err(|e| format!("invalid controlroom config JSON: {e}"))?;

    Ok(config)
}
