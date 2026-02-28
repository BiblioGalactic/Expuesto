export type ServiceState = "running" | "stopped" | "error" | "starting" | "stopping";
export type FeatureTier = "stable" | "experimental";

export interface SafeCommandSpec {
  program: string;
  args: string[];
  cwd?: string;
  env?: Record<string, string>;
}

export interface ServiceHealthSpec {
  program: string;
  args: string[];
  intervalSec?: number;
}

export interface ServiceConfig {
  id: string;
  name: string;
  cwd?: string;
  start: SafeCommandSpec;
  stop?: SafeCommandSpec;
  restart?: SafeCommandSpec;
  health?: ServiceHealthSpec;
  logSources?: string[];
  tier?: FeatureTier;
}

export type VideoFeedKind = "auto" | "rtsp" | "hls" | "mjpeg" | "image" | "web";

export interface WorkspaceConfig {
  id: string;
  name: string;
  path: string;
}

export interface VideoAutoPauseConfig {
  whenModeNotMultimedia: boolean;
  whenPanelHidden: boolean;
  whenAppHidden: boolean;
  whenHighLoad: boolean;
  highLoadLatencyMs: number;
  highLoadConsecutiveSamples: number;
}

export interface VideoNativeLauncherConfig {
  id: string;
  name: string;
  command: SafeCommandSpec;
}

export interface VideoSnapshotConfig {
  enabled: boolean;
  timeoutMs: number;
  analyzerCommand?: SafeCommandSpec;
}

export interface VideoWallConfig {
  enabled: boolean;
  maxActiveFeeds: number;
  autoPause: VideoAutoPauseConfig;
  nativeLaunchers: VideoNativeLauncherConfig[];
  snapshot: VideoSnapshotConfig;
}

export interface ControlRoomConfig {
  featureFlags: {
    controlRoomEnabled: boolean;
  };
  ui: {
    defaultView: "control-room" | "classic";
    rememberLastView: boolean;
    shortcuts: {
      commandPalette: string;
    };
    layout: {
      showLeftSidebar: boolean;
      showTopBar: boolean;
    };
  };
  services: ServiceConfig[];
  workspaces: WorkspaceConfig[];
  git: {
    enabled: boolean;
    maxCommits: number;
  };
  videoWall?: VideoWallConfig;
}

export interface ServiceStatus {
  serviceId: string;
  state: ServiceState;
  pid?: number | null;
  uptimeSec?: number | null;
  lastError?: string | null;
  correlationId?: string;
}

export interface ServiceLogEvent {
  serviceId: string;
  stream: "stdout" | "stderr";
  ts: number;
  level: "info" | "warn" | "error";
  line: string;
  correlationId?: string;
}

export interface RunnerCommandInput {
  workspaceId?: string;
  program: string;
  args: string[];
}

export interface RunnerStartResponse {
  runId: string;
}

export interface RunnerOutputEvent {
  runId: string;
  stream: "stdout" | "stderr";
  ts: number;
  line: string;
  correlationId?: string;
}

export interface RunnerExitEvent {
  runId: string;
  code?: number | null;
  signal?: string | null;
  correlationId?: string;
}

export interface WorkspaceEntry {
  name: string;
  path: string;
  isDirectory: boolean;
  size?: number | null;
  modifiedMs?: number | null;
}

export interface GitCommit {
  hash: string;
  shortHash: string;
  author: string;
  date: string;
  message: string;
}

export interface ControlRoomBackendError {
  scope: string;
  message: string;
  correlationId?: string;
}

export interface ServiceRealtimeMeta {
  serviceId: string;
  lastStatusTs?: number;
  lastStateChangeTs?: number;
  transitionCount: number;
}

export type RuntimeActivityLevel = "info" | "warn" | "error";

export interface RuntimeActivityStatus {
  id: string;
  name: string;
  hitCount: number;
  level: RuntimeActivityLevel;
  lastSeenTs?: number;
  lastSourceServiceId?: string;
  lastLine?: string;
  lastMetricMs?: number;
  metricSource?: "log" | "activity";
  samples: number[];
}

export type DashboardMode = "all" | "dev" | "multimedia" | "medical";

export interface ServiceTelemetry {
  serviceId: string;
  port?: number;
  lastLatencyMs?: number;
  samples: number[];
  unavailableCount: number;
}

export type RealtimeConnectionState = "connecting" | "online" | "degraded" | "offline";

export interface RealtimeBusStatus {
  state: RealtimeConnectionState;
  reconnectCount: number;
  subscribedTs?: number;
  lastEventTs?: number;
  lastStatusSyncTs?: number;
  lastError?: string | null;
}

export type FeedCategory = "service" | "runner" | "agent" | "system" | "video";
export type FeedSeverity = "info" | "warn" | "error";

export interface ControlFeedEvent {
  id: string;
  ts: number;
  category: FeedCategory;
  severity: FeedSeverity;
  source: string;
  message: string;
  correlationId?: string;
}

export interface RunnerRunMeta {
  runId: string;
  startedTs: number;
  input: RunnerCommandInput;
}

export interface VideoEvent {
  ts: number;
  severity: FeedSeverity;
  source: string;
  message: string;
  feedId?: string;
  kind?: string;
  details?: string;
  correlationId?: string;
}

export interface VideoLaunchNativeInput {
  launcherId: string;
  feedId?: string;
  feedName?: string;
  feedUrl?: string;
}

export interface VideoLaunchNativeResult {
  ok: boolean;
  message: string;
}

export interface VideoSnapshotAnalyzeInput {
  feedId?: string;
  feedName?: string;
  imageBase64: string;
}

export interface VideoSnapshotAnalyzeResult {
  ok: boolean;
  summary: string;
  message?: string;
}
