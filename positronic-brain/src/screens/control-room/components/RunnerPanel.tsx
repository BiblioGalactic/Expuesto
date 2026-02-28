import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { useMemo, useState } from "react";
import type { RunnerCommandInput, RunnerExitEvent, RunnerOutputEvent } from "../types";

function parseArgs(raw: string): string[] {
  const out: string[] = [];
  const re = /"([^"]*)"|'([^']*)'|([^\s]+)/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(raw)) !== null) {
    out.push(m[1] ?? m[2] ?? m[3]);
  }
  return out;
}

function extractDropPaths(event: React.DragEvent<HTMLDivElement>) {
  const fromFiles = Array.from(event.dataTransfer.files)
    .map((file) => (file as File & { path?: string }).path || file.name)
    .filter(Boolean);

  if (fromFiles.length > 0) return fromFiles;

  const text = event.dataTransfer.getData("text/plain") || event.dataTransfer.getData("text/uri-list") || "";
  if (!text.trim()) return [];
  return text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
}

export function RunnerPanel({
  history,
  outputsByRun,
  exitsByRun,
  onExecute,
  onCancel,
}: {
  history: RunnerCommandInput[];
  outputsByRun: Record<string, RunnerOutputEvent[]>;
  exitsByRun: Record<string, RunnerExitEvent>;
  onExecute: (input: RunnerCommandInput) => Promise<string | null>;
  onCancel: (runId: string) => Promise<void>;
}) {
  const [program, setProgram] = useState("");
  const [args, setArgs] = useState("");
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  const activeLines = useMemo(() => {
    if (!activeRunId) return [] as RunnerOutputEvent[];
    return outputsByRun[activeRunId] ?? [];
  }, [outputsByRun, activeRunId]);

  const activeExit = activeRunId ? exitsByRun[activeRunId] : undefined;

  async function run() {
    const cmd = program.trim();
    if (!cmd) return;
    setRunning(true);
    try {
      const runId = await onExecute({ program: cmd, args: parseArgs(args) });
      if (runId) setActiveRunId(runId);
    } finally {
      setRunning(false);
    }
  }

  function useHistoryItem(item: RunnerCommandInput) {
    setProgram(item.program);
    setArgs(item.args.join(" "));
  }

  return (
    <div
      className="h-full min-h-0 flex flex-col rounded-md border bg-card"
      onDragOver={(event) => event.preventDefault()}
      onDrop={(event) => {
        event.preventDefault();
        const paths = extractDropPaths(event);
        if (paths.length > 0) {
          const suffix = paths.map((path) => `"${path}"`).join(" ");
          setArgs((prev) => `${prev} ${suffix}`.trim());
        }
      }}
    >
      <div className="border-b p-2 space-y-2">
        <div className="flex items-center justify-between gap-2">
          <div className="text-sm font-semibold">Runner</div>
          {activeRunId ? <Badge variant="outline">{activeRunId.slice(0, 8)}</Badge> : null}
        </div>

        <Input placeholder="program" value={program} onChange={(event) => setProgram(event.target.value)} className="h-8" />
        <Input
          placeholder="args (drag and drop files/rutas here)"
          value={args}
          onChange={(event) => setArgs(event.target.value)}
          className="h-8"
        />
        <div className="flex gap-2">
          <Button size="sm" onClick={run} disabled={running}>
            Execute
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              if (!activeRunId) return;
              void onCancel(activeRunId);
            }}
            disabled={!activeRunId}
          >
            Cancel
          </Button>
        </div>
      </div>

      <div className="border-b p-2">
        <div className="mb-1 text-xs text-muted-foreground">History</div>
        <div className="flex flex-wrap gap-1">
          {history.slice(0, 8).map((entry, index) => (
            <Button key={`${entry.program}-${index}`} size="sm" variant="secondary" onClick={() => useHistoryItem(entry)}>
              {entry.program}
            </Button>
          ))}
        </div>
      </div>

      <ScrollArea className="min-h-0 flex-1">
        <div className="space-y-1 p-2 font-mono text-xs">
          {activeLines.map((line, index) => (
            <div key={`${line.ts}-${index}`} className={line.stream === "stderr" ? "text-rose-400" : "text-foreground"}>
              <span className="mr-2 text-muted-foreground">[{new Date(line.ts).toLocaleTimeString()}]</span>
              <span className="mr-2 uppercase opacity-70">{line.stream}</span>
              {line.line}
            </div>
          ))}
          {activeExit ? (
            <div className="pt-2 text-muted-foreground">
              Process finished · code={activeExit.code ?? "null"} signal={activeExit.signal ?? "null"}
            </div>
          ) : null}
          {activeLines.length === 0 ? <div className="text-muted-foreground">No runner output.</div> : null}
        </div>
      </ScrollArea>
    </div>
  );
}
