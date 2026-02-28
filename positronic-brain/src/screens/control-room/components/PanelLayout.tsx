import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from "@/components/ui/resizable";
import { useEffect, useMemo, useState } from "react";
import {
  CONTROLROOM_LAYOUT_STORAGE_KEY,
  parseLayoutState,
  serializeLayoutState,
  type ControlRoomLayoutState,
} from "../layout/layoutState";
import type {
  ControlFeedEvent,
  DashboardMode,
  RealtimeBusStatus,
  RunnerCommandInput,
  RunnerExitEvent,
  RunnerOutputEvent,
  RunnerRunMeta,
  ServiceConfig,
  ServiceLogEvent,
  ServiceRealtimeMeta,
  ServiceState,
  ServiceStatus,
  VideoEvent,
  VideoWallConfig,
} from "../types";
import { AgentsPanel } from "./AgentsPanel";
import { LiveFeedPanel } from "./LiveFeedPanel";
import { MissionBoardPanel } from "./MissionBoardPanel";
import { NativeTerminalPanel } from "./NativeTerminalPanel";
import { RunnerPanel } from "./RunnerPanel";
import { ServiceLogPanel } from "./ServiceLogPanel";
import { VideoWallPanel } from "./VideoWallPanel";

function EmptyServicesPanel() {
  return (
    <div className="controlroom-empty-state flex h-full items-center justify-center rounded-md border border-dashed bg-card/40 text-sm text-muted-foreground">
      No services configured
    </div>
  );
}

function serviceRank(state: ServiceState): number {
  if (state === "error") return 0;
  if (state === "running") return 1;
  if (state === "starting") return 2;
  if (state === "stopping") return 3;
  return 4;
}

