import { AspectRatio } from "@/components/ui/aspect-ratio";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import {
  controlroomVideoLaunchNative,
  controlroomVideoSnapshotAnalyze,
} from "../services/controlRoomApi";
import type { DashboardMode, VideoEvent, VideoFeedKind, VideoWallConfig } from "../types";

type PersistedVideoFeedKind = Exclude<VideoFeedKind, "auto">;

interface StoredFeed {
  id: string;
  name: string;
  kind: PersistedVideoFeedKind;
  url?: string;
  urlRedacted: string;
  requiresAuth: boolean;
  manualPaused?: boolean;
  launcherId?: string;
}

interface RuntimeFeed extends StoredFeed {
  resolvedUrl?: string;
  paused: boolean;
  autoPauseReasons: string[];
}

const VIDEO_WALL_FEEDS_STORAGE_KEY = "controlroom.video-wall.feeds.v2";

const DEFAULT_VIDEO_WALL_CONFIG: VideoWallConfig = {
  enabled: true,
  maxActiveFeeds: 2,
  autoPause: {
    whenModeNotMultimedia: true,
    whenPanelHidden: true,
    whenAppHidden: true,
    whenHighLoad: true,
    highLoadLatencyMs: 350,
    highLoadConsecutiveSamples: 3,
  },
  nativeLaunchers: [],
  snapshot: {
    enabled: false,
    timeoutMs: 20000,
  },
};

function inferFeedKind(url: string): PersistedVideoFeedKind {
  const value = String(url || "").trim().toLowerCase();
  if (value.startsWith("rtsp://")) return "rtsp";
  if (value.includes(".m3u8")) return "hls";
  if (/\.(jpe?g|png|webp|gif)(\?|$)/.test(value)) return "image";
  if (value.includes("mjpeg") || value.includes("snapshot")) return "mjpeg";
  return "web";
}

function hasInlineCredentials(url: string): boolean {
  const value = String(url || "").trim();
  if (!value) return false;
  try {
    const parsed = new URL(value);
    return Boolean(parsed.username || parsed.password);
  } catch {
    return /:\/\/[^\s/@:]+:[^\s/@]*@/i.test(value);
  }
}

function redactUrl(url: string): string {
  const value = String(url || "").trim();
  if (!value) return "";
  try {
    const parsed = new URL(value);
    if (parsed.username || parsed.password) {
      parsed.username = "***";
      parsed.password = "***";
    }
    return parsed.toString();
  } catch {
    return value.replace(/(:\/\/)([^\s/@:]+):([^\s/@]*)@/i, "$1***:***@");
  }
}

function parseStoredFeeds(raw: string | null): StoredFeed[] {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];

    const feeds = parsed
      .map((entry): StoredFeed | null => {
        const id = String(entry?.id || "").trim();
        const name = String(entry?.name || "").trim();
        const url = typeof entry?.url === "string" ? String(entry.url).trim() : "";
        const urlRedacted = String(entry?.urlRedacted || url || "").trim();
        const declaredKind = String(entry?.kind || "").trim().toLowerCase();
        const kind = ["rtsp", "hls", "mjpeg", "image", "web"].includes(declaredKind)
          ? (declaredKind as PersistedVideoFeedKind)
          : inferFeedKind(url || urlRedacted);
        const requiresAuth = Boolean(entry?.requiresAuth);
        if (!id || !urlRedacted) return null;

        const feed: StoredFeed = {
          id,
          name: name || `Feed ${id.slice(0, 4)}`,
          kind,
          urlRedacted,
          requiresAuth,
          manualPaused: Boolean(entry?.manualPaused),
          launcherId:
            typeof entry?.launcherId === "string"
              ? String(entry.launcherId).trim() || undefined
              : undefined,
        };

        if (url) {
          feed.url = url;
        }

        return feed;
      })
      .filter((entry): entry is StoredFeed => entry !== null);

    return feeds;
  } catch {
    return [];
  }
}

