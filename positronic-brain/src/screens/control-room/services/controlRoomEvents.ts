import { listen } from "@tauri-apps/api/event";
import type {
  ControlRoomBackendError,
  RunnerExitEvent,
  RunnerOutputEvent,
  ServiceLogEvent,
  ServiceStatus,
  VideoEvent,
} from "../types";

export interface ControlRoomEventHandlers {
  onServiceLog?: (event: ServiceLogEvent) => void;
  onServiceState?: (event: ServiceStatus) => void;
  onRunnerOutput?: (event: RunnerOutputEvent) => void;
  onRunnerExit?: (event: RunnerExitEvent) => void;
  onBackendError?: (event: ControlRoomBackendError) => void;
  onVideoEvent?: (event: VideoEvent) => void;
}

export async function subscribeControlRoomEvents(handlers: ControlRoomEventHandlers): Promise<() => void> {
  const unlisteners = await Promise.all([
    listen<ServiceLogEvent>("controlroom://service-log", (event) => handlers.onServiceLog?.(event.payload)),
    listen<ServiceStatus>("controlroom://service-state", (event) => handlers.onServiceState?.(event.payload)),
    listen<RunnerOutputEvent>("controlroom://runner-output", (event) => handlers.onRunnerOutput?.(event.payload)),
    listen<RunnerExitEvent>("controlroom://runner-exit", (event) => handlers.onRunnerExit?.(event.payload)),
    listen<ControlRoomBackendError>("controlroom://backend-error", (event) => handlers.onBackendError?.(event.payload)),
    listen<VideoEvent>("controlroom://video-event", (event) => handlers.onVideoEvent?.(event.payload)),
  ]);

  return () => {
    unlisteners.forEach((unlisten) => {
      void unlisten();
    });
  };
}