export function PanelLayout({
  services,
  statuses,
  logs,
  onClearServiceLogs,
  runnerHistory,
  runnerOutputs,
  runnerExits,
  runnerMetaByRun,
  feedEvents,
  realtimeByService,
  busStatus,
  activeServiceId,
  dashboardMode,
  videoWallConfig,
  isHighLoad,
  onSelectService,
  onRunnerExecute,
  onRunnerCancel,
  onVideoFeedEvent,
}: {
  services: ServiceConfig[];
  statuses: Record<string, ServiceStatus>;
  logs: Record<string, ServiceLogEvent[]>;
  onClearServiceLogs: (serviceId: string) => void;
  runnerHistory: RunnerCommandInput[];
  runnerOutputs: Record<string, RunnerOutputEvent[]>;
  runnerExits: Record<string, RunnerExitEvent>;
  runnerMetaByRun: Record<string, RunnerRunMeta>;
  feedEvents: ControlFeedEvent[];
  realtimeByService: Record<string, ServiceRealtimeMeta>;
  busStatus: RealtimeBusStatus;
  activeServiceId: string | null;
  dashboardMode: DashboardMode;
  videoWallConfig?: VideoWallConfig;
  isHighLoad: boolean;
  onSelectService: (serviceId: string) => void;
  onRunnerExecute: (input: RunnerCommandInput) => Promise<string | null>;
  onRunnerCancel: (runId: string) => Promise<void>;
  onVideoFeedEvent?: (event: VideoEvent) => void;
}) {
  const [serviceOrder, setServiceOrder] = useState<string[]>([]);
  const [collapsedByService, setCollapsedByService] = useState<Record<string, boolean>>({});
  const [draggingServiceId, setDraggingServiceId] = useState<string | null>(null);
  const [dragOverServiceId, setDragOverServiceId] = useState<string | null>(null);
  const [opsTab, setOpsTab] = useState<"runner" | "terminal" | "mission">("runner");

  useEffect(() => {
    if (typeof window === "undefined") return;
    const parsed = parseLayoutState(window.localStorage.getItem(CONTROLROOM_LAYOUT_STORAGE_KEY));
    if (!parsed) return;
    const order = parsed.widgets
      .filter((widget) => widget.id.startsWith("service:"))
      .sort((a, b) => (a.order ?? 0) - (b.order ?? 0))
      .map((widget) => widget.id.replace(/^service:/, ""));

    const collapsed: Record<string, boolean> = {};
    parsed.widgets
      .filter((widget) => widget.id.startsWith("service:"))
      .forEach((widget) => {
        if (widget.collapsed) {
          collapsed[widget.id.replace(/^service:/, "")] = true;
        }
      });

    setServiceOrder(order);
    setCollapsedByService(collapsed);
  }, []);

  useEffect(() => {
    const validIds = new Set(services.map((service) => service.id));
    const orderedIds = services.map((service) => service.id);

    setServiceOrder((prev) => {
      const next: string[] = [];
      const seen = new Set<string>();

      prev.forEach((id) => {
        if (validIds.has(id) && !seen.has(id)) {
          next.push(id);
          seen.add(id);
        }
      });

      orderedIds.forEach((id) => {
        if (!seen.has(id)) {
          next.push(id);
          seen.add(id);
        }
      });

      return next;
    });

    setCollapsedByService((prev) => {
      const next: Record<string, boolean> = {};
      Object.keys(prev).forEach((id) => {
        if (validIds.has(id) && prev[id]) next[id] = true;
      });
      return next;
    });
  }, [services]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (serviceOrder.length === 0) return;

    const state: ControlRoomLayoutState = {
      version: 2,
      widgets: serviceOrder.map((id, index) => ({
        id: `service:${id}`,
        x: index % 3,
        y: Math.floor(index / 3),
        w: 1,
        h: collapsedByService[id] ? 1 : 4,
        collapsed: Boolean(collapsedByService[id]),
        order: index,
        visible: true,
      })),
    };

    window.localStorage.setItem(CONTROLROOM_LAYOUT_STORAGE_KEY, serializeLayoutState(state));
  }, [serviceOrder, collapsedByService]);

  const orderedServices = useMemo(() => {
    if (services.length === 0) return [] as ServiceConfig[];
    const byId = new Map(services.map((service) => [service.id, service]));
    const next: ServiceConfig[] = [];
    const seen = new Set<string>();

    serviceOrder.forEach((id) => {
      const service = byId.get(id);
      if (!service || seen.has(id)) return;
      next.push(service);
      seen.add(id);
    });

    services.forEach((service) => {
      if (seen.has(service.id)) return;
      next.push(service);
      seen.add(service.id);
    });

    return next;
  }, [services, serviceOrder]);

  const activeService = useMemo(
    () => orderedServices.find((service) => service.id === activeServiceId) ?? null,
    [orderedServices, activeServiceId],
  );

  const serviceGridExtraCols = orderedServices.length >= 5 ? "2xl:grid-cols-3" : "2xl:grid-cols-2";
  const experimentalCount = orderedServices.filter((service) => service.tier === "experimental").length;

  function toggleCollapsed(serviceId: string) {
    setCollapsedByService((prev) => ({
      ...prev,
      [serviceId]: !prev[serviceId],
    }));
  }

  function collapseNonCritical() {
    setCollapsedByService((prev) => {
      const next = { ...prev };
      orderedServices.forEach((service) => {
        const state = statuses[service.id]?.state ?? "stopped";
        const isCritical = service.id === activeServiceId || state === "running" || state === "error";
        if (!isCritical) next[service.id] = true;
      });
      return next;
    });
  }

  function autoPackServiceWall() {
    setServiceOrder((prev) => {
      const ranked = [...orderedServices].sort((a, b) => {
        const aRank = serviceRank(statuses[a.id]?.state ?? "stopped");
        const bRank = serviceRank(statuses[b.id]?.state ?? "stopped");
        if (aRank !== bRank) return aRank - bRank;
        return a.name.localeCompare(b.name);
      });
      const rankedIds = ranked.map((service) => service.id);
      if (rankedIds.length === 0) return prev;
      return rankedIds;
    });
  }

  function resetServiceWallLayout() {
    setServiceOrder(services.map((service) => service.id));
    setCollapsedByService({});
    setDraggingServiceId(null);
    setDragOverServiceId(null);
  }

  function reorderServices(sourceServiceId: string, targetServiceId: string) {
    if (sourceServiceId === targetServiceId) return;

    setServiceOrder((prev) => {
      const base = prev.length > 0 ? [...prev] : services.map((service) => service.id);
      const sourceIndex = base.indexOf(sourceServiceId);
      const targetIndex = base.indexOf(targetServiceId);
      if (sourceIndex < 0 || targetIndex < 0) return base;

      const [moved] = base.splice(sourceIndex, 1);
      base.splice(targetIndex, 0, moved);
      return base;
    });
  }

  return (
    <div className="relative h-full min-h-0">
      <ResizablePanelGroup direction="horizontal" autoSaveId="controlroom-main-lateral-v3" className="h-full min-h-0">
        <ResizablePanel defaultSize={73} minSize={42}>
          <ResizablePanelGroup direction="vertical" autoSaveId="controlroom-main-center-v3" className="h-full min-h-0">
            <ResizablePanel defaultSize={74} minSize={46}>
              <ResizablePanelGroup direction="horizontal" autoSaveId="controlroom-top-band-v5" className="h-full min-h-0">
                <ResizablePanel defaultSize={68} minSize={40}>
                  <div className="controlroom-card flex h-full min-h-0 flex-col rounded-md border border-border/50 bg-card/35">
                    <div className="cr-panel-header">
                      <div className="cr-toolbar">
                        <span className="cr-panel-title">Service Wall</span>
                        <span className="cr-meta">drag and drop</span>
                      </div>
                      <div className="cr-toolbar">
                        <span className="cr-meta">
                          {orderedServices.length} panel{orderedServices.length === 1 ? "" : "es"}
                        </span>
                        <span className="cr-meta">exp {experimentalCount}</span>
                        <Button size="sm" variant="outline" className="cr-compact-btn" onClick={autoPackServiceWall}>
                          Auto-pack
                        </Button>
                        <Button size="sm" variant="outline" className="cr-compact-btn" onClick={collapseNonCritical}>
                          Collapse non-critical
                        </Button>
                        <Button size="sm" variant="outline" className="cr-compact-btn" onClick={resetServiceWallLayout}>
                          Reset Layout
                        </Button>
                      </div>
                    </div>

                    <ScrollArea className="min-h-0 flex-1">
                      {orderedServices.length === 0 ? (
                        <div className="h-full p-2">
                          <EmptyServicesPanel />
                        </div>
                      ) : (
                        <div className={`grid grid-cols-1 gap-2 p-2 md:grid-cols-2 ${serviceGridExtraCols}`}>
                          {orderedServices.map((service) => {
                            const collapsed = Boolean(collapsedByService[service.id]);
                            const isDragging = draggingServiceId === service.id;
                            const isDropTarget = dragOverServiceId === service.id && draggingServiceId !== service.id;

                            return (
                              <div
                                key={service.id}
                                className={`min-h-0 transition-all duration-150 ${collapsed ? "h-[72px]" : "h-[390px]"} ${
                                  isDragging ? "opacity-75" : ""
                                } ${isDropTarget ? "rounded-md ring-1 ring-primary/60" : ""}`}
                                draggable
                                onDragStart={(event) => {
                                  setDraggingServiceId(service.id);
                                  setDragOverServiceId(service.id);
                                  event.dataTransfer.effectAllowed = "move";
                                  event.dataTransfer.setData("text/plain", service.id);
                                }}
                                onDragEnter={(event) => {
                                  event.preventDefault();
                                  if (!draggingServiceId) return;
                                  if (draggingServiceId === service.id) return;
                                  setDragOverServiceId(service.id);
                                }}
                                onDragOver={(event) => {
                                  event.preventDefault();
                                  event.dataTransfer.dropEffect = "move";
                                }}
                                onDrop={(event) => {
                                  event.preventDefault();
                                  const sourceId = draggingServiceId || event.dataTransfer.getData("text/plain");
                                  if (!sourceId) return;
                                  reorderServices(sourceId, service.id);
                                  setDraggingServiceId(null);
                                  setDragOverServiceId(null);
                                }}
                                onDragEnd={() => {
                                  setDraggingServiceId(null);
                                  setDragOverServiceId(null);
                                }}
                              >
                                <ServiceLogPanel
                                  serviceName={service.name}
                                  serviceId={service.id}
                                  status={statuses[service.id]}
                                  logs={logs[service.id] ?? []}
                                  onClear={onClearServiceLogs}
                                  isActive={activeServiceId === service.id}
                                  onActivate={onSelectService}
                                  collapsed={collapsed}
                                  onToggleCollapsed={toggleCollapsed}
                                />
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </ScrollArea>
                  </div>
                </ResizablePanel>

                <ResizableHandle />

                <ResizablePanel defaultSize={32} minSize={18}>
                  <VideoWallPanel
                    dashboardMode={dashboardMode}
                    isHighLoad={isHighLoad}
                    config={videoWallConfig}
                    onVideoEvent={onVideoFeedEvent}
                  />
                </ResizablePanel>
              </ResizablePanelGroup>
            </ResizablePanel>

            <ResizableHandle />

            <ResizablePanel defaultSize={26} minSize={16}>
              <ResizablePanelGroup direction="horizontal" autoSaveId="controlroom-bottom-observability-v3" className="h-full min-h-0">
                <ResizablePanel defaultSize={50} minSize={24}>
                  <AgentsPanel
                    services={orderedServices}
                    statuses={statuses}
                    logs={logs}
                    realtimeByService={realtimeByService}
                    activeServiceId={activeServiceId}
                    onSelectService={onSelectService}
                  />
                </ResizablePanel>

                <ResizableHandle />

                <ResizablePanel defaultSize={50} minSize={24}>
                  <LiveFeedPanel events={feedEvents} busStatus={busStatus} />
                </ResizablePanel>
              </ResizablePanelGroup>
            </ResizablePanel>
          </ResizablePanelGroup>
        </ResizablePanel>

        <ResizableHandle />

        <ResizablePanel defaultSize={27} minSize={18}>
          <div className="controlroom-card flex h-full min-h-0 flex-col rounded-md border border-border/50 bg-card/35">
            <div className="cr-panel-header">
              <div className="cr-toolbar">
                <span className="cr-panel-title">Ops Workbench</span>
                <Button
                  size="sm"
                  variant={opsTab === "runner" ? "default" : "outline"}
                  className={opsTab === "runner" ? "cr-compact-btn controlroom-btn-start" : "cr-compact-btn"}
                  onClick={() => setOpsTab("runner")}
                >
                  Runner
                </Button>
                <Button
                  size="sm"
                  variant={opsTab === "terminal" ? "default" : "outline"}
                  className={opsTab === "terminal" ? "cr-compact-btn controlroom-btn-neutral" : "cr-compact-btn"}
                  onClick={() => setOpsTab("terminal")}
                >
                  Terminal
                </Button>
                <Button
                  size="sm"
                  variant={opsTab === "mission" ? "default" : "outline"}
                  className={opsTab === "mission" ? "cr-compact-btn controlroom-btn-neutral" : "cr-compact-btn"}
                  onClick={() => setOpsTab("mission")}
                >
                  Mission
                </Button>
              </div>
              <span className="cr-meta uppercase">{opsTab}</span>
            </div>

            <div className="min-h-0 flex-1">
              {opsTab === "runner" ? (
                <RunnerPanel
                  history={runnerHistory}
                  outputsByRun={runnerOutputs}
                  exitsByRun={runnerExits}
                  onExecute={onRunnerExecute}
                  onCancel={onRunnerCancel}
                />
              ) : null}
              {opsTab === "terminal" ? <NativeTerminalPanel activeService={activeService} /> : null}
              {opsTab === "mission" ? (
                <MissionBoardPanel
                  services={orderedServices}
                  statuses={statuses}
                  runnerMetaByRun={runnerMetaByRun}
                  runnerOutputs={runnerOutputs}
                  runnerExits={runnerExits}
                  feedEvents={feedEvents}
                />
              ) : null}
            </div>
          </div>
        </ResizablePanel>
      </ResizablePanelGroup>
    </div>
  );
}