function mergeVideoConfig(config?: VideoWallConfig): VideoWallConfig {
  return {
    enabled: config?.enabled ?? DEFAULT_VIDEO_WALL_CONFIG.enabled,
    maxActiveFeeds: Math.max(1, Number(config?.maxActiveFeeds ?? DEFAULT_VIDEO_WALL_CONFIG.maxActiveFeeds)),
    autoPause: {
      ...DEFAULT_VIDEO_WALL_CONFIG.autoPause,
      ...(config?.autoPause ?? {}),
      highLoadLatencyMs: Math.max(
        100,
        Number(config?.autoPause?.highLoadLatencyMs ?? DEFAULT_VIDEO_WALL_CONFIG.autoPause.highLoadLatencyMs),
      ),
      highLoadConsecutiveSamples: Math.max(
        1,
        Number(
          config?.autoPause?.highLoadConsecutiveSamples ??
            DEFAULT_VIDEO_WALL_CONFIG.autoPause.highLoadConsecutiveSamples,
        ),
      ),
    },
    nativeLaunchers: Array.isArray(config?.nativeLaunchers)
      ? config!.nativeLaunchers.filter((launcher) => Boolean(launcher?.id))
      : [],
    snapshot: {
      ...DEFAULT_VIDEO_WALL_CONFIG.snapshot,
      ...(config?.snapshot ?? {}),
      timeoutMs: Math.max(5000, Number(config?.snapshot?.timeoutMs ?? DEFAULT_VIDEO_WALL_CONFIG.snapshot.timeoutMs)),
    },
  };
}

async function openFeedExternally(url: string) {
  try {
    const { openPath } = await import("@tauri-apps/plugin-opener");
    await openPath(url);
  } catch (error) {
    toast.error(`No se pudo abrir feed: ${error instanceof Error ? error.message : String(error)}`);
  }
}

function buildVideoEvent(
  source: string,
  severity: VideoEvent["severity"],
  message: string,
  feedId?: string,
  kind?: string,
): VideoEvent {
  return {
    ts: Date.now(),
    source,
    severity,
    message,
    feedId,
    kind,
  };
}

interface FeedTileProps {
  feed: RuntimeFeed;
  busy: boolean;
  snapshotSummary?: string;
  snapshotEnabled: boolean;
  canPictureInPicture: boolean;
  onToggleManualPause: (feedId: string) => void;
  onSetSessionUrl: (feedId: string) => void;
  onRequestPictureInPicture: (feedId: string) => void;
  onSnapshot: (feedId: string) => void;
  onOpenNative: (feedId: string) => void;
  onRemove: (feedId: string) => void;
  onDragStart: (feedId: string, event: React.DragEvent<HTMLDivElement>) => void;
  onDragEnter: (feedId: string, event: React.DragEvent<HTMLDivElement>) => void;
  onDrop: (feedId: string, event: React.DragEvent<HTMLDivElement>) => void;
  onDragEnd: () => void;
  isDragging: boolean;
  isDropTarget: boolean;
  setVideoRef: (feedId: string, el: HTMLVideoElement | null) => void;
  setImageRef: (feedId: string, el: HTMLImageElement | null) => void;
  onTileVisibilityChange: (feedId: string, isVisible: boolean) => void;
}

