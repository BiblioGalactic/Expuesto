use crate::controlroom::types::{ControlRoomConfig, GitCommit};

pub async fn get_commits(
    config: &ControlRoomConfig,
    workspace_id: &str,
    limit: u32,
    skip: u32,
) -> Result<Vec<GitCommit>, String> {
    let workspace = config
        .workspaces
        .iter()
        .find(|workspace| workspace.id == workspace_id)
        .ok_or_else(|| format!("workspace not found: {workspace_id}"))?;

    let check_output = tokio::process::Command::new("git")
        .arg("-C")
        .arg(&workspace.path)
        .arg("rev-parse")
        .arg("--is-inside-work-tree")
        .output()
        .await
        .map_err(|e| format!("git check failed: {e}"))?;

    if !check_output.status.success() {
        return Ok(Vec::new());
    }

    let output = tokio::process::Command::new("git")
        .arg("-C")
        .arg(&workspace.path)
        .arg("log")
        .arg(format!("--skip={skip}"))
        .arg(format!("-n{limit}"))
        .arg("--date=iso-strict")
        .arg("--pretty=format:%H%x1f%h%x1f%an%x1f%ad%x1f%s")
        .output()
        .await
        .map_err(|e| format!("git log failed: {e}"))?;

    if !output.status.success() {
        return Ok(Vec::new());
    }

    let text = String::from_utf8_lossy(&output.stdout);
    let mut commits = Vec::new();

    for line in text.lines() {
        if line.trim().is_empty() {
            continue;
        }

        let parts: Vec<&str> = line.split('\u{1f}').collect();
        if parts.len() != 5 {
            continue;
        }

        commits.push(GitCommit {
            hash: parts[0].to_string(),
            short_hash: parts[1].to_string(),
            author: parts[2].to_string(),
            date: parts[3].to_string(),
            message: parts[4].to_string(),
        });
    }

    Ok(commits)
}
