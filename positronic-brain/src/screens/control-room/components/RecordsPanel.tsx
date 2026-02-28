import { useEffect, useMemo, useRef, useState } from "react";
import { useVirtualWindow } from "../perf/virtualization";
import type { ServiceConfig, ServiceLogEvent } from "../types";

const ROW_HEIGHT = 76;

export function RecordsPanel({
  services,
  logs,
  onSelectService,
}: {
  services: ServiceConfig[];
  logs: Record<string, ServiceLogEvent[]>;
  onSelectService: (serviceId: string) => void;
}) {
  const [viewportHeight, setViewportHeight] = useState(280);
  const [scrollTop, setScrollTop] = useState(0);
  const viewportRef = useRef<HTMLDivElement | null>(null);

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
    total: services.length,
    rowHeight: ROW_HEIGHT,
    viewportHeight,
    scrollTop,
    overscan: 10,
  });

  const visibleServices = useMemo(
    () => services.slice(virtual.start, virtual.end),
    [services, virtual.start, virtual.end],
  );

  return (
    <div
      ref={viewportRef}
      className="h-full min-h-0 overflow-auto"
      onScroll={(event) => setScrollTop((event.currentTarget as HTMLDivElement).scrollTop)}
    >
      <div style={{ height: virtual.offsetTop }} />
      {visibleServices.map((service) => {
        const lines = logs[service.id] ?? [];
        const latest = lines[lines.length - 1];
        return (
          <button
            key={service.id}
            className="controlroom-card mx-2 mb-2 w-[calc(100%-1rem)] rounded-md border border-border/50 bg-background/45 p-2 text-left transition-all duration-200 hover:-translate-y-[1px] hover:border-border hover:bg-accent/40"
            onClick={() => onSelectService(service.id)}
            style={{ minHeight: ROW_HEIGHT - 8 }}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm font-semibold tracking-tight">{service.name}</span>
              <span className="text-xs text-muted-foreground">{lines.length} lines</span>
            </div>
            <div className="line-clamp-2 text-xs text-muted-foreground">
              {latest?.line || "No logs yet"}
            </div>
          </button>
        );
      })}
      <div style={{ height: virtual.offsetBottom }} />
    </div>
  );
}