function FeedTile({
  feed,
  busy,
  snapshotSummary,
  snapshotEnabled,
  canPictureInPicture,
  onToggleManualPause,
  onSetSessionUrl,
  onRequestPictureInPicture,
  onSnapshot,
  onOpenNative,
  onRemove,
  onDragStart,
  onDragEnter,
  onDrop,
  onDragEnd,
  isDragging,
  isDropTarget,
  setVideoRef,
  setImageRef,
  onTileVisibilityChange,
}: FeedTileProps) {
  const tileRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const node = tileRef.current;
    if (!node || typeof window === "undefined") return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        onTileVisibilityChange(feed.id, entry.isIntersecting);
      },
      {
        threshold: 0.1,
      },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [feed.id, onTileVisibilityChange]);

  const isInlineImage = feed.kind === "image" || feed.kind === "mjpeg";
  const isInlineVideo = feed.kind === "hls";
  const isRtsp = feed.kind === "rtsp";
  const isMissingAuth = feed.requiresAuth && !feed.resolvedUrl;

  return (
    <div
      ref={tileRef}
      className={`controlroom-card group flex min-h-0 flex-col rounded-md border border-border/55 bg-card/55 transition-all duration-150 ${
        isDragging ? "opacity-70" : ""
      } ${isDropTarget ? "ring-1 ring-primary/70" : ""}`}
      draggable
      onDragStart={(event) => onDragStart(feed.id, event)}
      onDragEnter={(event) => onDragEnter(feed.id, event)}
      onDragOver={(event) => {
        event.preventDefault();
        event.dataTransfer.dropEffect = "move";
      }}
      onDrop={(event) => onDrop(feed.id, event)}
      onDragEnd={onDragEnd}
    >
      <div className="flex items-center justify-between gap-2 border-b border-border/45 px-2 py-1.5">
        <div className="min-w-0">
          <div className="truncate text-xs font-semibold text-foreground">{feed.name}</div>
          <div className="truncate text-[10px] text-muted-foreground">{feed.urlRedacted}</div>
        </div>
        <div className="flex items-center gap-1">
          <Badge variant="outline" className="text-[10px] uppercase">
            {feed.kind}
          </Badge>
          {feed.paused ? (
            <Badge variant="secondary" className="text-[10px] uppercase">
              paused
            </Badge>
          ) : (
            <Badge variant="default" className="text-[10px] uppercase">
              live
            </Badge>
          )}
        </div>
      </div>

      <div className="min-h-0 flex-1 p-2">
        <AspectRatio ratio={16 / 9} className="relative h-full w-full">
          <div
            className={`pointer-events-none absolute left-2 right-2 top-2 z-20 transition-opacity duration-150 ${
              feed.paused || isMissingAuth
                ? "opacity-100"
                : "opacity-0 group-hover:opacity-100 group-focus-within:opacity-100"
            }`}
          >
            <div className="pointer-events-auto flex flex-wrap items-center gap-1 rounded-md border border-border/55 bg-background/70 p-1 backdrop-blur-sm">
              <Button size="sm" variant="outline" onClick={() => onToggleManualPause(feed.id)}>
                {feed.manualPaused ? "Resume" : "Pause"}
              </Button>

              <Button
                size="sm"
                variant="outline"
                onClick={() => void openFeedExternally(feed.resolvedUrl || feed.urlRedacted)}
                disabled={!feed.resolvedUrl && isMissingAuth}
              >
                Open
              </Button>

              <Button size="sm" variant="outline" onClick={() => onOpenNative(feed.id)} disabled={busy}>
                Open Native
              </Button>

              <Button
                size="sm"
                variant="outline"
                onClick={() => onRequestPictureInPicture(feed.id)}
                disabled={!canPictureInPicture || feed.paused || !feed.resolvedUrl}
              >
                PiP
              </Button>

              <Button
                size="sm"
                variant="outline"
                onClick={() => onSnapshot(feed.id)}
                disabled={!snapshotEnabled || busy || feed.paused || !feed.resolvedUrl}
              >
                Snapshot AI
              </Button>

              {isMissingAuth ? (
                <Button
                  size="sm"
                  variant="outline"
                  className="controlroom-btn-start"
                  onClick={() => onSetSessionUrl(feed.id)}
                >
                  Set URL
                </Button>
              ) : null}

              <Button size="sm" variant="outline" className="controlroom-btn-neutral" onClick={() => onRemove(feed.id)}>
                Remove
              </Button>
            </div>
          </div>

          {feed.paused ? (
            <div className="flex h-full w-full flex-col items-center justify-center rounded-md border border-dashed border-border/55 bg-background/40 p-3 text-center">
              <div className="text-xs font-semibold text-foreground">Stream paused</div>
              {feed.autoPauseReasons.length > 0 ? (
                <div className="mt-1 text-[11px] text-muted-foreground">{feed.autoPauseReasons.join(" · ")}</div>
              ) : null}
            </div>
          ) : isMissingAuth ? (
            <div className="flex h-full w-full flex-col items-center justify-center rounded-md border border-dashed border-amber-400/40 bg-amber-500/10 p-3 text-center">
              <div className="text-xs font-semibold text-amber-200">AUTH NEEDED</div>
              <div className="mt-1 text-[11px] text-amber-100/80">Este feed requiere URL en esta sesion.</div>
            </div>
          ) : isInlineImage ? (
            <img
              src={feed.resolvedUrl}
              alt={feed.name}
              className="h-full w-full rounded-md border border-border/45 object-cover"
              loading="lazy"
              ref={(el) => setImageRef(feed.id, el)}
            />
          ) : isInlineVideo ? (
            <video
              src={feed.resolvedUrl}
              controls
              muted
              playsInline
              className="h-full w-full rounded-md border border-border/45 bg-background/60 object-cover"
              ref={(el) => setVideoRef(feed.id, el)}
            />
          ) : (
            <div className="flex h-full w-full flex-col items-center justify-center rounded-md border border-dashed border-border/55 bg-background/40 px-3 text-center text-xs text-muted-foreground">
              {isRtsp ? (
                <div>
                  <div className="font-semibold text-foreground">RTSP no embebible en WebView</div>
                  <div className="mt-1">Usa Open Native para baja latencia o Open externo.</div>
                </div>
              ) : (
                <div>
                  <div className="font-semibold text-foreground">Feed web externo</div>
                  <div className="mt-1">Usa Open para visualizar en app/navegador externo.</div>
                </div>
              )}
            </div>
          )}

          {snapshotSummary ? (
            <div className="pointer-events-none absolute bottom-2 left-2 right-2 z-20 rounded-md border border-emerald-500/35 bg-black/55 px-2 py-1 text-[11px] text-emerald-300 backdrop-blur-sm">
              {snapshotSummary}
            </div>
          ) : null}
        </AspectRatio>
      </div>
    </div>
  );
}

