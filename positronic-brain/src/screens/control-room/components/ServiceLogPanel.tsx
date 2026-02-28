import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useEffect, useMemo, useRef, useState } from "react";
import { useVirtualWindow } from "../perf/virtualization";
import type { ServiceLogEvent, ServiceStatus } from "../types";

const LOG_TOKEN_PATTERN =
  /(\bERROR\b|\bWARN(?:ING)?\b|\bINFO\b|\bDEBUG\b|\bTRACE\b|\b\d{2}:\d{2}:\d{2}\b|\b\d{4}-\d{2}-\d{2}\b|\/Users\/[^\s\"'`]+|\"(?:[^\"\\]|\\.)+\"\s*:|\b(?:pid|port|model|state|slot|task|tokens?)=[^\s]+)/gi;
const LOG_TOKEN_EXACT_PATTERN =
  /^(?:\bERROR\b|\bWARN(?:ING)?\b|\bINFO\b|\bDEBUG\b|\bTRACE\b|\b\d{2}:\d{2}:\d{2}\b|\b\d{4}-\d{2}-\d{2}\b|\/Users\/[^\s\"'`]+|\"(?:[^\"\\]|\\.)+\"\s*:|\b(?:pid|port|model|state|slot|task|tokens?)=[^\s]+)$/i;
const ROW_HEIGHT = 24;

function levelClass(level: ServiceLogEvent["level"]) {
  if (level === "error") return "text-rose-400";
  if (level === "warn") return "text-amber-400";
  return "text-foreground";
}

function tokenClass(token: string) {
  const normalized = token.toLowerCase();
  const tokenWord = normalized.replace(/[^a-z]/g, "");

  if (tokenWord === "error") return "text-rose-300 font-semibold";
  if (tokenWord === "warn" || tokenWord === "warning") return "text-amber-300 font-medium";
  if (tokenWord === "info") return "text-sky-300";
  if (tokenWord === "debug" || tokenWord === "trace") return "text-violet-300";
  if (/^\d{2}:\d{2}:\d{2}$/.test(token) || /^\d{4}-\d{2}-\d{2}$/.test(token)) return "text-emerald-300";
  if (token.startsWith("/Users/")) return "text-cyan-300";
  if (/^".+"\s*:$/.test(token)) return "text-lime-300";
  if (normalized.includes("=")) return "text-fuchsia-200";
  return "text-foreground";
}

function highlightLine(line: string) {
  const parts = line.split(LOG_TOKEN_PATTERN);
  return parts.map((part, index) => {
    if (!part) return null;
    if (!LOG_TOKEN_EXACT_PATTERN.test(part)) return <span key={`${part}-${index}`}>{part}</span>;
    return (
      <span key={`${part}-${index}`} className={tokenClass(part)}>
        {part}
      </span>
    );
  });
}

export function ServiceLogPanel({
  serviceName,
  serviceId,
  status,
  logs,
  onClear,
  isActive = false,
  onActivate,
  collapsed = false,
  onToggleCollapsed,
}: {
  serviceName: string;
  serviceId: string;
  status?: ServiceStatus;
  logs: ServiceLogEvent[];
  onClear: (serviceId: string) => void;
  isActive?: boolean;
  onActivate?: (serviceId: string) => void;
  collapsed?: boolean;
  onToggleCollapsed?: (serviceId: string) => void;
}) {
  const [filter, setFilter] = useState("");
  const [autoScroll, setAutoScroll] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [searchIndex, setSearchIndex] = useState(-1);
  const [scrollTop, setScrollTop] = useState(0);
  const [viewportHeight, setViewportHeight] = useState(320);
  const [levels, setLevels] = useState<Record<ServiceLogEvent["level"], boolean>>({
    error: true,
    warn: true,
    info: true,
  });

  const viewportRef = useRef<HTMLDivElement | null>(null);

  const filtered = useMemo(() => {
    const value = filter.trim().toLowerCase();
    return logs.filter((entry) => {
      if (!levels[entry.level]) return false;
      if (!value) return true;
      return entry.line.toLowerCase().includes(value);
    });
  }, [logs, filter, levels]);

  const levelCounts = useMemo(() => {
    const value = filter.trim().toLowerCase();
    return logs.reduce<Record<ServiceLogEvent["level"], number>>(
      (acc, entry) => {
        if (value && !entry.line.toLowerCase().includes(value)) return acc;
        acc[entry.level] += 1;
        return acc;
      },
      { error: 0, warn: 0, info: 0 },
    );
  }, [logs, filter]);

  const searchMatches = useMemo(() => {
    const term = searchTerm.trim().toLowerCase();
    if (!term) return [] as number[];
    const indexes: number[] = [];
    filtered.forEach((entry, index) => {
      if (entry.line.toLowerCase().includes(term)) indexes.push(index);
    });
    return indexes;
  }, [filtered, searchTerm]);

  const virtual = useVirtualWindow({
    total: filtered.length,
    rowHeight: ROW_HEIGHT,
    viewportHeight,
    scrollTop,
    overscan: 24,
  });

  const visibleRows = useMemo(
    () => filtered.slice(virtual.start, virtual.end),
    [filtered, virtual.start, virtual.end],
  );

  useEffect(() => {
    const node = viewportRef.current;
    if (!node) return;

    const handleResize = () => {
      setViewportHeight(node.clientHeight || 320);
    };

    handleResize();
    const observer = new ResizeObserver(handleResize);
    observer.observe(node);

    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!autoScroll) return;
    const node = viewportRef.current;
    if (!node) return;
    node.scrollTop = node.scrollHeight;
    setScrollTop(node.scrollTop);
  }, [filtered, autoScroll]);

  function jump(next: boolean) {
    if (searchMatches.length === 0) return;
    const base = searchIndex < 0 ? 0 : searchIndex;
    const index = next
      ? (base + 1) % searchMatches.length
      : (base - 1 + searchMatches.length) % searchMatches.length;
    setSearchIndex(index);

    const targetLine = searchMatches[index] * ROW_HEIGHT;
    const node = viewportRef.current;
    if (!node) return;
    node.scrollTo({ top: targetLine, behavior: "smooth" });
  }

  async function copyLogs() {
    const raw = filtered
      .map((entry) => `[${new Date(entry.ts).toLocaleTimeString()}] ${entry.level.toUpperCase()} ${entry.line}`)
      .join("\n");
    await navigator.clipboard.writeText(raw);
  }

  const latestEntry = filtered[filtered.length - 1] ?? logs[logs.length - 1];

  return (
    <div
      className={`controlroom-card h-full min-h-0 flex flex-col rounded-md border bg-card/70 transition-all duration-200 ${
        isActive ? "border-primary/70 shadow-[0_0_0_1px_hsl(var(--primary)/0.35)]" : "hover:border-border/80"
      }`}
    >
      <div className="cr-panel-header flex-wrap">
        <button
          type="button"
          className={`cr-panel-title transition-colors ${isActive ? "text-primary" : "text-foreground hover:text-primary"}`}
          onClick={() => onActivate?.(serviceId)}
          title="Focus service"
        >
          {serviceName}
        </button>
        <Badge variant="outline" className="cr-badge">
          {status?.state ?? "stopped"}
        </Badge>
        <Badge variant="secondary" className="cr-badge">
          {filtered.length} lines
        </Badge>
        <Button size="sm" variant="outline" className="cr-compact-btn" onClick={() => onToggleCollapsed?.(serviceId)}>
          {collapsed ? "Expand" : "Collapse"}
        </Button>
        {!collapsed ? (
          <>
            <Input value={filter} onChange={(event) => setFilter(event.target.value)} placeholder="Filtro" className="cr-compact-input w-[130px]" />
            <Input
              value={searchTerm}
              onChange={(event) => {
                setSearchTerm(event.target.value);
                setSearchIndex(-1);
              }}
              placeholder="Buscar"
              className="cr-compact-input w-[130px]"
            />
            <Button
              size="sm"
              variant={levels.error ? "destructive" : "outline"}
              className={`cr-compact-btn ${!levels.error && levelCounts.error > 0 ? "border-rose-400/60 text-rose-300" : ""}`}
              onClick={() => setLevels((prev) => ({ ...prev, error: !prev.error }))}
            >
              Error ({levelCounts.error})
            </Button>
            <Button
              size="sm"
              variant={levels.warn ? "default" : "outline"}
              className={
                levels.warn
                  ? "cr-compact-btn controlroom-btn-neutral"
                  : levelCounts.warn > 0
                    ? "cr-compact-btn border-amber-400/60 text-amber-300"
                    : "cr-compact-btn"
              }
              onClick={() => setLevels((prev) => ({ ...prev, warn: !prev.warn }))}
            >
              Warn ({levelCounts.warn})
            </Button>
            <Button
              size="sm"
              variant={levels.info ? "default" : "outline"}
              className={
                levels.info
                  ? "cr-compact-btn controlroom-btn-start"
                  : levelCounts.info > 0
                    ? "cr-compact-btn border-emerald-400/60 text-emerald-300"
                    : "cr-compact-btn"
              }
              onClick={() => setLevels((prev) => ({ ...prev, info: !prev.info }))}
            >
              Info ({levelCounts.info})
            </Button>
            <Button size="sm" variant="outline" className="cr-compact-btn" onClick={() => jump(false)}>
              Prev
            </Button>
            <Button size="sm" variant="outline" className="cr-compact-btn" onClick={() => jump(true)}>
              Next
            </Button>
            <Button
              size="sm"
              variant={autoScroll ? "default" : "outline"}
              className={autoScroll ? "cr-compact-btn controlroom-btn-start" : "cr-compact-btn"}
              onClick={() => setAutoScroll((prev) => !prev)}
            >
              Auto
            </Button>
            <Button size="sm" variant="outline" className="cr-compact-btn" onClick={copyLogs}>
              Copy
            </Button>
            <Button size="sm" variant="outline" className="cr-compact-btn controlroom-btn-neutral" onClick={() => onClear(serviceId)}>
              Clear
            </Button>
          </>
        ) : null}
      </div>

      {collapsed ? (
        <div className="flex min-h-0 flex-1 items-center justify-between px-2 py-1 text-[11px] text-muted-foreground">
          <span className="truncate">
            {status?.lastError ? `Last error: ${status.lastError}` : "Panel collapsed. Click Expand to inspect logs."}
          </span>
          {latestEntry ? <span className="ml-2 shrink-0 opacity-70">{new Date(latestEntry.ts).toLocaleTimeString()}</span> : null}
        </div>
      ) : (
        <div
          ref={viewportRef}
          className="min-h-0 flex-1 overflow-auto"
          onScroll={(event) => setScrollTop((event.currentTarget as HTMLDivElement).scrollTop)}
        >
          <div className="font-mono text-[11px] leading-5">
            <div style={{ height: virtual.offsetTop }} />
            {visibleRows.map((entry, index) => {
              const absoluteIndex = virtual.start + index;
              const selectedMatch = searchMatches[searchIndex] === absoluteIndex;
              return (
                <div
                  key={`${entry.ts}-${absoluteIndex}`}
                  data-level={entry.level}
                  className={`controlroom-log-line px-2 py-0.5 ${levelClass(entry.level)} ${
                    selectedMatch ? "bg-primary/20 ring-1 ring-primary/40" : absoluteIndex % 2 === 0 ? "bg-background/5" : "bg-background/0"
                  }`}
                  style={{ height: ROW_HEIGHT }}
                >
                  <span className="mr-2 text-muted-foreground">[{new Date(entry.ts).toLocaleTimeString()}]</span>
                  <span className="mr-2 uppercase opacity-70">{entry.level}</span>
                  <span className="truncate">{highlightLine(entry.line)}</span>
                </div>
              );
            })}
            <div style={{ height: virtual.offsetBottom }} />
            {filtered.length === 0 ? (
              <div className="controlroom-empty-state flex min-h-[160px] flex-col items-center justify-center rounded-md border border-dashed border-border/50 bg-background/30 text-center">
                <div className="text-lg opacity-50">∅</div>
                <div className="mt-1 text-xs text-muted-foreground">No logs yet</div>
                <div className="text-[11px] text-muted-foreground/80">Cuando el servicio emita salida aparecerá aquí</div>
              </div>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
}
