use crate::controlroom::types::{ControlRoomConfig, WorkspaceEntry};
use std::path::{Path, PathBuf};

fn now_modified_ms(meta: &std::fs::Metadata) -> Option<u64> {
    let modified = meta.modified().ok()?;
    let since_epoch = modified.duration_since(std::time::UNIX_EPOCH).ok()?;
    Some(since_epoch.as_millis() as u64)
}

fn secure_target_path(base: &Path, rel_or_abs: &str) -> Result<PathBuf, String> {
    let target = if rel_or_abs.trim().is_empty() {
        base.to_path_buf()
    } else {
        let candidate = PathBuf::from(rel_or_abs);
        if candidate.is_absolute() {
            candidate
        } else {
            base.join(candidate)
        }
    };

    let canonical_base = base
        .canonicalize()
        .map_err(|e| format!("workspace canonicalize failed: {e}"))?;
    let canonical_target = target
        .canonicalize()
        .map_err(|e| format!("target canonicalize failed: {e}"))?;

    if !canonical_target.starts_with(&canonical_base) {
        return Err("path traversal blocked".to_string());
    }

    Ok(canonical_target)
}

fn workspace_base_path(config: &ControlRoomConfig, workspace_id: &str) -> Result<PathBuf, String> {
    let workspace = config
        .workspaces
        .iter()
        .find(|workspace| workspace.id == workspace_id)
        .ok_or_else(|| format!("workspace not found: {workspace_id}"))?;
    Ok(PathBuf::from(&workspace.path))
}

pub fn list_workspace_entries(
    config: &ControlRoomConfig,
    workspace_id: &str,
    rel_or_abs: &str,
) -> Result<Vec<WorkspaceEntry>, String> {
    let base = workspace_base_path(config, workspace_id)?;
    let target = secure_target_path(&base, rel_or_abs)?;

    let mut entries = Vec::new();
    let dir = std::fs::read_dir(&target)
        .map_err(|e| format!("read_dir failed for {}: {e}", target.display()))?;

    for item in dir {
        let item = item.map_err(|e| format!("read_dir entry error: {e}"))?;
        let item_path = item.path();
        let meta = item
            .metadata()
            .map_err(|e| format!("metadata failed for {}: {e}", item_path.display()))?;

        let canonical_base = base
            .canonicalize()
            .map_err(|e| format!("workspace canonicalize failed: {e}"))?;
        let canonical_item = item_path
            .canonicalize()
            .map_err(|e| format!("entry canonicalize failed: {e}"))?;

        if !canonical_item.starts_with(&canonical_base) {
            continue;
        }

        let relative = canonical_item
            .strip_prefix(&canonical_base)
            .ok()
            .map(|p| p.to_string_lossy().to_string())
            .unwrap_or_else(String::new);

        let name = item
            .file_name()
            .to_string_lossy()
            .to_string();

        entries.push(WorkspaceEntry {
            name,
            path: relative,
            is_directory: meta.is_dir(),
            size: if meta.is_file() { Some(meta.len()) } else { None },
            modified_ms: now_modified_ms(&meta),
        });
    }

    entries.sort_by(|a, b| match (a.is_directory, b.is_directory) {
        (true, false) => std::cmp::Ordering::Less,
        (false, true) => std::cmp::Ordering::Greater,
        _ => a.name.to_lowercase().cmp(&b.name.to_lowercase()),
    });

    Ok(entries)
}

pub fn read_workspace_file(
    config: &ControlRoomConfig,
    workspace_id: &str,
    rel_or_abs: &str,
    max_bytes: usize,
) -> Result<String, String> {
    let base = workspace_base_path(config, workspace_id)?;
    let target = secure_target_path(&base, rel_or_abs)?;

    let meta = std::fs::metadata(&target)
        .map_err(|e| format!("metadata failed for {}: {e}", target.display()))?;
    if !meta.is_file() {
        return Err(format!("not a file: {}", target.display()));
    }
    if meta.len() as usize > max_bytes {
        return Err(format!(
            "file too large for editor: {} bytes (max {})",
            meta.len(),
            max_bytes
        ));
    }

    let raw = std::fs::read(&target)
        .map_err(|e| format!("read failed for {}: {e}", target.display()))?;
    Ok(String::from_utf8_lossy(&raw).to_string())
}

pub fn write_workspace_file(
    config: &ControlRoomConfig,
    workspace_id: &str,
    rel_or_abs: &str,
    content: &str,
    max_bytes: usize,
) -> Result<bool, String> {
    if content.as_bytes().len() > max_bytes {
        return Err(format!(
            "content too large for editor save: {} bytes (max {})",
            content.as_bytes().len(),
            max_bytes
        ));
    }

    let base = workspace_base_path(config, workspace_id)?;
    let target = secure_target_path(&base, rel_or_abs)?;
    let meta = std::fs::metadata(&target)
        .map_err(|e| format!("metadata failed for {}: {e}", target.display()))?;
    if !meta.is_file() {
        return Err(format!("not a file: {}", target.display()));
    }

    std::fs::write(&target, content)
        .map_err(|e| format!("write failed for {}: {e}", target.display()))?;
    Ok(true)
}