export function VideoWallPanel({
  dashboardMode,
  isHighLoad,
  config,
  onVideoEvent,
}: {
  dashboardMode: DashboardMode;
  isHighLoad: boolean;
  config?: VideoWallConfig;
  onVideoEvent?: (event: VideoEvent) => void;
}) {
  const mergedConfig = useMemo(() => mergeVideoConfig(config), [config]);
  const panelRef = useRef<HTMLDivElement | null>(null);
  const videoRefs = useRef<Record<string, HTMLVideoElement | null>>({});
  const imageRefs = useRef<Record<string, HTMLImageElement | null>>({});
  const previousPausedRef = useRef<Record<string, boolean>>({});

  const [feeds, setFeeds] = useState<StoredFeed[]>([]);
  const [sessionUrls, setSessionUrls] = useState<Record<string, string>>({});
  const [snapshotByFeed, setSnapshotByFeed] = useState<Record<string, string>>({});
  const [busyByFeed, setBusyByFeed] = useState<Record<string, boolean>>({});
  const [tileVisibleByFeed, setTileVisibleByFeed] = useState<Record<string, boolean>>({});

  const [draftName, setDraftName] = useState("");
  const [draftUrl, setDraftUrl] = useState("");
  const [draftKind, setDraftKind] = useState<VideoFeedKind>("auto");
  const [draftLauncherId, setDraftLauncherId] = useState("");

  const [panelVisible, setPanelVisible] = useState(true);
  const [appHidden, setAppHidden] = useState(false);
  const [draggingFeedId, setDraggingFeedId] = useState<string | null>(null);
  const [dragOverFeedId, setDragOverFeedId] = useState<string | null>(null);

  const emitLocalEvent = useCallback(
    (event: VideoEvent) => {
      onVideoEvent?.(event);
    },
    [onVideoEvent],
  );

  useEffect(() => {
    if (typeof window === "undefined") return;
    const restored = parseStoredFeeds(window.localStorage.getItem(VIDEO_WALL_FEEDS_STORAGE_KEY));
    setFeeds(restored);

    const restoredSession: Record<string, string> = {};
    restored.forEach((feed) => {
      if (feed.url && !feed.requiresAuth) {
        restoredSession[feed.id] = feed.url;
      }
    });
    setSessionUrls(restoredSession);
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(VIDEO_WALL_FEEDS_STORAGE_KEY, JSON.stringify(feeds));
  }, [feeds]);

  useEffect(() => {
    const handler = () => {
      setAppHidden(document.visibilityState === "hidden");
    };
    handler();
    document.addEventListener("visibilitychange", handler);
    return () => document.removeEventListener("visibilitychange", handler);
  }, []);

  useEffect(() => {
    const node = panelRef.current;
    if (!node || typeof window === "undefined") return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        setPanelVisible(Boolean(entry?.isIntersecting));
      },
      {
        threshold: 0.05,
      },
    );

    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  const runtimeFeeds = useMemo(() => {
    const modePaused = mergedConfig.autoPause.whenModeNotMultimedia && dashboardMode !== "multimedia";
    const panelHiddenPaused = mergedConfig.autoPause.whenPanelHidden && !panelVisible;
    const appHiddenPaused = mergedConfig.autoPause.whenAppHidden && appHidden;
    const highLoadPaused = mergedConfig.autoPause.whenHighLoad && isHighLoad;

    return feeds.map((feed, index) => {
      const resolvedUrl = sessionUrls[feed.id] || feed.url;
      const reasons: string[] = [];

      if (modePaused) reasons.push("MODE");
      if (panelHiddenPaused) reasons.push("PANEL_HIDDEN");
      if (appHiddenPaused) reasons.push("APP_HIDDEN");
      if (highLoadPaused) reasons.push("HIGH_LOAD");
      if (mergedConfig.autoPause.whenPanelHidden && tileVisibleByFeed[feed.id] === false) reasons.push("OFFSCREEN");
      if (index >= mergedConfig.maxActiveFeeds) reasons.push("BUDGET");
      if (feed.requiresAuth && !resolvedUrl) reasons.push("AUTH_NEEDED");

      const paused = Boolean(feed.manualPaused) || reasons.length > 0;

      return {
        ...feed,
        resolvedUrl,
        paused,
        autoPauseReasons: reasons,
      } satisfies RuntimeFeed;
    });
  }, [
    appHidden,
    dashboardMode,
    feeds,
    isHighLoad,
    mergedConfig.autoPause.whenAppHidden,
    mergedConfig.autoPause.whenHighLoad,
    mergedConfig.autoPause.whenModeNotMultimedia,
    mergedConfig.autoPause.whenPanelHidden,
    mergedConfig.maxActiveFeeds,
    panelVisible,
    sessionUrls,
    tileVisibleByFeed,
  ]);

  useEffect(() => {
    const nextPausedMap: Record<string, boolean> = {};
    runtimeFeeds.forEach((feed) => {
      const prevPaused = previousPausedRef.current[feed.id];
      nextPausedMap[feed.id] = feed.paused;
      if (prevPaused === undefined || prevPaused === feed.paused) return;

      emitLocalEvent(
        buildVideoEvent(
          "video-wall",
          feed.paused ? "warn" : "info",
          `${feed.name}: ${feed.paused ? "paused" : "resumed"}${feed.autoPauseReasons.length > 0 ? ` (${feed.autoPauseReasons.join(",")})` : ""}`,
          feed.id,
          feed.paused ? "pause" : "resume",
        ),
      );
    });
    previousPausedRef.current = nextPausedMap;
  }, [emitLocalEvent, runtimeFeeds]);

  function reorderFeeds(sourceFeedId: string, targetFeedId: string) {
    if (sourceFeedId === targetFeedId) return;
    setFeeds((prev) => {
      const next = [...prev];
      const sourceIndex = next.findIndex((feed) => feed.id === sourceFeedId);
      const targetIndex = next.findIndex((feed) => feed.id === targetFeedId);
      if (sourceIndex < 0 || targetIndex < 0) return next;
      const [moved] = next.splice(sourceIndex, 1);
      next.splice(targetIndex, 0, moved);
      return next;
    });
  }

  function addFeed() {
    const url = draftUrl.trim();
    if (!url) {
      toast.error("Necesitas URL del feed");
      return;
    }

    const kind = draftKind === "auto" ? inferFeedKind(url) : (draftKind as PersistedVideoFeedKind);
    const hasAuth = hasInlineCredentials(url);
    const id = `${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;
    const feed: StoredFeed = {
      id,
      name: draftName.trim() || `Feed ${feeds.length + 1}`,
      kind,
      url: hasAuth ? undefined : url,
      urlRedacted: redactUrl(url),
      requiresAuth: hasAuth,
      manualPaused: false,
      launcherId: draftLauncherId.trim() || undefined,
    };

    setFeeds((prev) => [...prev, feed]);
    setSessionUrls((prev) => ({
      ...prev,
      [id]: url,
    }));

    setDraftName("");
    setDraftUrl("");
    setDraftKind("auto");

    emitLocalEvent(
      buildVideoEvent(
        "video-wall",
        hasAuth ? "warn" : "info",
        `${feed.name} added (${feed.kind})${hasAuth ? " · auth not persisted" : ""}`,
        id,
        "feed-add",
      ),
    );
  }

  function removeFeed(feedId: string) {
    const feed = feeds.find((item) => item.id === feedId);
    setFeeds((prev) => prev.filter((item) => item.id !== feedId));
    setSessionUrls((prev) => {
      const next = { ...prev };
      delete next[feedId];
      return next;
    });
    setSnapshotByFeed((prev) => {
      const next = { ...prev };
      delete next[feedId];
      return next;
    });

    if (feed) {
      emitLocalEvent(buildVideoEvent("video-wall", "info", `${feed.name} removed`, feedId, "feed-remove"));
    }
  }

  function toggleManualPause(feedId: string) {
    setFeeds((prev) =>
      prev.map((feed) =>
        feed.id === feedId
          ? {
              ...feed,
              manualPaused: !feed.manualPaused,
            }
          : feed,
      ),
    );
  }

  function setSessionUrl(feedId: string) {
    const feed = feeds.find((item) => item.id === feedId);
    if (!feed) return;

    const input = window.prompt(`URL para ${feed.name}`, "");
    if (!input) return;

    const nextUrl = input.trim();
    if (!nextUrl) return;

    const hasAuth = hasInlineCredentials(nextUrl);
    const redacted = redactUrl(nextUrl);
    const kind = inferFeedKind(nextUrl);

    setFeeds((prev) =>
      prev.map((item) =>
        item.id === feedId
          ? {
              ...item,
              kind,
              urlRedacted: redacted,
              requiresAuth: hasAuth,
              url: hasAuth ? undefined : nextUrl,
            }
          : item,
      ),
    );

    setSessionUrls((prev) => ({
      ...prev,
      [feedId]: nextUrl,
    }));

    emitLocalEvent(
      buildVideoEvent(
        "video-wall",
        "info",
        `${feed.name}: session URL updated${hasAuth ? " (auth protected)" : ""}`,
        feedId,
        "auth-update",
      ),
    );
  }

  function setVideoRef(feedId: string, element: HTMLVideoElement | null) {
    videoRefs.current[feedId] = element;
  }

  function setImageRef(feedId: string, element: HTMLImageElement | null) {
    imageRefs.current[feedId] = element;
  }

  function setTileVisibility(feedId: string, isVisible: boolean) {
    setTileVisibleByFeed((prev) => ({
      ...prev,
      [feedId]: isVisible,
    }));
  }

  async function requestPictureInPicture(feedId: string) {
    const video = videoRefs.current[feedId];
    if (!video) {
      toast.error("PiP solo disponible en feeds video embebidos");
      return;
    }

    const candidate = video as HTMLVideoElement & {
      requestPictureInPicture?: () => Promise<unknown>;
    };

    if (typeof candidate.requestPictureInPicture !== "function") {
      toast.error("PiP no soportado en este feed/entorno");
      return;
    }

    try {
      if (video.paused) {
        await video.play().catch(() => null);
      }
      await candidate.requestPictureInPicture();
      emitLocalEvent(buildVideoEvent("video-wall", "info", "PiP activated", feedId, "pip"));
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      toast.error(`PiP error: ${message}`);
      emitLocalEvent(buildVideoEvent("video-wall", "error", `PiP error: ${message}`, feedId, "pip"));
    }
  }

  async function launchNative(feedId: string) {
    const feed = runtimeFeeds.find((item) => item.id === feedId);
    if (!feed) return;

    const launcherId = feed.launcherId || mergedConfig.nativeLaunchers[0]?.id;
    if (!launcherId) {
      toast.error("No hay launcher nativo configurado");
      emitLocalEvent(buildVideoEvent("video-wall", "error", "No native launcher configured", feedId, "native-launch"));
      return;
    }

    setBusyByFeed((prev) => ({ ...prev, [feedId]: true }));
    try {
      const result = await controlroomVideoLaunchNative({
        launcherId,
        feedId: feed.id,
        feedName: feed.name,
        feedUrl: feed.resolvedUrl,
      });

      if (result.ok) {
        toast.success(result.message);
        emitLocalEvent(buildVideoEvent("video-wall", "info", result.message, feedId, "native-launch"));
      } else {
        toast.error(result.message);
        emitLocalEvent(buildVideoEvent("video-wall", "error", result.message, feedId, "native-launch"));
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      toast.error(`Native launch failed: ${message}`);
      emitLocalEvent(buildVideoEvent("video-wall", "error", message, feedId, "native-launch"));
    } finally {
      setBusyByFeed((prev) => ({ ...prev, [feedId]: false }));
    }
  }

  async function snapshotFeed(feedId: string) {
    if (!mergedConfig.snapshot.enabled) {
      toast.error("Snapshot AI desactivado en config");
      return;
    }

    const feed = runtimeFeeds.find((item) => item.id === feedId);
    if (!feed || !feed.resolvedUrl) {
      toast.error("Feed sin URL activa para snapshot");
      return;
    }

    const video = videoRefs.current[feedId];
    const image = imageRefs.current[feedId];

    let dataUrl = "";

    try {
      const canvas = document.createElement("canvas");
      const context = canvas.getContext("2d");
      if (!context) {
        toast.error("No se pudo crear contexto de canvas");
        return;
      }

      if (video && video.videoWidth > 0 && video.videoHeight > 0) {
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        context.drawImage(video, 0, 0, canvas.width, canvas.height);
      } else if (image && image.naturalWidth > 0 && image.naturalHeight > 0) {
        canvas.width = image.naturalWidth;
        canvas.height = image.naturalHeight;
        context.drawImage(image, 0, 0, canvas.width, canvas.height);
      } else {
        toast.error("No hay frame disponible para snapshot");
        return;
      }

      dataUrl = canvas.toDataURL("image/png");
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      toast.error(`Snapshot capture failed: ${message}`);
      emitLocalEvent(buildVideoEvent("video-wall", "error", message, feedId, "snapshot"));
      return;
    }

    setBusyByFeed((prev) => ({ ...prev, [feedId]: true }));
    try {
      const result = await controlroomVideoSnapshotAnalyze({
        feedId,
        feedName: feed.name,
        imageBase64: dataUrl,
      });

      if (!result.ok) {
        toast.error(result.message || "Snapshot analysis failed");
        emitLocalEvent(
          buildVideoEvent(
            "video-wall",
            "error",
            result.message || "Snapshot analysis failed",
            feedId,
            "snapshot",
          ),
        );
        return;
      }

      const summary = (result.summary || "Sin resumen").trim();
      setSnapshotByFeed((prev) => ({ ...prev, [feedId]: summary }));
      emitLocalEvent(buildVideoEvent("video-wall", "info", summary, feedId, "snapshot"));
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      toast.error(`Snapshot AI failed: ${message}`);
      emitLocalEvent(buildVideoEvent("video-wall", "error", message, feedId, "snapshot"));
    } finally {
      setBusyByFeed((prev) => ({ ...prev, [feedId]: false }));
    }
  }

  function addTapoTemplate() {
    setDraftName("Tapo Cam");
    setDraftUrl("rtsp://usuario:password@ip:554/stream1");
    setDraftKind("rtsp");
    if (!draftLauncherId && mergedConfig.nativeLaunchers.length > 0) {
      setDraftLauncherId(mergedConfig.nativeLaunchers[0].id);
    }
  }

  if (!mergedConfig.enabled) {
    return (
      <div className="controlroom-card flex h-full min-h-0 flex-col rounded-md border border-border/50 bg-card/35">
        <div className="flex h-full min-h-[220px] flex-col items-center justify-center p-3 text-center text-xs text-muted-foreground">
          <div className="text-sm font-semibold text-foreground">Video Wall disabled</div>
          <div className="mt-1">Activalo en `videoWall.enabled=true` en la config.</div>
        </div>
      </div>
    );
  }

  return (
    <div ref={panelRef} className="controlroom-card flex h-full min-h-0 flex-col rounded-md border border-border/50 bg-card/35">
      <div className="flex items-center justify-between border-b border-border/45 px-3 py-2 text-xs text-muted-foreground">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold tracking-tight text-foreground">Video Wall</span>
          <Badge variant="outline" className="text-[10px] uppercase">
            {runtimeFeeds.length} feed(s)
          </Badge>
          <Badge variant="secondary" className="text-[10px] uppercase">
            max active {mergedConfig.maxActiveFeeds}
          </Badge>
          {dashboardMode !== "multimedia" ? (
            <Badge variant="secondary" className="text-[10px] uppercase">
              mode paused
            </Badge>
          ) : null}
          {isHighLoad ? (
            <Badge variant="destructive" className="text-[10px] uppercase">
              high load
            </Badge>
          ) : null}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 border-b border-border/45 px-2 py-2">
        <Input
          value={draftName}
          onChange={(event) => setDraftName(event.target.value)}
          placeholder="Nombre"
          className="h-7 w-[130px]"
        />
        <Input
          value={draftUrl}
          onChange={(event) => setDraftUrl(event.target.value)}
          placeholder="URL (rtsp/http/mjpeg/hls)"
          className="h-7 min-w-[260px] flex-1"
        />
        <select
          value={draftKind}
          onChange={(event) => setDraftKind(event.target.value as VideoFeedKind)}
          className="h-7 rounded-md border border-input bg-background px-2 text-xs"
        >
          <option value="auto">auto</option>
          <option value="rtsp">rtsp</option>
          <option value="hls">hls</option>
          <option value="mjpeg">mjpeg</option>
          <option value="image">image</option>
          <option value="web">web</option>
        </select>
        <select
          value={draftLauncherId}
          onChange={(event) => setDraftLauncherId(event.target.value)}
          className="h-7 rounded-md border border-input bg-background px-2 text-xs"
        >
          <option value="">launcher auto</option>
          {mergedConfig.nativeLaunchers.map((launcher) => (
            <option key={launcher.id} value={launcher.id}>
              {launcher.name}
            </option>
          ))}
        </select>
        <Button size="sm" variant="outline" onClick={addFeed}>
          Add
        </Button>
        <Button size="sm" variant="outline" onClick={addTapoTemplate}>
          Tapo template
        </Button>
      </div>

      <ScrollArea className="min-h-0 flex-1">
        {runtimeFeeds.length === 0 ? (
          <div className="flex h-full min-h-[220px] flex-col items-center justify-center p-3 text-center text-xs text-muted-foreground">
            <div className="text-sm font-semibold text-foreground">Sin feeds todavia</div>
            <div className="mt-1">Anade camaras y se repartirán automaticamente en mosaico adaptativo.</div>
          </div>
        ) : (
          <div
            className="grid gap-2 p-2"
            style={{
              gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
              gridAutoRows: "minmax(260px, auto)",
            }}
          >
            {runtimeFeeds.map((feed) => (
              <FeedTile
                key={feed.id}
                feed={feed}
                busy={Boolean(busyByFeed[feed.id])}
                snapshotSummary={snapshotByFeed[feed.id]}
                snapshotEnabled={mergedConfig.snapshot.enabled}
                canPictureInPicture={feed.kind === "hls"}
                onToggleManualPause={toggleManualPause}
                onSetSessionUrl={setSessionUrl}
                onRequestPictureInPicture={requestPictureInPicture}
                onSnapshot={snapshotFeed}
                onOpenNative={launchNative}
                onRemove={removeFeed}
                onDragStart={(feedId, event) => {
                  setDraggingFeedId(feedId);
                  setDragOverFeedId(feedId);
                  event.dataTransfer.effectAllowed = "move";
                  event.dataTransfer.setData("text/plain", feedId);
                }}
                onDragEnter={(feedId, event) => {
                  event.preventDefault();
                  if (!draggingFeedId || draggingFeedId === feedId) return;
                  setDragOverFeedId(feedId);
                }}
                onDrop={(feedId, event) => {
                  event.preventDefault();
                  const sourceId = draggingFeedId || event.dataTransfer.getData("text/plain");
                  if (!sourceId) return;
                  reorderFeeds(sourceId, feedId);
                  setDraggingFeedId(null);
                  setDragOverFeedId(null);
                }}
                onDragEnd={() => {
                  setDraggingFeedId(null);
                  setDragOverFeedId(null);
                }}
                isDragging={draggingFeedId === feed.id}
                isDropTarget={dragOverFeedId === feed.id && draggingFeedId !== feed.id}
                setVideoRef={setVideoRef}
                setImageRef={setImageRef}
                onTileVisibilityChange={setTileVisibility}
              />
            ))}
          </div>
        )}
      </ScrollArea>
    </div>
  );
}
