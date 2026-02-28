import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useEffect, useMemo, useRef, useState } from "react";
import { useVirtualWindow } from "../perf/virtualization";
import type { ControlFeedEvent } from "../types";

const ROW_HEIGHT = 62;

const SOURCE_PALETTES = [
  [
    "border-sky-500/35 bg-sky-500/12 text-sky-100",
    "border-sky-400/35 bg-sky-400/12 text-sky-100",
    "border-cyan-500/35 bg-cyan-500/12 text-cyan-100",
  ],
  [
    "border-emerald-500/35 bg-emerald-500/12 text-emerald-100",
    "border-teal-500/35 bg-teal-500/12 text-teal-100",
    "border-lime-500/35 bg-lime-500/12 text-lime-100",
  ],
  [
    "border-fuchsia-500/35 bg-fuchsia-500/12 text-fuchsia-100",
    "border-violet-500/35 bg-violet-500/12 text-violet-100",
    "border-pink-500/35 bg-pink-500/12 text-pink-100",
  ],
  [
    "border-amber-500/35 bg-amber-500/12 text-amber-100",
    "border-orange-500/35 bg-orange-500/12 text-orange-100",
    "border-yellow-500/35 bg-yellow-500/12 text-yellow-100",
  ],
  [
    "border-indigo-500/35 bg-indigo-500/12 text-indigo-100",
    "border-blue-500/35 bg-blue-500/12 text-blue-100",
    "border-violet-400/35 bg-violet-400/12 text-violet-100",
  ],
] as const;

function hashText(input: string): number {
  let hash = 2166136261;
  for (let i = 0; i < input.length; i += 1) {
    hash ^= input.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

function sourceClass(source: string, message: string): string {
  const sourceHash = hashText(source);
  const palette = SOURCE_PALETTES[sourceHash % SOURCE_PALETTES.length];
  const variant = hashText(`${source}|${message}`) % palette.length;
  return palette[variant];
}

export function UnifiedLogPanel({
  events,
}: {
  events: ControlFeedEvent[];
}) {
  const [query, setQuery] = useState("");
  const [autoScroll, setAutoScroll] = useState(true);
  const [viewportHeight, setViewportHeight] = useState(220);
  const [scrollTop, setScrollTop] = useState(0);
  const viewportRef = useRef<HTMLDivElement | null>(null);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return events;
    return events.filter((event) => {
      return (
        event.source.toLowerCase().includes(q) ||
        event.message.toLowerCase().includes(q) ||
        event.category.toLowerCase().includes(q) ||
        event.severity.toLowerCase().includes(q) ||
        String(event.correlationId || "").toLowerCase().includes(q)
      );
    });
  }, [events, query]);

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

  useEffect(() => {
    const node = viewportRef.current;
    if (!node) return;
    const update = () => setViewportHeight(node.clientHeight || 220);
    update();
    const observer = new ResizeObserver(update);
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

  const sourceCount = useMemo(() => {
    const sourceSet = new Set(filtered.map((event) => event.source));
    return sourceSet.size;
  }, [filtered]);

  return (
    <div className="h-full min-h-0 flex flex-col rounded-md border bg-card">
      <div className="cr-panel-header">
        <div className="cr-panel-title">Unified Log</div>
        <div className="cr-toolbar">
          <Badge variant="outline" className="cr-badge">
            {sourceCount} sources
          </Badge>
          <Badge variant="secondary" className="cr-badge">
            {filtered.length} events
          </Badge>
        </div>
      </div>

      <div className="flex items-center gap-1 border-b px-2 py-1">
        <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search unified logs" className="cr-compact-input" />
        <Button
          size="sm"
          variant={autoScroll ? "default" : "outline"}
          className={autoScroll ? "cr-compact-btn controlroom-btn-start" : "cr-compact-btn"}
          onClick={() => setAutoScroll((prev) => !prev)}
        >
          Auto
        </Button>
      </div>

      <div
        ref={viewportRef}
        className="min-h-0 flex-1 overflow-auto"
        onScroll={(event) => setScrollTop((event.currentTarget as HTMLDivElement).scrollTop)}
      >
        <div className="font-mono text-xs">
          <div style={{ height: virtual.offsetTop }} />
          {visibleRows.map((event) => {
            const tone = sourceClass(event.source, event.message);
            return (
              <div
                key={event.id}
                className={`m-2 rounded border px-2 py-1 ${tone}`}
                style={{ minHeight: ROW_HEIGHT - 8 }}
              >
                <div className="flex items-center justify-between gap-2 text-[10px]">
                  <span>
                    [{new Date(event.ts).toLocaleTimeString()}] {event.source}
                  </span>
                  <span className="uppercase">
                    {event.category}/{event.severity}
                  </span>
                </div>
                <div className="mt-1 break-words">{event.message}</div>
                {event.correlationId ? (
                  <div className="mt-1 text-[10px] opacity-80">cid={event.correlationId}</div>
                ) : null}
              </div>
            );
          })}
          <div style={{ height: virtual.offsetBottom }} />
          {filtered.length === 0 ? <div className="p-2 text-muted-foreground">No unified logs yet.</div> : null}
        </div>
      </div>
    </div>
  );
}
