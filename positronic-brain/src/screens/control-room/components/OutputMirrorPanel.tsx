import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { convertFileSrc } from "@tauri-apps/api/core";
import { toast } from "sonner";
import { useMemo, useState } from "react";
import {
  categoryLabel,
  categoryPalette,
  classifySource,
  type SourceCategory,
} from "../palette/sourceCategory";
import type { ServiceConfig, ServiceLogEvent } from "../types";

interface MirrorItem {
  id: string;
  ts: number;
  serviceId: string;
  serviceName: string;
  line: string;
  filePath?: string;
  pathAllowed: boolean;
  category: SourceCategory;
  kind: "message" | "file";
  previewType?: "image" | "audio";
  previewSrc?: string;
}

const OUTBOUND_PATTERNS = [
  /\bsending message\b/i,
  /\bsent message\b/i,
  /\boutbound message\b/i,
  /\breply sent\b/i,
  /\bmessage delivered\b/i,
];

const FILE_PATH_PATTERN =
  /(\/Users\/[^\s"'`]+?\.(?:png|jpg|jpeg|webp|gif|mp4|mov|mp3|wav|m4a|txt|md|json|csv|pdf))/i;
const PROJECT_PATH_SEGMENT = "/proyecto/";
const IMAGE_EXT_PATTERN = /\.(png|jpe?g|webp|gif)$/i;
const AUDIO_EXT_PATTERN = /\.(mp3|wav|m4a)$/i;

function isOutboundLine(line: string): boolean {
  return OUTBOUND_PATTERNS.some((pattern) => pattern.test(line));
}

function extractFilePath(line: string): string | undefined {
  const match = line.match(FILE_PATH_PATTERN);
  return match?.[1];
}

function isPathAllowed(path?: string): boolean {
  if (!path) return false;
  return path.includes(PROJECT_PATH_SEGMENT);
}

export function OutputMirrorPanel({
  services,
  logs,
}: {
  services: ServiceConfig[];
  logs: Record<string, ServiceLogEvent[]>;
}) {
  const [query, setQuery] = useState("");
  const [showFilesOnly, setShowFilesOnly] = useState(false);

  const items = useMemo(() => {
    const byServiceName = new Map(services.map((service) => [service.id, service.name]));
    const output: MirrorItem[] = [];

    Object.entries(logs).forEach(([serviceId, events]) => {
      const serviceName = byServiceName.get(serviceId) ?? serviceId;
      events.forEach((event, idx) => {
        const line = event.line.trim();
        if (!line) return;

        const filePath = extractFilePath(line);
        const outbound = isOutboundLine(line);
        if (!outbound && !filePath) return;
        const pathAllowed = isPathAllowed(filePath);
        const category = classifySource(serviceId, serviceName, line);
        const lowerPath = filePath?.toLowerCase() ?? "";
        const previewType = pathAllowed
          ? IMAGE_EXT_PATTERN.test(lowerPath)
            ? "image"
            : AUDIO_EXT_PATTERN.test(lowerPath)
              ? "audio"
              : undefined
          : undefined;
        const previewSrc = previewType && filePath ? convertFileSrc(filePath) : undefined;

        output.push({
          id: `${serviceId}-${event.ts}-${idx}`,
          ts: event.ts,
          serviceId,
          serviceName,
          line,
          filePath,
          pathAllowed,
          category,
          kind: filePath ? "file" : "message",
          previewType,
          previewSrc,
        });
      });
    });

    output.sort((a, b) => b.ts - a.ts);
    return output.slice(0, 600);
  }, [logs, services]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return items.filter((item) => {
      if (showFilesOnly && item.kind !== "file") return false;
      if (!q) return true;
      return (
        item.serviceName.toLowerCase().includes(q) ||
        item.line.toLowerCase().includes(q) ||
        item.filePath?.toLowerCase().includes(q)
      );
    });
  }, [items, query, showFilesOnly]);

  function copyText(value: string, label: string) {
    void navigator.clipboard
      .writeText(value)
      .then(() => toast.success(`${label} copied`))
      .catch(() => toast.error("Copy failed"));
  }

  function openFile(path: string) {
    if (!isPathAllowed(path)) {
      toast.error("Path blocked by policy");
      return;
    }
    void import("@tauri-apps/plugin-opener")
      .then(({ openPath }) => openPath(path))
      .catch((error) => toast.error(`Open failed: ${error instanceof Error ? error.message : String(error)}`));
  }

  return (
    <div className="controlroom-card flex h-full min-h-0 flex-col rounded-md border border-border/50 bg-card/35">
      <div className="cr-panel-header">
        <div className="cr-toolbar">
          <span className="cr-panel-title">Output Mirror</span>
          <Badge variant="outline" className="cr-badge">
            {filtered.length} events
          </Badge>
          <Badge variant="secondary" className="cr-badge">
            {items.filter((item) => item.kind === "file").length} files
          </Badge>
        </div>
        <div className="cr-toolbar">
          <Button
            size="sm"
            variant={showFilesOnly ? "default" : "outline"}
            className={showFilesOnly ? "cr-compact-btn controlroom-btn-neutral" : "cr-compact-btn"}
            onClick={() => setShowFilesOnly((prev) => !prev)}
          >
            Files
          </Button>
        </div>
      </div>

      <div className="flex items-center gap-1 border-t border-border/45 p-2">
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="buscar salida o fichero"
          className="cr-compact-input"
        />
      </div>

      <ScrollArea className="min-h-0 flex-1 border-t border-border/45">
        <div className="space-y-2 p-2">
          {filtered.map((item) => {
            const accent = categoryPalette(item.category, "2");
            const accentSoft = categoryPalette(item.category, "1", 0.22);
            return (
              <div
                key={item.id}
                className="rounded-md border border-border/60 bg-background/55 p-2 text-xs"
                style={{ borderLeft: `4px solid ${accent}` }}
              >
                <div className="mb-1 flex items-center justify-between gap-2">
                  <div className="flex min-w-0 items-center gap-1">
                    <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: accent }} />
                    <Badge variant={item.kind === "file" ? "default" : "secondary"} className="cr-badge">
                      {item.kind}
                    </Badge>
                    <Badge
                      variant="outline"
                      className="cr-badge"
                      style={{
                        borderColor: accent,
                        backgroundColor: accentSoft,
                        color: categoryPalette(item.category, "3"),
                      }}
                    >
                      {categoryLabel(item.category)}
                    </Badge>
                    <span className="cr-meta truncate">{item.serviceName}</span>
                  </div>
                  <span className="cr-meta">{new Date(item.ts).toLocaleTimeString()}</span>
                </div>
                <div className="break-words font-mono text-[11px]">{item.line}</div>

                {item.previewType === "image" && item.previewSrc ? (
                  <div className="mt-2">
                    <img
                      src={item.previewSrc}
                      alt={item.filePath ?? "preview"}
                      className="h-20 w-auto rounded border border-border/50 object-cover"
                      loading="lazy"
                    />
                  </div>
                ) : null}

                {item.previewType === "audio" && item.previewSrc ? (
                  <div className="mt-2">
                    <audio controls className="h-8 w-full">
                      <source src={item.previewSrc} />
                    </audio>
                  </div>
                ) : null}

                <div className="mt-2 flex flex-wrap items-center gap-1">
                  <Button size="sm" variant="outline" className="cr-compact-btn" onClick={() => copyText(item.line, "Message")}>
                    Copy
                  </Button>
                  {item.filePath && item.pathAllowed ? (
                    <Button
                      size="sm"
                      variant="outline"
                      className="cr-compact-btn"
                      onClick={() => copyText(item.filePath!, "Path")}
                    >
                      Copy path
                    </Button>
                  ) : null}
                  {item.filePath && item.pathAllowed ? (
                    <Button size="sm" variant="outline" className="cr-compact-btn" onClick={() => openFile(item.filePath!)}>
                      Open
                    </Button>
                  ) : null}
                  {item.filePath && !item.pathAllowed ? (
                    <Badge variant="destructive" className="cr-badge">
                      path blocked
                    </Badge>
                  ) : null}
                </div>

                {item.filePath ? (
                  <div className="mt-2 flex items-center justify-between gap-2 rounded border border-border/60 bg-background/65 px-2 py-1">
                    <span className="truncate font-mono text-[11px]">{item.filePath}</span>
                  </div>
                ) : null}
              </div>
            );
          })}
          {filtered.length === 0 ? (
            <div className="rounded-md border border-dashed border-border/55 p-3 text-sm text-muted-foreground">
              No hay mensajes salientes o ficheros reflejados todavía.
            </div>
          ) : null}
        </div>
      </ScrollArea>
    </div>
  );
}
