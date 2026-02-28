import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { useMemo, useState } from "react";
import type {
  DashboardMode,
  RealtimeBusStatus,
  RuntimeActivityStatus,
  ServiceConfig,
  ServiceStatus,
  ServiceTelemetry,
} from "../types";

const RUNTIME_ACTIVITY_ACTIVE_MS = 90000;

function statusColor(state: string) {
  switch (state) {
    case "running":
      return "bg-emerald-500";
    case "starting":
    case "stopping":
      return "bg-amber-500";
    case "error":
      return "bg-rose-500";
    default:
      return "bg-slate-500";
  }
}

function formatUptime(uptimeSec?: number | null) {
  if (!uptimeSec || uptimeSec <= 0) return "--";
  const h = Math.floor(uptimeSec / 3600);
  const m = Math.floor((uptimeSec % 3600) / 60);
  const s = Math.floor(uptimeSec % 60);
  if (h > 0) return `${h}h ${m}m ${s}s`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

function busDotClass(state: RealtimeBusStatus["state"]) {
  if (state === "online") return "bg-emerald-500";
  if (state === "degraded") return "bg-amber-500";
  if (state === "offline") return "bg-rose-500";
  return "bg-slate-500";
}

function formatLagMs(ms?: number) {
  if (!ms || ms < 0) return "--";
  if (ms < 1000) return `${ms}ms`;
  return `${Math.floor(ms / 1000)}s`;
}

function formatSince(ts?: number) {
  if (!ts) return "--";
  const diffMs = Math.max(0, Date.now() - ts);
  if (diffMs < 1000) return "just now";
  if (diffMs < 60000) return `${Math.floor(diffMs / 1000)}s ago`;
  if (diffMs < 3600000) return `${Math.floor(diffMs / 60000)}m ago`;
  return `${Math.floor(diffMs / 3600000)}h ago`;
}

function runtimeState(activity: RuntimeActivityStatus): "active" | "idle" | "error" {
  if (activity.level === "error" && activity.lastSeenTs) return "error";
  if (activity.lastSeenTs && Date.now() - activity.lastSeenTs <= RUNTIME_ACTIVITY_ACTIVE_MS) return "active";
  return "idle";
}

function runtimeDotClass(state: "active" | "idle" | "error") {
  if (state === "error") return "bg-rose-500";
  if (state === "active") return "bg-emerald-500";
  return "bg-slate-500";
}

function formatLatency(ms?: number) {
  if (ms === undefined || !Number.isFinite(ms)) return "--";
  return `${Math.round(ms)}ms`;
}

type ServiceAction = "start" | "stop" | "restart";

function recommendedServiceAction(state: ServiceStatus["state"] | undefined): ServiceAction {
  if (state === "running" || state === "starting") return "stop";
  if (state === "error") return "restart";
  return "start";
}

function isActionDisabled(action: ServiceAction, state: ServiceStatus["state"] | undefined) {
  if (action === "start") return state === "running" || state === "starting";
  if (action === "stop") return state === "stopped" || state === "stopping";
  return state === "starting" || state === "stopping";
}

function actionButtonClass(action: ServiceAction, recommended: ServiceAction) {
  if (action === "start") return recommended === action ? "controlroom-btn-start" : undefined;
  if (action === "stop") return recommended === action ? "controlroom-btn-stop" : undefined;
  return "controlroom-btn-neutral";
}

function modeLabel(mode: DashboardMode) {
  if (mode === "dev") return "Dev";
  if (mode === "multimedia") return "Multimedia";
  if (mode === "medical") return "Medico";
  return "All";
}

function Sparkline({ samples }: { samples: number[] }) {
  const clean = samples.filter((value) => Number.isFinite(value) && value > 0).slice(-20);
  if (clean.length < 2) {
    return <div className="h-5 w-16 rounded-sm bg-muted/30" />;
  }
  const max = Math.max(...clean, 1);
  const points = clean
    .map((value, index) => {
      const x = (index / (clean.length - 1)) * 100;
      const y = 100 - Math.min(100, (value / max) * 100);
      return `${x},${y}`;
    })
    .join(" ");
  return (
    <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="h-5 w-16">
      <polyline points={points} fill="none" stroke="currentColor" strokeWidth="5" className="text-primary/85" />
    </svg>
  );
}

export function TopStatusBar({
  services,
  statuses,
  busStatus,
  runtimeActivities,
  telemetryByService,
  dashboardMode,
  refreshing,
  onStart,
  onStop,
  onRestart,
  onRefresh,
}: {
  services: ServiceConfig[];
  statuses: Record<string, ServiceStatus>;
  busStatus: RealtimeBusStatus;
  runtimeActivities: RuntimeActivityStatus[];
  telemetryByService: Record<string, ServiceTelemetry>;
  dashboardMode: DashboardMode;
  refreshing: boolean;
  onStart: (serviceId: string) => void;
  onStop: (serviceId: string) => void;
  onRestart: (serviceId: string) => void;
  onRefresh: () => void;
}) {
  const now = Date.now();
  const [showInactiveServices, setShowInactiveServices] = useState(false);
  const [showInactiveRuntime, setShowInactiveRuntime] = useState(false);
  const runningCount = services.filter((service) => statuses[service.id]?.state === "running").length;
  const errorCount = services.filter((service) => statuses[service.id]?.state === "error").length;
  const statusLagMs = busStatus.lastStatusSyncTs ? Math.max(0, now - busStatus.lastStatusSyncTs) : undefined;
  const runtimeActiveCount = runtimeActivities.filter((activity) => runtimeState(activity) === "active").length;
  const runtimeErrorCount = runtimeActivities.filter((activity) => runtimeState(activity) === "error").length;
  const sortedServices = useMemo(() => {
    const active: ServiceConfig[] = [];
    const inactive: ServiceConfig[] = [];
    services.forEach((service) => {
      const state = statuses[service.id]?.state ?? "stopped";
      if (state === "stopped") {
        inactive.push(service);
      } else {
        active.push(service);
      }
    });
    return { active, inactive };
  }, [services, statuses]);
  const sortedRuntime = useMemo(() => {
    const active: RuntimeActivityStatus[] = [];
    const inactive: RuntimeActivityStatus[] = [];
    runtimeActivities.forEach((activity) => {
      const state = runtimeState(activity);
      if (state === "idle") {
        inactive.push(activity);
      } else {
        active.push(activity);
      }
    });
    return { active, inactive };
  }, [runtimeActivities]);

  return (
    <div className="controlroom-card flex h-full min-h-0 flex-col rounded-md border border-border/50 bg-card/35">
      <div className="cr-panel-header border-b border-border/45">
        <div className="cr-toolbar">
          <span className="cr-panel-title">Services Overview</span>
          <div className="cr-toolbar rounded-md border border-border/45 bg-background/40 px-2 py-1">
            <span className={`h-2.5 w-2.5 rounded-full ${busDotClass(busStatus.state)}`} />
            <span className="cr-meta uppercase">Realtime {busStatus.state}</span>
            <Separator orientation="vertical" className="h-3" />
            <span className="cr-meta">lag {formatLagMs(statusLagMs)}</span>
            <Separator orientation="vertical" className="h-3" />
            <span className="cr-meta">reconnects {busStatus.reconnectCount}</span>
            <Separator orientation="vertical" className="h-3" />
            <span className="cr-meta">sync {formatSince(busStatus.lastStatusSyncTs)}</span>
          </div>
        </div>
        <div className="cr-toolbar">
          <Button size="sm" variant="outline" className="cr-compact-btn" onClick={onRefresh} disabled={refreshing}>
            {refreshing ? "Refreshing..." : "Refresh"}
          </Button>
          <Badge variant="outline" className="cr-badge">
            mode {modeLabel(dashboardMode)}
          </Badge>
          <Badge variant="secondary" className="cr-badge">
            running {runningCount}
          </Badge>
          <Badge variant={errorCount > 0 ? "destructive" : "outline"} className="cr-badge">
            errors {errorCount}
          </Badge>
          <Badge variant="secondary" className="cr-badge">
            runtime active {runtimeActiveCount}
          </Badge>
          <Badge variant={runtimeErrorCount > 0 ? "destructive" : "outline"} className="cr-badge">
            runtime errors {runtimeErrorCount}
          </Badge>
          <span className="cr-meta">
            {services.length} service{services.length === 1 ? "" : "s"}
          </span>
        </div>
      </div>

      <ScrollArea className="min-h-0 flex-1">
        <div className="space-y-2 p-2">
          <div className="overflow-x-auto">
            <div className="flex min-w-max items-stretch gap-2 pb-1">
              {sortedServices.active.map((service) => {
                const status = statuses[service.id];
                const state = status?.state ?? "stopped";
                const telemetry = telemetryByService[service.id];
                const hasWarnLatency =
                  state === "running" &&
                  telemetry?.lastLatencyMs !== undefined &&
                  telemetry.lastLatencyMs > 200;
                return (
                  <div
                    key={service.id}
                    className={`controlroom-card w-[320px] shrink-0 rounded-lg border border-border/50 bg-background/50 p-2 transition-all duration-200 hover:-translate-y-[1px] hover:border-border ${
                      hasWarnLatency ? "controlroom-telemetry-warn" : ""
                    }`}
                  >
                    <div className="mb-2 flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span className={`h-2.5 w-2.5 rounded-full ${statusColor(state)}`} />
                        <span className="text-sm font-semibold tracking-tight">{service.name}</span>
                        <Badge variant="outline" className="cr-badge">
                          {state}
                        </Badge>
                      </div>
                      <span className="cr-meta">uptime {formatUptime(status?.uptimeSec)}</span>
                    </div>
                    {status?.lastError ? (
                      <div className="mb-2 line-clamp-2 text-xs text-rose-400">{status.lastError}</div>
                    ) : (
                      <div className="mb-2 text-xs text-muted-foreground">
                        No errors
                        <span className="ml-2 inline-flex items-center gap-2">
                          <span className="cr-meta">lat {formatLatency(telemetry?.lastLatencyMs)}</span>
                          {telemetry?.port ? <span className="cr-meta">:{telemetry.port}</span> : null}
                          <Sparkline samples={telemetry?.samples ?? []} />
                        </span>
                      </div>
                    )}
                    <div className="flex items-center gap-1.5">
                      <Button
                        size="sm"
                        variant="outline"
                        className={`cr-compact-btn ${actionButtonClass("start", recommendedServiceAction(state)) ?? ""}`}
                        disabled={isActionDisabled("start", state)}
                        onClick={() => onStart(service.id)}
                      >
                        Start
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        className={`cr-compact-btn ${actionButtonClass("stop", recommendedServiceAction(state)) ?? ""}`}
                        disabled={isActionDisabled("stop", state)}
                        onClick={() => onStop(service.id)}
                      >
                        Stop
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        className={`cr-compact-btn ${actionButtonClass("restart", recommendedServiceAction(state)) ?? ""}`}
                        disabled={isActionDisabled("restart", state)}
                        onClick={() => onRestart(service.id)}
                      >
                        Restart
                      </Button>
                    </div>
                  </div>
                );
              })}
              {sortedServices.active.length === 0 ? (
                <div className="controlroom-card w-full min-w-[320px] rounded-lg border border-border/40 bg-background/35 p-2 text-xs text-muted-foreground">
                  No hay servicios activos ahora.
                </div>
              ) : null}
            </div>
          </div>

          {sortedServices.inactive.length > 0 ? (
            <div className="rounded-lg border border-border/45 bg-background/30 p-2">
              <button
                type="button"
                className="flex w-full items-center justify-between text-left text-[11px] font-medium text-muted-foreground"
                onClick={() => setShowInactiveServices((prev) => !prev)}
              >
                <span>Inactive services ({sortedServices.inactive.length})</span>
                <span>{showInactiveServices ? "Hide" : "Show"}</span>
              </button>
              {showInactiveServices ? (
                <div className="mt-2 overflow-x-auto">
                  <div className="flex min-w-max items-stretch gap-2 pb-1">
                    {sortedServices.inactive.map((service) => {
                      const status = statuses[service.id];
                      const state = status?.state ?? "stopped";
                      const telemetry = telemetryByService[service.id];
                      return (
                        <div
                          key={service.id}
                          className="controlroom-card w-[300px] shrink-0 rounded-lg border border-border/50 bg-background/40 p-2"
                        >
                          <div className="mb-2 flex items-center justify-between gap-2">
                            <div className="flex items-center gap-2">
                              <span className={`h-2.5 w-2.5 rounded-full ${statusColor(state)}`} />
                              <span className="text-sm font-semibold tracking-tight">{service.name}</span>
                              <Badge variant="outline" className="cr-badge">
                                {state}
                              </Badge>
                            </div>
                            <span className="cr-meta">uptime {formatUptime(status?.uptimeSec)}</span>
                          </div>
                          <div className="mb-2 text-xs text-muted-foreground">
                            lat {formatLatency(telemetry?.lastLatencyMs)} {telemetry?.port ? `· :${telemetry.port}` : ""}
                          </div>
                          <div className="flex items-center gap-1.5">
                            <Button
                              size="sm"
                              variant="outline"
                              className={`cr-compact-btn ${actionButtonClass("start", recommendedServiceAction(state)) ?? ""}`}
                              disabled={isActionDisabled("start", state)}
                              onClick={() => onStart(service.id)}
                            >
                              Start
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              className={`cr-compact-btn ${actionButtonClass("stop", recommendedServiceAction(state)) ?? ""}`}
                              disabled={isActionDisabled("stop", state)}
                              onClick={() => onStop(service.id)}
                            >
                              Stop
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              className={`cr-compact-btn ${actionButtonClass("restart", recommendedServiceAction(state)) ?? ""}`}
                              disabled={isActionDisabled("restart", state)}
                              onClick={() => onRestart(service.id)}
                            >
                              Restart
                            </Button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ) : null}
            </div>
          ) : null}

          <div className="overflow-x-auto border-t border-border/50 pt-2">
            <div className="mb-2 flex items-center justify-between text-[11px] text-muted-foreground">
              <span className="cr-panel-title">Occasional Runtime Modules</span>
              <span className="cr-meta">{runtimeActivities.length} tracked</span>
            </div>
            <div className="flex min-w-max items-stretch gap-2 pb-1">
              {sortedRuntime.active.map((activity) => {
                const state = runtimeState(activity);
                return (
                  <div
                    key={activity.id}
                    className="controlroom-card w-[220px] shrink-0 rounded-lg border border-border/50 bg-background/45 p-2 transition-all duration-200 hover:border-border"
                  >
                    <div className="mb-1 flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span className={`h-2.5 w-2.5 rounded-full ${runtimeDotClass(state)}`} />
                        <span className="text-sm font-semibold tracking-tight">{activity.name}</span>
                      </div>
                      <Badge
                        variant={state === "error" ? "destructive" : state === "active" ? "default" : "outline"}
                        className="cr-badge"
                      >
                        {state}
                      </Badge>
                    </div>
                    <div className="line-clamp-2 text-[11px] text-muted-foreground">{activity.lastLine || "No recent activity"}</div>
                    <div className="mt-2 flex items-center justify-between text-[11px] text-muted-foreground">
                      <span>hits {activity.hitCount}</span>
                      <span>last {formatSince(activity.lastSeenTs)}</span>
                    </div>
                    <div className="mt-1 flex items-center justify-between text-[11px] text-muted-foreground">
                      <span>
                        metric {formatLatency(activity.lastMetricMs)}
                        {activity.metricSource ? ` (${activity.metricSource})` : ""}
                      </span>
                      <Sparkline samples={activity.samples ?? []} />
                    </div>
                    <div className="mt-1 text-[11px] text-muted-foreground">
                      source {activity.lastSourceServiceId || "--"}
                    </div>
                  </div>
                );
              })}
              {sortedRuntime.active.length === 0 ? (
                <div className="controlroom-card w-full min-w-[220px] rounded-lg border border-border/40 bg-background/35 p-2 text-xs text-muted-foreground">
                  No hay módulos ocasionales activos.
                </div>
              ) : null}
            </div>
            {sortedRuntime.inactive.length > 0 ? (
              <div className="mt-1 rounded-lg border border-border/45 bg-background/30 p-2">
                <button
                  type="button"
                  className="flex w-full items-center justify-between text-left text-[11px] font-medium text-muted-foreground"
                  onClick={() => setShowInactiveRuntime((prev) => !prev)}
                >
                  <span>Inactive runtime modules ({sortedRuntime.inactive.length})</span>
                  <span>{showInactiveRuntime ? "Hide" : "Show"}</span>
                </button>
                {showInactiveRuntime ? (
                  <div className="mt-2 overflow-x-auto">
                    <div className="flex min-w-max items-stretch gap-2 pb-1">
                      {sortedRuntime.inactive.map((activity) => {
                        const state = runtimeState(activity);
                        return (
                          <div
                            key={activity.id}
                            className="controlroom-card w-[220px] shrink-0 rounded-lg border border-border/50 bg-background/45 p-2 transition-all duration-200 hover:border-border"
                          >
                            <div className="mb-1 flex items-center justify-between gap-2">
                              <div className="flex items-center gap-2">
                                <span className={`h-2.5 w-2.5 rounded-full ${runtimeDotClass(state)}`} />
                                <span className="text-sm font-semibold tracking-tight">{activity.name}</span>
                              </div>
                              <Badge variant="outline" className="cr-badge">
                                {state}
                              </Badge>
                            </div>
                            <div className="line-clamp-2 text-[11px] text-muted-foreground">{activity.lastLine || "No recent activity"}</div>
                            <div className="mt-2 flex items-center justify-between text-[11px] text-muted-foreground">
                              <span>hits {activity.hitCount}</span>
                              <span>last {formatSince(activity.lastSeenTs)}</span>
                            </div>
                            <div className="mt-1 flex items-center justify-between text-[11px] text-muted-foreground">
                              <span>
                                metric {formatLatency(activity.lastMetricMs)}
                                {activity.metricSource ? ` (${activity.metricSource})` : ""}
                              </span>
                              <Sparkline samples={activity.samples ?? []} />
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ) : null}
              </div>
            ) : null}
          </div>
        </div>
      </ScrollArea>
    </div>
  );
}
