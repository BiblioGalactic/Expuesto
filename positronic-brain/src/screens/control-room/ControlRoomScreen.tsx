import { Button } from "@/components/ui/button";
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from "@/components/ui/resizable";
import { toast } from "sonner";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { parseControlRoomConfig } from "./schema";
import type {
  ControlFeedEvent,
  ControlRoomConfig,
  DashboardMode,
  RealtimeBusStatus,
  RuntimeActivityStatus,
  RunnerCommandInput,
  RunnerRunMeta,
  ServiceConfig,
  ServiceRealtimeMeta,
  ServiceState,
  ServiceStatus,
  ServiceTelemetry,
  VideoEvent,
  WorkspaceEntry,
} from "./types";
import {
  controlroomExportLogs,
  controlroomGetServices,
  controlroomGitCommits,
  controlroomRunnerCancel,
  controlroomRunnerExecute,
  controlroomServiceClearLogs,
  controlroomServiceLogs,
  controlroomServiceRestart,
  controlroomServiceStart,
  controlroomServiceStatusAll,
  controlroomServiceStop,
  controlroomWorkspaceReadFile,
  controlroomWorkspaceList,
  controlroomWorkspaceWriteFile,
} from "./services/controlRoomApi";
import { subscribeControlRoomEvents } from "./services/controlRoomEvents";
import { ControlRoomStoreProvider, useControlRoomStore } from "./store/controlRoomStore";
import { CommandPalette, type PaletteAction } from "./components/CommandPalette";
import { AgentsPanel } from "./components/AgentsPanel";
import { CenterPanelLayout } from "./components/CenterPanelLayout";
import { ChannelChatsPanel } from "./components/ChannelChatsPanel";
import { LeftSidebar } from "./components/LeftSidebar";
import { LiveEditorPanel, type LiveEditorSelection } from "./components/LiveEditorPanel";
import { LiveFeedPanel } from "./components/LiveFeedPanel";
import { NetworkGraphPanel } from "./components/NetworkGraphPanel";
import { OutputMirrorPanel } from "./components/OutputMirrorPanel";
import { TopStatusBar } from "./components/TopStatusBar";
import { VideoWallPanel } from "./components/VideoWallPanel";

interface ControlRoomScreenProps {
  config: ControlRoomConfig;
  onSwitchClassic: () => void;
}

const MAX_FEED_EVENTS = 450;
const STATUS_SYNC_DEGRADED_MS = 12000;
const STATUS_SYNC_OFFLINE_MS = 30000;
const RUNTIME_ACTIVITY_ACTIVE_MS = 90000;
const TELEMETRY_INTERVAL_MS = 12000;
const TELEMETRY_TIMEOUT_MS = 1800;
const TELEMETRY_MAX_SAMPLES = 24;

