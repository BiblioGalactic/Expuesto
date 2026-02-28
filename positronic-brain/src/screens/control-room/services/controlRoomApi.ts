import { invoke } from "@tauri-apps/api/core";
import type {
  ControlRoomConfig,
  GitCommit,
  RunnerCommandInput,
  RunnerStartResponse,
  ServiceConfig,
  ServiceLogEvent,
  ServiceStatus,
  VideoLaunchNativeInput,
  VideoLaunchNativeResult,
  VideoSnapshotAnalyzeInput,
  VideoSnapshotAnalyzeResult,
  WorkspaceEntry,
} from "../types";

export async function controlroomLoadConfig(): Promise<ControlRoomConfig> {
  return invoke<ControlRoomConfig>("controlroom_load_config");
}

export async function controlroomGetServices(): Promise<ServiceConfig[]> {
  return invoke<ServiceConfig[]>("controlroom_get_services");
}

export async function controlroomServiceStart(serviceId: string): Promise<ServiceStatus> {
  return invoke<ServiceStatus>("controlroom_service_start", { serviceId });
}

export async function controlroomServiceStop(serviceId: string): Promise<ServiceStatus> {
  return invoke<ServiceStatus>("controlroom_service_stop", { serviceId });
}

export async function controlroomServiceRestart(serviceId: string): Promise<ServiceStatus> {
  return invoke<ServiceStatus>("controlroom_service_restart", { serviceId });
}

export async function controlroomServiceStatus(serviceId: string): Promise<ServiceStatus> {
  return invoke<ServiceStatus>("controlroom_service_status", { serviceId });
}

export async function controlroomServiceStatusAll(): Promise<ServiceStatus[]> {
  return invoke<ServiceStatus[]>("controlroom_service_status_all");
}

export async function controlroomServiceClearLogs(serviceId: string): Promise<boolean> {
  return invoke<boolean>("controlroom_service_clear_logs", { serviceId });
}

export async function controlroomServiceLogs(serviceId: string, limit = 300): Promise<ServiceLogEvent[]> {
  return invoke<ServiceLogEvent[]>("controlroom_service_logs", { serviceId, limit });
}

export async function controlroomRunnerExecute(input: RunnerCommandInput): Promise<RunnerStartResponse> {
  return invoke<RunnerStartResponse>("controlroom_runner_execute", { input });
}

export async function controlroomRunnerCancel(runId: string): Promise<boolean> {
  return invoke<boolean>("controlroom_runner_cancel", { runId });
}

export async function controlroomWorkspaceList(workspaceId: string, relativePath = ""): Promise<WorkspaceEntry[]> {
  return invoke<WorkspaceEntry[]>("controlroom_workspace_list", { workspaceId, relativePath });
}

export async function controlroomWorkspaceReadFile(
  workspaceId: string,
  relativePath: string,
): Promise<string> {
  return invoke<string>("controlroom_workspace_read_file", { workspaceId, relativePath });
}

export async function controlroomWorkspaceWriteFile(
  workspaceId: string,
  relativePath: string,
  content: string,
): Promise<boolean> {
  return invoke<boolean>("controlroom_workspace_write_file", { workspaceId, relativePath, content });
}

export async function controlroomGitCommits(
  workspaceId: string,
  limit = 30,
  skip = 0
): Promise<GitCommit[]> {
  return invoke<GitCommit[]>("controlroom_git_commits", { workspaceId, limit, skip });
}

export async function controlroomExportLogs(serviceId: string, targetPath: string): Promise<boolean> {
  return invoke<boolean>("controlroom_export_logs", { serviceId, targetPath });
}

export async function controlroomVideoLaunchNative(input: VideoLaunchNativeInput): Promise<VideoLaunchNativeResult> {
  return invoke<VideoLaunchNativeResult>("controlroom_video_launch_native", { input });
}

export async function controlroomVideoSnapshotAnalyze(
  input: VideoSnapshotAnalyzeInput,
): Promise<VideoSnapshotAnalyzeResult> {
  return invoke<VideoSnapshotAnalyzeResult>("controlroom_video_snapshot_analyze", { input });
}
