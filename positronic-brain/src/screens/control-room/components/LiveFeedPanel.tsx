import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useVirtualWindow } from "../perf/virtualization";
import type { ControlFeedEvent, FeedCategory, RealtimeBusStatus } from "../types";

const FILTERS: Array<{ key: "all" | FeedCategory; label: string }> = [
  { key: "all", label: "All" },
  { key: "service", label: "Services" },
  { key: "video", label: "Video" },
  { key: "agent", label: "Agents" },
  { key: "runner", label: "Runner" },
  { key: "system", label: "System" },
];

const ROW_HEIGHT = 62;

function severityClass(level: ControlFeedEvent["severity"]) {
  if (level === "error") return "text-rose-300";
  if (level === "warn") return "text-amber-300";
  return "text-foreground";
}

function busDotClass(state: RealtimeBusStatus["state"]) {
  if (state === "online") return "bg-emerald-500";
  if (state === "degraded") return "bg-amber-500";
  if (state === "offline") return "bg-rose-500";
  return "bg-slate-500";
}

export function LiveFeedPanel({
  events,
  busStatus,
}: {
  events: ControlFeedEvent[];
  busStatus: RealtimeBusStatus;
}) {
  const [filter, setFilter] = useState<"all" | FeedCategory>("all");
  const [query, setQuery] = useState("");
  const [isMinimized, setIsMinimized] = useState(false);
  const [viewportHeight, setViewportHeight] = useState(280);
  const [scrollTop, setScrollTop] = useState(0);
  const viewportRef = useRef<HTMLDivElement | null>(null);

  const filtered = useMemo(() => {
    const queryValue = query.trim().toLowerCase();
    return events.filter((event) => {
      const categoryOk = filter === "all" || event.category === filter;
      if (!categoryOk) return false;
      if (!queryValue) return true;
      return (
        event.message.toLowerCase().includes(queryValue) ||
        event.source.toLowerCase().includes(queryValue) ||
        String(event.correlationId || "").toLowerCase().includes(queryValue)
      );
    });
  }, [events, filter, query]);

  useEffect(() => {
    const node = viewportRef.current;
    if (!node) return;

    const update = () => setViewportHeight(node.clientHeight || 280);
    update();
    const observer = new ResizeObserver(update);
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  const virtual = useVirtualWindow({
    total: filtered.length,
    rowHeight: ROW_HEIGHT,
    viewportHeight,
    scrollTop,
    overscan: 10,
  });

  const visibleRows = useMemo(
    () => filtered.slice(virtual.start, virtual.end),
    [filtered, virtual.start, virtual.end],
  );

  return (
    <div className="h-full min-h-0 flex flex-col rounded-md border bg-card transition-all duration-300 ease-in-out">
      <div className="cr-panel-header">
        <div className="cr-toolbar">
          <button
            type="button"
            onClick={() => setIsMinimized((prev) => !prev)}
            className="rounded p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            title={isMinimized ? "Expand live feed panel" : "Minimize live feed panel"}
            aria-label={isMinimized ? "Expand live feed panel" : "Minimize live feed panel"}
          >
            {isMinimized ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
          </button>
          <div className="cr-panel-title">Live Feed</div>
        </div>
        <div className="cr-toolbar">
          {!isMinimized ? (
            <Badge variant="outline" className="cr-badge">
              Tauri events
            </Badge>
          ) : null}
          <Badge variant="secondary" className="cr-badge flex items-center gap-1">
            <span className={`h-2 w-2 rounded-full ${busDotClass(busStatus.state)}`} />
            {busStatus.state}
          </Badge>
        </div>
      </div>

      {!isMinimized ? (
        <>
          <div className="flex gap-1 border-b px-2 py-1">
            {FILTERS.map((tab) => (
              <Button
                key={tab.key}
                size="sm"
                variant={filter === tab.key ? "default" : "outline"}
                onClick={() => setFilter(tab.key)}
                className="cr-compact-btn"
              >
                {tab.label}
              </Button>
            ))}
          </div>
          <div className="border-b px-2 py-1">
            <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search feed" className="cr-compact-input" />
          </div>

          <div
            ref={viewportRef}
            className="min-h-0 flex-1 overflow-auto"
            onScroll={(event) => setScrollTop((event.currentTarget as HTMLDivElement).scrollTop)}
          >
            <div className="font-mono text-xs">
              <div style={{ height: virtual.offsetTop }} />
              {visibleRows.map((event) => (
                <div
                  key={event.id}
                  className={`m-2 rounded border border-border/60 bg-background/60 px-2 py-1 ${severityClass(event.severity)}`}
                  style={{ minHeight: ROW_HEIGHT - 8 }}
                >
                  <div className="flex items-center justify-between gap-2 text-[10px] text-muted-foreground">
                    <span>
                      [{new Date(event.ts).toLocaleTimeString()}] {event.category.toUpperCase()} · {event.source}
                    </span>
                    <span className="uppercase">{event.severity}</span>
                  </div>
                  <div className="mt-1 break-words">{event.message}</div>
                  {event.correlationId ? (
                    <div className="mt-1 text-[10px] text-muted-foreground">cid={event.correlationId}</div>
                  ) : null}
                </div>
              ))}
              <div style={{ height: virtual.offsetBottom }} />
              {filtered.length === 0 ? <div className="p-2 text-muted-foreground">No feed events yet.</div> : null}
            </div>
          </div>
        </>
      ) : (
        <div className="min-h-0 flex-1 overflow-auto">
          <div className="space-y-1 p-2 font-mono text-[11px]">
            {filtered.slice(0, 18).map((event) => (
              <div key={event.id} className={`rounded border border-border/60 bg-background/60 px-2 py-1 ${severityClass(event.severity)}`}>
                <div className="flex items-center gap-2">
                  <span className={`h-2 w-2 rounded-full ${event.severity === "error" ? "bg-rose-500" : event.severity === "warn" ? "bg-amber-500" : "bg-emerald-500"}`} />
                  <span className="truncate text-[10px] uppercase text-muted-foreground">{event.category}</span>
                </div>
                <div className="mt-1 line-clamp-2">{event.message}</div>
              </div>
            ))}
            {filtered.length === 0 ? <div className="text-muted-foreground">No events</div> : null}
          </div>
        </div>
      )}
    </div>
  );
}