const RUNTIME_ACTIVITY_DEFS: Array<{ id: string; name: string; patterns: RegExp[] }> = [
  {
    id: "audio-stt",
    name: "Audio STT",
    patterns: [/\bstt\b/i, /\btranscrib/i, /\bwhisper\b/i, /\baudio\s+processing\b/i],
  },
  {
    id: "ocr",
    name: "OCR",
    patterns: [/\bocr\b/i, /\bpaddleocr\b/i, /\btext\s+detect/i],
  },
  {
    id: "vlm",
    name: "VLM",
    patterns: [/\bvlm\b/i, /\bqwen2\.5-vl\b/i, /\bimage\s+caption\b/i, /\bvisual\b/i],
  },
  {
    id: "yolo",
    name: "YOLO",
    patterns: [/\byolo\b/i, /\bultralytics\b/i, /\bdetection/i],
  },
  {
    id: "image-gen",
    name: "Image Gen",
    patterns: [/\b\/img\b/i, /\bsdxl\b/i, /\bdiffusers\b/i, /\bimage\s+generation\b/i],
  },
  {
    id: "rag",
    name: "RAG",
    patterns: [/\brag\b/i, /\bretrieval\b/i, /\bwikirag\b/i, /\bgutenberg\b/i, /\barxiv\b/i],
  },
  {
    id: "aider",
    name: "Aider",
    patterns: [/\baider\b/i, /\bgit\s+ls-files\b/i],
  },
  {
    id: "sms",
    name: "SMS",
    patterns: [/\bsms\b/i, /\bmessages\.app\b/i, /\bosascript\b/i],
  },
  {
    id: "clone-tts",
    name: "Clone TTS",
    patterns: [/\bclone\b/i, /\bxtts\b/i, /\btts\b/i, /\bvoice\b/i],
  },
  {
    id: "web",
    name: "Web",
    patterns: [/\bweb\s*scrape\b/i, /\b\/web\b/i, /\bscrap/i],
  },
  {
    id: "medical",
    name: "Medical",
    patterns: [
      /(?:^|[\s"'`])\/salud\b/i,
      /\bmedicalApplied\b["'=:\s]*true\b/i,
      /\brunMedicalContextQuery\b/i,
      /\[Contexto salud local\b/i,
      /\bSalud error\b/i,
    ],
  },
];

const RUNTIME_ACTIVITY_NAME_BY_ID = new Map(
  RUNTIME_ACTIVITY_DEFS.map((definition) => [definition.id, definition.name]),
);

const RUNTIME_ACTIVITY_ERROR_HINT = /\b(error|failed|traceback|exception|enoent|cannot|timed out|timeout)\b/i;

function buildInitialRuntimeActivityState(): Record<string, RuntimeActivityStatus> {
  return RUNTIME_ACTIVITY_DEFS.reduce<Record<string, RuntimeActivityStatus>>((acc, definition) => {
    acc[definition.id] = {
      id: definition.id,
      name: definition.name,
      hitCount: 0,
      level: "info",
      samples: [],
    };
    return acc;
  }, {});
}

function detectRuntimeActivityModules(line: string): string[] {
  const clean = String(line ?? "").trim();
  if (!clean) return [];
  return RUNTIME_ACTIVITY_DEFS.filter((definition) =>
    definition.patterns.some((pattern) => pattern.test(clean)),
  ).map((definition) => definition.id);
}

function extractRuntimeMetricMs(line: string): number | undefined {
  const clean = String(line ?? "");
  if (!clean) return undefined;

  const msMatch = clean.match(/(\d+(?:\.\d+)?)\s*ms\b/i);
  if (msMatch) {
    const value = Number.parseFloat(msMatch[1] ?? "");
    if (Number.isFinite(value) && value > 0) return Math.round(value);
  }

  const secMatch = clean.match(/(\d+(?:\.\d+)?)\s*s(?:ec|econds?)?\b/i);
  if (secMatch) {
    const seconds = Number.parseFloat(secMatch[1] ?? "");
    if (Number.isFinite(seconds) && seconds > 0) return Math.round(seconds * 1000);
  }

  return undefined;
}

function normalizeServiceText(service: ServiceConfig): string {
  return [service.id, service.name, service.start.program, ...service.start.args]
    .join(" ")
    .toLowerCase();
}

function serviceMatchesMode(service: ServiceConfig, mode: DashboardMode): boolean {
  if (mode === "all") return true;
  const text = normalizeServiceText(service);
  if (mode === "dev") {
    return /aider|deepseek|dolphin|unholy|mytho|llama|git|bridge|runner|mistral|gateway|openclaw/.test(
      text,
    );
  }
  if (mode === "multimedia") {
    return /image|ocr|audio|clone|tts|whisper|yolo|vlm|diffusion|sdxl/.test(text);
  }
  if (mode === "medical") {
    return /meditron|medical|salud|health|apple|fitness|ecg|doctor|medico/.test(text);
  }
  return true;
}

function extractServicePort(service: ServiceConfig): number | undefined {
  const args = service.start.args ?? [];
  for (let i = 0; i < args.length; i += 1) {
    const value = args[i];
    if ((value === "--port" || value === "-p") && args[i + 1]) {
      const port = Number.parseInt(args[i + 1], 10);
      if (Number.isFinite(port) && port > 0 && port <= 65535) return port;
    }
    if (value.startsWith("--port=")) {
      const port = Number.parseInt(value.split("=")[1] ?? "", 10);
      if (Number.isFinite(port) && port > 0 && port <= 65535) return port;
    }
  }
  return undefined;
}

async function probeLatency(port: number): Promise<number | null> {
  const candidates = [
    `http://127.0.0.1:${port}/health`,
    `http://127.0.0.1:${port}/v1/models`,
    `http://127.0.0.1:${port}/`,
  ];

  for (const url of candidates) {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), TELEMETRY_TIMEOUT_MS);
    const start = performance.now();
    try {
      await fetch(url, {
        method: "GET",
        mode: "no-cors",
        cache: "no-store",
        signal: controller.signal,
      });
      window.clearTimeout(timeout);
      return performance.now() - start;
    } catch {
      window.clearTimeout(timeout);
    }
  }
  return null;
}

function severityFromState(state: ServiceState): "info" | "warn" | "error" {
  if (state === "error") return "error";
  if (state === "starting" || state === "stopping") return "warn";
  return "info";
}

function ControlRoomInner({ onSwitchClassic }: { onSwitchClassic: () => void }) {
  const { state, dispatch } = useControlRoomStore();
  const [services, setServices] = useState<ServiceConfig[]>(state.config.services);
  const [dashboardMode, setDashboardMode] = useState<DashboardMode>("all");
  const [commitsLoading, setCommitsLoading] = useState(false);
  const [commitsError, setCommitsError] = useState<string | null>(null);
  const [feedEvents, setFeedEvents] = useState<ControlFeedEvent[]>([]);
  const [runnerMetaByRun, setRunnerMetaByRun] = useState<Record<string, RunnerRunMeta>>({});
  const [realtimeByService, setRealtimeByService] = useState<Record<string, ServiceRealtimeMeta>>({});
  const [telemetryByService, setTelemetryByService] = useState<Record<string, ServiceTelemetry>>({});
  const [servicesRefreshing, setServicesRefreshing] = useState(false);
  const [runtimeActivityById, setRuntimeActivityById] = useState<Record<string, RuntimeActivityStatus>>(
    () => buildInitialRuntimeActivityState(),
  );
  const [editorSelection, setEditorSelection] = useState<LiveEditorSelection | null>(null);
  const [editorContent, setEditorContent] = useState("");
  const [editorDirty, setEditorDirty] = useState(false);
  const [editorLoading, setEditorLoading] = useState(false);
  const [editorSaving, setEditorSaving] = useState(false);
  const [editorError, setEditorError] = useState<string | null>(null);
  const [busStatus, setBusStatus] = useState<RealtimeBusStatus>({
    state: "connecting",
    reconnectCount: 0,
    lastError: null,
  });

  const feedSeqRef = useRef(1);
  const lastServiceDigestRef = useRef<Record<string, string>>({});
  const runnerMetaRef = useRef<Record<string, RunnerRunMeta>>({});
  const prevServiceStateRef = useRef<Record<string, ServiceState>>({});
  const realtimeMetaRef = useRef<Record<string, ServiceRealtimeMeta>>({});

  useEffect(() => {
    runnerMetaRef.current = runnerMetaByRun;
  }, [runnerMetaByRun]);

  useEffect(() => {
    realtimeMetaRef.current = realtimeByService;
  }, [realtimeByService]);

  const appendFeedEvent = useCallback((event: Omit<ControlFeedEvent, "id">) => {
    const withId: ControlFeedEvent = {
      ...event,
      id: `feed-${event.ts}-${feedSeqRef.current++}`,
    };
    setFeedEvents((prev) => [withId, ...prev].slice(0, MAX_FEED_EVENTS));
  }, []);

  const touchBusEvent = useCallback((ts: number) => {
    setBusStatus((prev) => ({
      ...prev,
      state: prev.state === "offline" ? "degraded" : "online",
      lastEventTs: ts,
      lastError: null,
    }));
  }, []);

  const markBusError = useCallback((message: string, nextState: RealtimeBusStatus["state"]) => {
    setBusStatus((prev) => ({
      ...prev,
      state: nextState,
      lastError: message,
    }));
  }, []);

  const markRuntimeActivityFromLog = useCallback(
    (serviceId: string, eventLevel: "info" | "warn" | "error", line: string, ts: number) => {
      const modules = detectRuntimeActivityModules(line);
      if (modules.length === 0) return;
      const parsedMetricMs = extractRuntimeMetricMs(line);

      const normalizedLevel: RuntimeActivityStatus["level"] =
        eventLevel === "error" || RUNTIME_ACTIVITY_ERROR_HINT.test(line)
          ? "error"
          : eventLevel === "warn"
            ? "warn"
            : "info";
      const preview = line.slice(0, 180);

      setRuntimeActivityById((prev) => {
        const next = { ...prev };
        modules.forEach((moduleId) => {
          const name = RUNTIME_ACTIVITY_NAME_BY_ID.get(moduleId) ?? moduleId;
          const current = next[moduleId] ?? {
            id: moduleId,
            name,
            hitCount: 0,
            level: "info" as const,
            samples: [],
          };
          const derivedMetricMs =
            parsedMetricMs ??
            (current.lastSeenTs && ts > current.lastSeenTs ? Math.max(1, ts - current.lastSeenTs) : undefined);
          const samples = Number.isFinite(derivedMetricMs)
            ? [...(current.samples ?? []), Math.round(derivedMetricMs as number)].slice(-TELEMETRY_MAX_SAMPLES)
            : [...(current.samples ?? [])];
          next[moduleId] = {
            ...current,
            level: normalizedLevel,
            hitCount: current.hitCount + 1,
            lastSeenTs: ts,
            lastSourceServiceId: serviceId,
            lastLine: preview,
            lastMetricMs: Number.isFinite(derivedMetricMs)
              ? Math.round(derivedMetricMs as number)
              : current.lastMetricMs,
            metricSource: parsedMetricMs ? "log" : Number.isFinite(derivedMetricMs) ? "activity" : current.metricSource,
            samples,
          };
        });
        return next;
      });
    },
    [],
  );

  const updateRealtimeFromStatuses = useCallback(
    (statuses: ServiceStatus[], sourceTs: number) => {
      if (statuses.length === 0) return;

      const nextMeta: Record<string, ServiceRealtimeMeta> = { ...realtimeMetaRef.current };

      statuses.forEach((status) => {
        const prevState = prevServiceStateRef.current[status.serviceId];
        const prevMeta = nextMeta[status.serviceId] ?? {
          serviceId: status.serviceId,
          transitionCount: 0,
        };

        const stateChanged = prevState !== undefined && prevState !== status.state;

        nextMeta[status.serviceId] = {
          ...prevMeta,
          lastStatusTs: sourceTs,
          lastStateChangeTs: stateChanged
            ? sourceTs
            : prevMeta.lastStateChangeTs ?? sourceTs,
          transitionCount: stateChanged
            ? prevMeta.transitionCount + 1
            : prevMeta.transitionCount,
        };

        if (stateChanged) {
          appendFeedEvent({
            ts: sourceTs,
            category: "agent",
            severity: severityFromState(status.state),
            source: status.serviceId,
            message: `${status.serviceId} transitioned ${prevState} -> ${status.state}`,
          });
        }

        prevServiceStateRef.current[status.serviceId] = status.state;
      });

      realtimeMetaRef.current = nextMeta;
      setRealtimeByService(nextMeta);
      setBusStatus((prev) => ({
        ...prev,
        state: "online",
        lastStatusSyncTs: sourceTs,
        lastError: null,
      }));
    },
    [appendFeedEvent],
  );

  const refreshServicesAndStatuses = useCallback(
    async (options?: { includeDefinitions?: boolean; silent?: boolean }) => {
      const includeDefinitions = options?.includeDefinitions ?? false;
      const silent = options?.silent ?? false;
      setServicesRefreshing(true);
      try {
        if (includeDefinitions) {
          const [serviceDefs, statuses] = await Promise.all([
            controlroomGetServices(),
            controlroomServiceStatusAll(),
          ]);
          const now = Date.now();
          setServices(serviceDefs);
          dispatch({ type: "SET_SERVICE_STATUSES", payload: statuses });
          await Promise.all(
            serviceDefs.map(async (service) => {
              try {
                const snapshot = await controlroomServiceLogs(service.id, 400);
                dispatch({
                  type: "SET_SERVICE_LOGS",
                  payload: { serviceId: service.id, logs: snapshot },
                });
              } catch {
                // Best-effort hydration: keep stream-only mode if snapshot is unavailable.
              }
            }),
          );
          updateRealtimeFromStatuses(statuses, now);
          return;
        }

        const statuses = await controlroomServiceStatusAll();
        const now = Date.now();
        dispatch({ type: "SET_SERVICE_STATUSES", payload: statuses });
        updateRealtimeFromStatuses(statuses, now);
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        markBusError(message, "degraded");
        if (!silent) {
          toast.error(`Service sync failed: ${message}`);
        }
      } finally {
        setServicesRefreshing(false);
      }
    },
    [dispatch, markBusError, updateRealtimeFromStatuses],
  );

  useEffect(() => {
    let stop = () => {};
    let cancelled = false;
    let retryTimer: number | null = null;

    async function connect(retry: boolean) {
      if (cancelled) return;
      setBusStatus((prev) => ({
        ...prev,
        state: retry ? "degraded" : "connecting",
      }));

      try {
        const unsubscribe = await subscribeControlRoomEvents({
          onServiceLog: (event) => {
            dispatch({ type: "APPEND_SERVICE_LOG", payload: event });
            touchBusEvent(event.ts);
            const msg = event.line.trim();
            if (!msg) return;
            markRuntimeActivityFromLog(event.serviceId, event.level, msg, event.ts);
            appendFeedEvent({
              ts: event.ts,
              category: "service",
              severity: event.level,
              source: event.serviceId,
              message: msg,
              correlationId: event.correlationId,
            });
          },
          onServiceState: (event) => {
            const now = Date.now();
            dispatch({ type: "UPSERT_SERVICE_STATUS", payload: event });
            updateRealtimeFromStatuses([event], now);
            touchBusEvent(now);

            const digest = `${event.state}|${event.pid ?? ""}|${event.lastError ?? ""}`;
            const previous = lastServiceDigestRef.current[event.serviceId];
            if (previous === digest) return;
            lastServiceDigestRef.current[event.serviceId] = digest;

            appendFeedEvent({
              ts: now,
              category: "service",
              severity: severityFromState(event.state),
              source: event.serviceId,
              message: `state=${event.state}${event.uptimeSec ? ` · uptime=${event.uptimeSec}s` : ""}${event.lastError ? ` · ${event.lastError}` : ""}`,
              correlationId: event.correlationId,
            });
          },
          onRunnerOutput: (event) => {
            dispatch({ type: "APPEND_RUNNER_OUTPUT", payload: event });
            touchBusEvent(event.ts);
            const msg = event.line.trim();
            if (!msg) return;
            appendFeedEvent({
              ts: event.ts,
              category: "runner",
              severity: event.stream === "stderr" ? "warn" : "info",
              source: event.runId,
              message: msg,
              correlationId: event.correlationId,
            });
          },
          onRunnerExit: (event) => {
            const now = Date.now();
            dispatch({ type: "SET_RUNNER_EXIT", payload: event });
            touchBusEvent(now);
            const meta = runnerMetaRef.current[event.runId];
            const command = meta ? [meta.input.program, ...meta.input.args].join(" ").trim() : "runner";
            appendFeedEvent({
              ts: now,
              category: "runner",
              severity: event.code === 0 ? "info" : "error",
              source: event.runId,
              message: `${command} exited with code=${event.code ?? "null"} signal=${event.signal ?? "null"}`,
              correlationId: event.correlationId,
            });
          },
          onVideoEvent: (event) => {
            const now = event.ts || Date.now();
            appendFeedEvent({
              ts: now,
              category: "video",
              severity: event.severity,
              source: event.source || "video",
              message: event.message,
              correlationId: event.correlationId,
            });
          },
          onBackendError: (event) => {
            const now = Date.now();
            appendFeedEvent({
              ts: now,
              category: "system",
              severity: "error",
              source: event.scope,
              message: event.message,
              correlationId: event.correlationId,
            });
            markBusError(event.message, "degraded");
            toast.error(`${event.scope}: ${event.message}`);
          },
        });

        if (cancelled) {
          unsubscribe();
          return;
        }

        stop = unsubscribe;
        setBusStatus((prev) => ({
          ...prev,
          state: "online",
          subscribedTs: prev.subscribedTs ?? Date.now(),
          lastError: null,
        }));
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        setBusStatus((prev) => ({
          ...prev,
          state: "offline",
          reconnectCount: prev.reconnectCount + 1,
          lastError: message,
        }));

        if (!cancelled) {
          retryTimer = window.setTimeout(() => {
            void connect(true);
          }, 4000);
        }
      }
    }

    void connect(false);

    return () => {
      cancelled = true;
      if (retryTimer) window.clearTimeout(retryTimer);
      stop();
    };
  }, [
    appendFeedEvent,
    dispatch,
    markBusError,
    markRuntimeActivityFromLog,
    touchBusEvent,
    updateRealtimeFromStatuses,
  ]);

  useEffect(() => {
    void refreshServicesAndStatuses({ includeDefinitions: true });

    const timer = window.setInterval(() => {
      void refreshServicesAndStatuses({ includeDefinitions: false, silent: true });
    }, 3000);

    return () => {
      window.clearInterval(timer);
    };
  }, [refreshServicesAndStatuses]);

  const runningStateSignature = useMemo(
    () =>
      services
        .map((service) => `${service.id}:${state.serviceStatuses[service.id]?.state ?? "stopped"}`)
        .join("|"),
    [services, state.serviceStatuses],
  );

  const runningServices = useMemo(
    () => services.filter((service) => state.serviceStatuses[service.id]?.state === "running"),
    [services, runningStateSignature],
  );

  useEffect(() => {
    let cancelled = false;

    async function runTelemetryTick() {
      if (runningServices.length === 0) return;

      const results = await Promise.all(
        runningServices.map(async (service) => {
          const port = extractServicePort(service);
          if (!port) return { serviceId: service.id, port, latency: null as number | null };
          const latency = await probeLatency(port);
          return { serviceId: service.id, port, latency };
        }),
      );

      if (cancelled) return;

      setTelemetryByService((prev) => {
        const next: Record<string, ServiceTelemetry> = { ...prev };
        results.forEach((result) => {
          const current = next[result.serviceId] ?? {
            serviceId: result.serviceId,
            samples: [],
            unavailableCount: 0,
          };
          if (result.latency !== null) {
            next[result.serviceId] = {
              ...current,
              port: result.port,
              lastLatencyMs: result.latency,
              unavailableCount: 0,
              samples: [...current.samples, result.latency].slice(-TELEMETRY_MAX_SAMPLES),
            };
          } else {
            next[result.serviceId] = {
              ...current,
              port: result.port,
              lastLatencyMs: undefined,
              unavailableCount: current.unavailableCount + 1,
              samples: [...current.samples].slice(-TELEMETRY_MAX_SAMPLES),
            };
          }
        });
        return next;
      });
    }

    void runTelemetryTick();
    const timer = window.setInterval(() => {
      void runTelemetryTick();
    }, TELEMETRY_INTERVAL_MS);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [runningServices]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setBusStatus((prev) => {
        if (!prev.lastStatusSyncTs) return prev;
        const lag = Date.now() - prev.lastStatusSyncTs;

        let nextState = prev.state;
        if (lag >= STATUS_SYNC_OFFLINE_MS) {
          nextState = "offline";
        } else if (lag >= STATUS_SYNC_DEGRADED_MS) {
          nextState = "degraded";
        } else if (prev.state !== "connecting") {
          nextState = "online";
        }

        if (nextState === prev.state) return prev;
        return {
          ...prev,
          state: nextState,
        };
      });
    }, 2000);

    return () => {
      window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    if (!state.activeWorkspaceId || !state.config.git.enabled) return;
    setCommitsLoading(true);
    setCommitsError(null);
    void controlroomGitCommits(state.activeWorkspaceId, state.config.git.maxCommits, 0)
      .then((commits) => {
        dispatch({ type: "SET_COMMITS", payload: { workspaceId: state.activeWorkspaceId!, commits } });
      })
      .catch((error) => {
        setCommitsError(error instanceof Error ? error.message : String(error));
      })
      .finally(() => {
        setCommitsLoading(false);
      });
  }, [state.activeWorkspaceId, state.config.git.enabled, state.config.git.maxCommits, dispatch]);

  async function runStart(serviceId: string) {
    const status = await controlroomServiceStart(serviceId);
    const now = Date.now();
    dispatch({ type: "UPSERT_SERVICE_STATUS", payload: status });
    updateRealtimeFromStatuses([status], now);
  }

  async function runStop(serviceId: string) {
    const status = await controlroomServiceStop(serviceId);
    const now = Date.now();
    dispatch({ type: "UPSERT_SERVICE_STATUS", payload: status });
    updateRealtimeFromStatuses([status], now);
  }

  async function runRestart(serviceId: string) {
    const status = await controlroomServiceRestart(serviceId);
    const now = Date.now();
    dispatch({ type: "UPSERT_SERVICE_STATUS", payload: status });
    updateRealtimeFromStatuses([status], now);
  }

  async function clearLogs(serviceId: string) {
    await controlroomServiceClearLogs(serviceId);
    dispatch({ type: "CLEAR_SERVICE_LOG", payload: { serviceId } });
  }

  async function executeRunner(input: RunnerCommandInput): Promise<string | null> {
    dispatch({ type: "PUSH_HISTORY", payload: input });
    const startedTs = Date.now();

    try {
      const result = await controlroomRunnerExecute(input);
      const meta: RunnerRunMeta = {
        runId: result.runId,
        startedTs,
        input,
      };
      setRunnerMetaByRun((prev) => ({ ...prev, [result.runId]: meta }));
      appendFeedEvent({
        ts: startedTs,
        category: "runner",
        severity: "info",
        source: result.runId,
        message: `started ${[input.program, ...input.args].join(" ").trim()}`,
      });
      return result.runId;
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      appendFeedEvent({
        ts: Date.now(),
        category: "runner",
        severity: "error",
        source: "runner",
        message,
      });
      toast.error(`Runner failed: ${message}`);
      return null;
    }
  }

  async function cancelRunner(runId: string) {
    await controlroomRunnerCancel(runId);
  }

  async function fetchWorkspaceEntries(workspaceId: string, relativePath = ""): Promise<WorkspaceEntry[]> {
    const key = `${workspaceId}::${relativePath}`;
    const entries = await controlroomWorkspaceList(workspaceId, relativePath);
    dispatch({ type: "SET_WORKSPACE_CACHE", payload: { key, entries } });
    return entries;
  }

  async function loadEditorFile(selection: LiveEditorSelection) {
    setEditorLoading(true);
    setEditorError(null);
    try {
      const content = await controlroomWorkspaceReadFile(selection.workspaceId, selection.relativePath);
      setEditorContent(content);
      setEditorDirty(false);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setEditorError(message);
      setEditorContent("");
      setEditorDirty(false);
    } finally {
      setEditorLoading(false);
    }
  }

  function selectWorkspaceFile(workspaceId: string, relativePath: string, fileName: string) {
    const workspace = state.config.workspaces.find((item) => item.id === workspaceId);
    if (!workspace) return;
    const nextSelection: LiveEditorSelection = {
      workspaceId,
      workspaceName: workspace.name,
      relativePath,
      fileName,
    };
    setEditorSelection(nextSelection);
    void loadEditorFile(nextSelection);
  }

  function reloadEditorFile() {
    if (!editorSelection) return;
    void loadEditorFile(editorSelection);
  }

  function saveEditorFile() {
    if (!editorSelection) return;
    setEditorSaving(true);
    setEditorError(null);
    void controlroomWorkspaceWriteFile(editorSelection.workspaceId, editorSelection.relativePath, editorContent)
      .then(() => {
        setEditorDirty(false);
        toast.success(`Saved ${editorSelection.fileName}`);
      })
      .catch((error) => {
        const message = error instanceof Error ? error.message : String(error);
        setEditorError(message);
        toast.error(`Save failed: ${message}`);
      })
      .finally(() => {
        setEditorSaving(false);
      });
  }

  function startAll() {
    services.forEach((service) => {
      void runStart(service.id);
    });
  }

  function stopAll() {
    services.forEach((service) => {
      void runStop(service.id);
    });
  }

  function restartAll() {
    services.forEach((service) => {
      void runRestart(service.id);
    });
  }

  function clearAllLogs() {
    services.forEach((service) => {
      void clearLogs(service.id);
    });
  }

  function exportLogs(serviceId: string) {
    const targetPath = `${serviceId}-logs-${Date.now()}.txt`;
    void controlroomExportLogs(serviceId, targetPath)
      .then(() => toast.success(`Logs exported: ${targetPath}`))
      .catch((error) => toast.error(`Export failed: ${error instanceof Error ? error.message : String(error)}`));
  }

  function openWorkspace(workspaceId: string) {
    const workspace = state.config.workspaces.find((item) => item.id === workspaceId);
    if (!workspace) return;
    void import("@tauri-apps/plugin-opener")
      .then(({ openPath }) => openPath(workspace.path))
      .catch((error) => toast.error(`Open failed: ${error instanceof Error ? error.message : String(error)}`));
  }

  const commits = state.activeWorkspaceId ? state.commitsByWorkspace[state.activeWorkspaceId] ?? [] : [];
  const servicesForMode = useMemo(() => {
    const filtered = services.filter((service) => serviceMatchesMode(service, dashboardMode));
    return filtered.length > 0 ? filtered : services;
  }, [services, dashboardMode]);

  const experimentalServicesForMode = useMemo(
    () => servicesForMode.filter((service) => service.tier === "experimental"),
    [servicesForMode],
  );

  const highLoadThreshold = state.config.videoWall?.autoPause.highLoadLatencyMs ?? 350;
  const highLoadConsecutive = state.config.videoWall?.autoPause.highLoadConsecutiveSamples ?? 3;

  const isHighLoad = useMemo(() => {
    const runningIds = new Set(
      services
        .filter((service) => state.serviceStatuses[service.id]?.state === "running")
        .map((service) => service.id),
    );

    if (runningIds.size === 0) return false;

    return Object.values(telemetryByService).some((telemetry) => {
      if (!runningIds.has(telemetry.serviceId)) return false;
      const samples = telemetry.samples.filter((value) => Number.isFinite(value)).slice(-highLoadConsecutive);
      if (samples.length < highLoadConsecutive) return false;
      return samples.every((sample) => sample >= highLoadThreshold);
    });
  }, [highLoadConsecutive, highLoadThreshold, services, state.serviceStatuses, telemetryByService]);

  const handleVideoFeedEvent = useCallback(
    (event: VideoEvent) => {
      appendFeedEvent({
        ts: event.ts || Date.now(),
        category: "video",
        severity: event.severity || "info",
        source: event.source || "video-wall",
        message: event.message,
              correlationId: event.correlationId,
            });
    },
    [appendFeedEvent],
  );

  const runtimeActivities = useMemo(() => {
    const now = Date.now();
    return Object.values(runtimeActivityById).sort((a, b) => {
      const aActive = a.lastSeenTs ? now - a.lastSeenTs <= RUNTIME_ACTIVITY_ACTIVE_MS : false;
      const bActive = b.lastSeenTs ? now - b.lastSeenTs <= RUNTIME_ACTIVITY_ACTIVE_MS : false;
      if (aActive !== bActive) return aActive ? -1 : 1;
      const aLast = a.lastSeenTs ?? 0;
      const bLast = b.lastSeenTs ?? 0;
      if (aLast !== bLast) return bLast - aLast;
      return a.name.localeCompare(b.name);
    });
  }, [runtimeActivityById, busStatus.lastStatusSyncTs]);

  const paletteActions = useMemo<PaletteAction[]>(() => {
    const serviceActions: PaletteAction[] = services.flatMap((service) => [
      {
        id: `${service.id}-start`,
        label: `Start ${service.name}`,
        group: "Services",
        run: () => void runStart(service.id),
      },
      {
        id: `${service.id}-stop`,
        label: `Stop ${service.name}`,
        group: "Services",
        run: () => void runStop(service.id),
      },
      {
        id: `${service.id}-restart`,
        label: `Restart ${service.name}`,
        group: "Services",
        run: () => void runRestart(service.id),
      },
      {
        id: `${service.id}-clear`,
        label: `Clear logs ${service.name}`,
        group: "Logs",
        run: () => void clearLogs(service.id),
      },
    ]);

    const workspaceActions: PaletteAction[] = state.config.workspaces.map((workspace) => ({
      id: `ws-${workspace.id}`,
      label: `Open workspace ${workspace.name}`,
      group: "Workspaces",
      run: () => openWorkspace(workspace.id),
    }));

    const historyActions: PaletteAction[] = state.runnerHistory.slice(0, 8).map((item, index) => ({
      id: `history-${index}`,
      label: `Run: ${item.program} ${item.args.join(" ")}`,
      group: "Runner",
      run: () => {
        void executeRunner(item);
      },
    }));

    const modeActions: PaletteAction[] = [
      { id: "mode-all", label: "Mode: All", group: "Views", run: () => setDashboardMode("all") },
      { id: "mode-dev", label: "Mode: Dev", group: "Views", run: () => setDashboardMode("dev") },
      { id: "mode-multimedia", label: "Mode: Multimedia", group: "Views", run: () => setDashboardMode("multimedia") },
      { id: "mode-medical", label: "Mode: Medico", group: "Views", run: () => setDashboardMode("medical") },
    ];

    const bridgeCommands = [
      "/status",
      "/comandos",
      "/persona medico",
      "/persona dolphin",
      "/persona unholy",
      "/persona mytho",
      "/autorag on",
      "/autorag off",
      "/aider",
      "/restaurar all",
    ];

    const bridgeActions: PaletteAction[] = bridgeCommands.map((command) => ({
      id: `bridge-${command}`,
      label: command,
      group: "Bridge / WhatsApp",
      run: () => {
        navigator.clipboard
          .writeText(command)
          .then(() => toast.success(`Comando copiado: ${command}`))
          .catch(() => toast.error("No se pudo copiar comando"));
      },
    }));

    return [...serviceActions, ...workspaceActions, ...historyActions, ...modeActions, ...bridgeActions];
  }, [services, state.config.workspaces, state.runnerHistory]);

  return (
    <div className="controlroom-theme h-screen w-screen flex flex-col bg-background text-foreground overflow-hidden">
      <div className="cr-panel-header border-b border-border/45">
        <div className="min-w-0">
          <div className="cr-panel-title">ControlRoom IDE</div>
          <div className="cr-meta">Cmd+K · Panel de control para servicios y runner</div>
        </div>
        <div className="cr-toolbar">
          <div className="cr-toolbar rounded-md border border-border/50 bg-background/40 p-1">
            <Button
              size="sm"
              variant={dashboardMode === "all" ? "default" : "outline"}
              className={dashboardMode === "all" ? "cr-compact-btn controlroom-btn-neutral" : "cr-compact-btn"}
              onClick={() => setDashboardMode("all")}
            >
              All
            </Button>
            <Button
              size="sm"
              variant={dashboardMode === "dev" ? "default" : "outline"}
              className={dashboardMode === "dev" ? "cr-compact-btn controlroom-btn-start" : "cr-compact-btn"}
              onClick={() => setDashboardMode("dev")}
            >
              Dev
            </Button>
            <Button
              size="sm"
              variant={dashboardMode === "multimedia" ? "default" : "outline"}
              className={dashboardMode === "multimedia" ? "cr-compact-btn controlroom-btn-neutral" : "cr-compact-btn"}
              onClick={() => setDashboardMode("multimedia")}
            >
              Multimedia
            </Button>
            <Button
              size="sm"
              variant={dashboardMode === "medical" ? "default" : "outline"}
              className={dashboardMode === "medical" ? "cr-compact-btn controlroom-btn-start" : "cr-compact-btn"}
              onClick={() => setDashboardMode("medical")}
            >
              Medico
            </Button>
          </div>

          {experimentalServicesForMode.length > 0 ? (
            <div className="rounded-md border border-amber-500/40 bg-amber-500/10 px-2 py-1 text-[10px] uppercase text-amber-200">
              experimental on: {experimentalServicesForMode.length}
            </div>
          ) : null}

          <Button size="sm" variant="outline" className="cr-compact-btn" onClick={onSwitchClassic}>
            Switch to Classic
          </Button>
        </div>
      </div>

      <div className="flex-1 overflow-hidden p-2 pt-1">
        <div className="grid h-full min-h-0 gap-2 lg:grid-rows-[minmax(260px,32%)_minmax(0,68%)]">
          <div className="grid min-h-0 gap-2 lg:grid-cols-[20%_60%_20%]">
            <div className="min-h-0">
              <LiveEditorPanel
                selection={editorSelection}
                content={editorContent}
                loading={editorLoading}
                saving={editorSaving}
                dirty={editorDirty}
                error={editorError}
                onContentChange={(value) => {
                  setEditorContent(value);
                  setEditorDirty(true);
                }}
                onReload={reloadEditorFile}
                onSave={saveEditorFile}
              />
            </div>

            <div className="min-h-0 flex flex-col gap-2">
              <div className="h-[42%] min-h-[120px]">
                <NetworkGraphPanel
                  services={servicesForMode}
                  statuses={state.serviceStatuses}
                  feedEvents={feedEvents}
                  busStatus={busStatus}
                />
              </div>
              <div className="min-h-0 flex-1 overflow-hidden">
                <TopStatusBar
                  services={servicesForMode}
                  statuses={state.serviceStatuses}
                  busStatus={busStatus}
                  runtimeActivities={runtimeActivities}
                  telemetryByService={telemetryByService}
                  dashboardMode={dashboardMode}
                  refreshing={servicesRefreshing}
                  onRefresh={() => void refreshServicesAndStatuses({ includeDefinitions: true })}
                  onStart={(serviceId) => void runStart(serviceId)}
                  onStop={(serviceId) => void runStop(serviceId)}
                  onRestart={(serviceId) => void runRestart(serviceId)}
                />
              </div>
            </div>

            <div className="min-h-0">
              <OutputMirrorPanel services={services} logs={state.serviceLogs} />
            </div>
          </div>

          <div className="grid min-h-0 gap-2 lg:grid-cols-[20%_60%_20%]">
            <div className="min-h-0 flex flex-col gap-2">
              <div className="min-h-0 flex-[2.2]">
                <LeftSidebar
                  services={services}
                  logs={state.serviceLogs}
                  workspaces={state.config.workspaces}
                  activeWorkspaceId={state.activeWorkspaceId}
                  commits={commits}
                  commitsLoading={commitsLoading}
                  commitsError={commitsError}
                  onSelectWorkspace={(workspaceId) => dispatch({ type: "SET_ACTIVE_WORKSPACE", payload: workspaceId })}
                  onFetchWorkspaceEntries={fetchWorkspaceEntries}
                  onSelectWorkspaceFile={selectWorkspaceFile}
                  selectedWorkspaceFilePath={editorSelection?.relativePath ?? null}
                  onSelectService={(serviceId) => dispatch({ type: "SET_ACTIVE_SERVICE", payload: serviceId })}
                  onRefreshCommits={() => {
                    if (!state.activeWorkspaceId) return;
                    setCommitsLoading(true);
                    void controlroomGitCommits(state.activeWorkspaceId, state.config.git.maxCommits, 0)
                      .then((next) =>
                        dispatch({ type: "SET_COMMITS", payload: { workspaceId: state.activeWorkspaceId!, commits: next } }),
                      )
                      .catch((error) => setCommitsError(error instanceof Error ? error.message : String(error)))
                      .finally(() => setCommitsLoading(false));
                  }}
                  onStartAll={startAll}
                  onStopAll={stopAll}
                  onRestartAll={restartAll}
                  onClearAllLogs={clearAllLogs}
                  onExportServiceLogs={exportLogs}
                  onOpenWorkspace={openWorkspace}
                />
              </div>
              <div className="min-h-0 flex-1">
                <ChannelChatsPanel services={services} logs={state.serviceLogs} />
              </div>
            </div>

            <div className="min-h-0">
              <CenterPanelLayout
                services={servicesForMode}
                statuses={state.serviceStatuses}
                logs={state.serviceLogs}
                onClearServiceLogs={(serviceId) => void clearLogs(serviceId)}
                runnerHistory={state.runnerHistory}
                runnerOutputs={state.runnerOutputs}
                runnerExits={state.runnerExits}
                runnerMetaByRun={runnerMetaByRun}
                feedEvents={feedEvents}
                activeServiceId={state.activeServiceId}
                onSelectService={(serviceId) => dispatch({ type: "SET_ACTIVE_SERVICE", payload: serviceId })}
                onRunnerExecute={executeRunner}
                onRunnerCancel={cancelRunner}
              />
            </div>

            <div className="min-h-0">
              <ResizablePanelGroup direction="vertical" autoSaveId="controlroom-right-column-v2" className="h-full min-h-0">
                <ResizablePanel defaultSize={45} minSize={24}>
                  <VideoWallPanel
                    dashboardMode={dashboardMode}
                    isHighLoad={isHighLoad}
                    config={state.config.videoWall}
                    onVideoEvent={handleVideoFeedEvent}
                  />
                </ResizablePanel>

                <ResizableHandle />

                <ResizablePanel defaultSize={28} minSize={20}>
                  <AgentsPanel
                    services={servicesForMode}
                    statuses={state.serviceStatuses}
                    logs={state.serviceLogs}
                    realtimeByService={realtimeByService}
                    activeServiceId={state.activeServiceId}
                    onSelectService={(serviceId) => dispatch({ type: "SET_ACTIVE_SERVICE", payload: serviceId })}
                  />
                </ResizablePanel>

                <ResizableHandle />

                <ResizablePanel defaultSize={27} minSize={20}>
                  <LiveFeedPanel events={feedEvents} busStatus={busStatus} />
                </ResizablePanel>
              </ResizablePanelGroup>
            </div>
          </div>
        </div>
      </div>

      <CommandPalette shortcut={state.config.ui.shortcuts.commandPalette} actions={paletteActions} />
    </div>
  );
}

export function ControlRoomScreen(props: ControlRoomScreenProps) {
  const safeConfig = parseControlRoomConfig(props.config);
  return (
    <ControlRoomStoreProvider config={safeConfig}>
      <ControlRoomInner onSwitchClassic={props.onSwitchClassic} />
    </ControlRoomStoreProvider>
  );
}
