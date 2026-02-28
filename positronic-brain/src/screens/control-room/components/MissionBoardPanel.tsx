import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useMemo } from "react";
import type {
  ControlFeedEvent,
  RunnerExitEvent,
  RunnerOutputEvent,
  RunnerRunMeta,
  ServiceConfig,
  ServiceState,
  ServiceStatus,
} from "../types";

type MissionColumnId = "planning" | "inbox" | "assigned" | "in_progress" | "testing" | "review" | "done";

interface MissionCard {
  id: string;
  title: string;
  subtitle: string;
  source: string;
  column: MissionColumnId;
  updatedTs: number;
  tone: "default" | "warn" | "error";
}

const TASK_TRIGGER_PATTERN =
  /\b(action required|aider|arregla|fix|corregir|todo|to-do|pendiente|hacer|resuelve|investiga)\b/i;

const BOARD_COLUMNS: Array<{ id: MissionColumnId; label: string }> = [
  { id: "planning", label: "Planning" },
  { id: "inbox", label: "Inbox" },
  { id: "assigned", label: "Assigned" },
  { id: "in_progress", label: "In Progress" },
  { id: "testing", label: "Testing" },
  { id: "review", label: "Review" },
  { id: "done", label: "Done" },
];

function mapServiceStateToColumn(state: ServiceState): MissionColumnId {
  switch (state) {
    case "starting":
      return "planning";
    case "stopping":
      return "testing";
    case "running":
      return "in_progress";
    case "error":
      return "review";
    case "stopped":
    default:
      return "inbox";
  }
}

function mapRunnerToColumn(exit?: RunnerExitEvent, outputCount = 0): MissionColumnId {
  if (exit) return exit.code === 0 ? "done" : "review";
  if (outputCount > 0) return "in_progress";
  return "assigned";
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

function cardToneClass(tone: MissionCard["tone"]) {
  if (tone === "error") return "border-rose-500/40 bg-rose-500/10";
  if (tone === "warn") return "border-amber-500/40 bg-amber-500/10";
  return "border-border bg-card";
}

export function MissionBoardPanel({
  services,
  statuses,
  runnerMetaByRun,
  runnerOutputs,
  runnerExits,
  feedEvents,
}: {
  services: ServiceConfig[];
  statuses: Record<string, ServiceStatus>;
  runnerMetaByRun: Record<string, RunnerRunMeta>;
  runnerOutputs: Record<string, RunnerOutputEvent[]>;
  runnerExits: Record<string, RunnerExitEvent>;
  feedEvents: ControlFeedEvent[];
}) {
  const cards = useMemo(() => {
    const serviceCards: MissionCard[] = services.map((service) => {
      const status = statuses[service.id];
      const state = status?.state ?? "stopped";
      return {
        id: `service-${service.id}`,
        title: service.name,
        subtitle: `state=${state} · uptime=${formatUptime(status?.uptimeSec)}`,
        source: "service",
        column: mapServiceStateToColumn(state),
        updatedTs: Date.now() - ((status?.uptimeSec ?? 0) * 1000),
        tone: (state === "error" ? "error" : state === "starting" || state === "stopping" ? "warn" : "default") as MissionCard["tone"],
      };
    });

    const runnerCards: MissionCard[] = Object.values(runnerMetaByRun)
      .map((meta) => {
        const exit = runnerExits[meta.runId];
        const outputCount = runnerOutputs[meta.runId]?.length ?? 0;
        const command = [meta.input.program, ...meta.input.args].join(" ").trim();
        const suffix = exit
          ? `exit=${exit.code ?? "?"}`
          : outputCount > 0
          ? `output=${outputCount}`
          : "queued";

        return {
          id: `runner-${meta.runId}`,
          title: command || meta.input.program,
          subtitle: `${suffix} · started ${new Date(meta.startedTs).toLocaleTimeString()}`,
          source: "runner",
          column: mapRunnerToColumn(exit, outputCount),
          updatedTs: meta.startedTs,
          tone: (exit && exit.code !== 0 ? "error" : exit ? "default" : "warn") as MissionCard["tone"],
        };
      })
      .sort((a, b) => b.updatedTs - a.updatedTs)
      .slice(0, 50);

    const feedTaskCards: MissionCard[] = feedEvents
      .filter((event) => event.category !== "system")
      .filter((event) => TASK_TRIGGER_PATTERN.test(event.message))
      .slice(0, 30)
      .map((event) => ({
        id: `feed-task-${event.id}`,
        title: event.message.slice(0, 88),
        subtitle: `${event.source} · ${new Date(event.ts).toLocaleTimeString()}`,
        source: "feed",
        column: event.severity === "error" ? "review" : "in_progress",
        updatedTs: event.ts,
        tone: event.severity === "error" ? "error" : "warn",
      }));

    return [...serviceCards, ...runnerCards, ...feedTaskCards];
  }, [feedEvents, runnerExits, runnerMetaByRun, runnerOutputs, services, statuses]);

  return (
    <div className="h-full min-h-0 flex flex-col rounded-md border bg-card">
      <div className="flex items-center justify-between border-b px-2 py-1">
        <div className="text-sm font-semibold">Mission Board</div>
        <Badge variant="outline" className="text-[10px] uppercase">
          Read only
        </Badge>
      </div>

      <ScrollArea className="min-h-0 flex-1">
        <div className="grid grid-cols-7 gap-2 p-2">
          {BOARD_COLUMNS.map((column) => {
            const items = cards.filter((card) => card.column === column.id);
            return (
              <div key={column.id} className="flex min-w-[170px] flex-col rounded-md border bg-background/50">
                <div className="flex items-center justify-between border-b px-2 py-1">
                  <span className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">{column.label}</span>
                  <Badge variant="secondary" className="h-5 px-1.5 text-[10px]">
                    {items.length}
                  </Badge>
                </div>
                <div className="flex-1 space-y-2 p-2">
                  {items.map((card) => (
                    <div key={card.id} className={`rounded border p-2 text-xs ${cardToneClass(card.tone)}`}>
                      <div className="line-clamp-2 font-medium">{card.title}</div>
                      <div className="mt-1 text-[10px] text-muted-foreground">{card.subtitle}</div>
                      <div className="mt-2 flex items-center justify-between text-[10px]">
                        <Badge variant="outline" className="h-4 px-1 uppercase">
                          {card.source}
                        </Badge>
                        <span className="text-muted-foreground">{new Date(card.updatedTs).toLocaleTimeString()}</span>
                      </div>
                    </div>
                  ))}
                  {items.length === 0 ? <div className="text-[11px] text-muted-foreground">No items</div> : null}
                </div>
              </div>
            );
          })}
        </div>
      </ScrollArea>
    </div>
  );
}
