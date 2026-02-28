import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useVirtualWindow } from "../perf/virtualization";
import type { ServiceConfig, ServiceLogEvent, ServiceRealtimeMeta, ServiceStatus } from "../types";

type AgentFilter = "all" | "running" | "attention" | "stopped";

const STALE_MS = 15000;
const FILTERS: Array<{ id: AgentFilter; label: string }> = [
  { id: "all", label: "all" },
  { id: "running", label: "running" },
  { id: "attention", label: "attention" },
  { id: "stopped", label: "stopped" },
];

const ROW_HEIGHT_EXPANDED = 204;
const ROW_HEIGHT_MINIMIZED = 34;

function stateDotClass(state: string) {
  if (state === "running") return "bg-emerald-500";
  if (state === "error") return "bg-rose-500";
  if (state === "starting" || state === "stopping") return "bg-amber-500";
  return "bg-zinc-500";
}

function statusBadgeVariant(state: string): "default" | "secondary" | "destructive" | "outline" {
  if (state === "running") return "default";
  if (state === "error") return "destructive";
  if (state === "starting" || state === "stopping") return "secondary";
  return "outline";
}

function formatUptime(seconds?: number | null) {
  if (!seconds || seconds <= 0) return "--";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

function formatAge(ts?: number) {
  if (!ts) return "--";
  const delta = Math.max(0, Date.now() - ts);
  if (delta < 1000) return `${delta}ms`;
  if (delta < 60000) return `${Math.floor(delta / 1000)}s`;
  return `${Math.floor(delta / 60000)}m`;
}

const STATE_PRIORITY: Record<string, number> = {
  error: 0,
  running: 1,
  starting: 2,
  stopping: 3,
  stopped: 4,
};

export function AgentsPanel({
  services,
  statuses,
  logs,
  realtimeByService,
  activeServiceId,
  onSelectService,
}: {
  services: ServiceConfig[];
  statuses: Record<string, ServiceStatus>;
  logs: Record<string, ServiceLogEvent[]>;
  realtimeByService: Record<string, ServiceRealtimeMeta>;
  activeServiceId: string | null;
  onSelectService: (serviceId: string) => void;
}) {
  const [filter, setFilter] = useState<AgentFilter>("all");
  const [query, setQuery] = useState("");
  const [isMinimized, setIsMinimized] = useState(false);
  const [viewportHeight, setViewportHeight] = useState(280);
  const [scrollTop, setScrollTop] = useState(0);
  const viewportRef = useRef<HTMLDivElement | null>(null);

  const agents = useMemo(() => {
    const now = Date.now();
    const queryValue = query.trim().toLowerCase();

    const mapped = services.map((service) => {
      const status = statuses[service.id];
      const state = status?.state ?? "stopped";
      const serviceLogs = logs[service.id] ?? [];
      const meta = realtimeByService[service.id];

      const lastLog = serviceLogs.length > 0 ? serviceLogs[serviceLogs.length - 1] : null;
      const recentMinute = serviceLogs.filter((entry) => entry.ts >= now - 60000);
      const recent5m = serviceLogs.filter((entry) => entry.ts >= now - 5 * 60000);
      const recentErrorCount = recent5m.filter((entry) => entry.level === "error").length;

      const lastSeenTs = Math.max(meta?.lastStatusTs ?? 0, lastLog?.ts ?? 0);
      const stale = lastSeenTs > 0 ? now - lastSeenTs > STALE_MS : false;
      const attention = state === "error" || recentErrorCount > 0 || stale;

      return {
        id: service.id,
        name: service.name,
        state,
        uptimeSec: status?.uptimeSec ?? null,
        pid: status?.pid ?? null,
        lastError: status?.lastError ?? null,
        lastLog,
        logCount: serviceLogs.length,
        logsPerMin: recentMinute.length,
        recentErrorCount,
        stale,
        attention,
        lastSeenTs,
        transitionCount: meta?.transitionCount ?? 0,
      };
    });

    return mapped
      .filter((agent) => {
        if (queryValue && !agent.name.toLowerCase().includes(queryValue) && !agent.id.toLowerCase().includes(queryValue)) {
          return false;
        }
        if (filter === "all") return true;
        if (filter === "running") return agent.state === "running";
        if (filter === "stopped") return agent.state === "stopped";
        return agent.attention;
      })
      .sort((a, b) => {
        if (a.attention !== b.attention) return a.attention ? -1 : 1;
        const byState = (STATE_PRIORITY[a.state] ?? 99) - (STATE_PRIORITY[b.state] ?? 99);
        if (byState !== 0) return byState;
        return a.name.localeCompare(b.name);
      });
  }, [filter, logs, query, realtimeByService, services, statuses]);

  useEffect(() => {
    const node = viewportRef.current;
    if (!node) return;
    const update = () => setViewportHeight(node.clientHeight || 280);
    update();
    const observer = new ResizeObserver(update);
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  const rowHeight = isMinimized ? ROW_HEIGHT_MINIMIZED : ROW_HEIGHT_EXPANDED;
  const virtual = useVirtualWindow({
    total: agents.length,
    rowHeight,
    viewportHeight,
    scrollTop,
    overscan: isMinimized ? 16 : 6,
  });

  const visibleAgents = useMemo(
    () => agents.slice(virtual.start, virtual.end),
    [agents, virtual.start, virtual.end],
  );

  const attentionCount = agents.filter((agent) => agent.attention).length;
  const runningCount = agents.filter((agent) => agent.state === "running").length;

  return (
    <div className="h-full min-h-0 flex flex-col rounded-md border bg-card transition-all duration-300 ease-in-out">
      <div className="cr-panel-header">
        <div className="cr-toolbar">
          <button
            type="button"
            onClick={() => setIsMinimized((prev) => !prev)}
            className="rounded p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            title={isMinimized ? "Expand agents panel" : "Minimize agents panel"}
            aria-label={isMinimized ? "Expand agents panel" : "Minimize agents panel"}
          >
            {isMinimized ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
          </button>
          <div className="cr-panel-title">Agents</div>
        </div>

        {!isMinimized ? (
          <div className="cr-toolbar">
            <Badge variant="secondary" className="cr-badge">
              running {runningCount}
            </Badge>
            <Badge variant={attentionCount > 0 ? "destructive" : "outline"} className="cr-badge">
              attention {attentionCount}
            </Badge>
          </div>
        ) : (
          <Badge variant="outline" className="cr-badge">
            {agents.length}
          </Badge>
        )}
      </div>

      {!isMinimized ? (
        <>
          <div className="space-y-2 border-b px-2 py-2">
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search agent/service"
              className="cr-compact-input"
            />
            <div className="flex flex-wrap gap-1">
              {FILTERS.map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setFilter(tab.id)}
                  className={`rounded border px-2 py-1 text-[10px] uppercase transition-colors ${
                    filter === tab.id ? "border-primary bg-primary/20 text-primary" : "border-border text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>

          <div
            ref={viewportRef}
            className="min-h-0 flex-1 overflow-auto"
            onScroll={(event) => setScrollTop((event.currentTarget as HTMLDivElement).scrollTop)}
          >
            <div style={{ height: virtual.offsetTop }} />
            {visibleAgents.map((agent) => (
              <button
                type="button"
                key={agent.id}
                onClick={() => onSelectService(agent.id)}
                className={`m-2 w-[calc(100%-1rem)] rounded border p-2 text-left transition-colors ${
                  activeServiceId === agent.id ? "border-primary bg-primary/10" : "bg-background/40 hover:bg-background/60"
                }`}
                style={{ minHeight: ROW_HEIGHT_EXPANDED - 8 }}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex min-w-0 items-center gap-2">
                    <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${stateDotClass(agent.state)}`} />
                    <div className="truncate text-sm font-medium">{agent.name}</div>
                  </div>
                  <Badge variant={statusBadgeVariant(agent.state)} className="h-5 text-[10px] uppercase">
                    {agent.state}
                  </Badge>
                </div>

                <div className="mt-2 grid grid-cols-3 gap-2 text-[11px] text-muted-foreground">
                  <div>
                    <div className="uppercase">Uptime</div>
                    <div className="text-foreground">{formatUptime(agent.uptimeSec)}</div>
                  </div>
                  <div>
                    <div className="uppercase">Logs/min</div>
                    <div className="text-foreground">{agent.logsPerMin}</div>
                  </div>
                  <div>
                    <div className="uppercase">Seen</div>
                    <div className={agent.stale ? "text-amber-300" : "text-foreground"}>{formatAge(agent.lastSeenTs)}</div>
                  </div>
                </div>

                <div className="mt-2 grid grid-cols-3 gap-2 text-[11px] text-muted-foreground">
                  <div>
                    <div className="uppercase">PID</div>
                    <div className="text-foreground">{agent.pid ?? "--"}</div>
                  </div>
                  <div>
                    <div className="uppercase">Err(5m)</div>
                    <div className={agent.recentErrorCount > 0 ? "text-rose-300" : "text-foreground"}>{agent.recentErrorCount}</div>
                  </div>
                  <div>
                    <div className="uppercase">Transitions</div>
                    <div className="text-foreground">{agent.transitionCount}</div>
                  </div>
                </div>

                {agent.lastError ? (
                  <div className="mt-2 line-clamp-1 rounded border border-rose-500/40 bg-rose-500/10 px-2 py-1 text-[11px] text-rose-300">
                    {agent.lastError}
                  </div>
                ) : null}

                {agent.lastLog ? (
                  <div className="mt-2 rounded border border-border/60 bg-background/70 px-2 py-1 text-[11px] text-muted-foreground">
                    <span className="mr-1">[{new Date(agent.lastLog.ts).toLocaleTimeString()}]</span>
                    <span className="uppercase">{agent.lastLog.level}</span>
                    <span className="ml-1 line-clamp-1">{agent.lastLog.line}</span>
                  </div>
                ) : null}
              </button>
            ))}
            <div style={{ height: virtual.offsetBottom }} />
            {agents.length === 0 ? <div className="p-2 text-xs text-muted-foreground">No services match this filter.</div> : null}
          </div>
        </>
      ) : (
        <div
          ref={viewportRef}
          className="min-h-0 flex-1 overflow-auto"
          onScroll={(event) => setScrollTop((event.currentTarget as HTMLDivElement).scrollTop)}
        >
          <div style={{ height: virtual.offsetTop }} />
          {visibleAgents.map((agent) => (
            <button
              type="button"
              key={agent.id}
              onClick={() => onSelectService(agent.id)}
              className={`mx-2 mb-1 flex w-[calc(100%-1rem)] items-center gap-2 rounded border px-2 py-1.5 text-left text-[11px] transition-colors ${
                activeServiceId === agent.id ? "border-primary bg-primary/10" : "bg-background/40 hover:bg-background/60"
              }`}
              title={`${agent.name} · ${agent.state}`}
              style={{ minHeight: ROW_HEIGHT_MINIMIZED - 2 }}
            >
              <span className={`h-2 w-2 shrink-0 rounded-full ${stateDotClass(agent.state)}`} />
              <span className="truncate font-medium">{agent.name}</span>
              {agent.attention ? (
                <Badge variant="destructive" className="ml-auto h-4 px-1 text-[9px] uppercase">
                  !
                </Badge>
              ) : null}
            </button>
          ))}
          <div style={{ height: virtual.offsetBottom }} />
          {agents.length === 0 ? <div className="p-2 text-xs text-muted-foreground">No items</div> : null}
        </div>
      )}
    </div>
  );
}
