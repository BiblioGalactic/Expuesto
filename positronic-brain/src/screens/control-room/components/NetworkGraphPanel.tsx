import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  CATEGORY_LEGEND_ORDER,
  categoryFromModuleId,
  categoryLabel,
  categoryPalette,
  classifySource,
  type SourceCategory,
} from "../palette/sourceCategory";
import type { ControlFeedEvent, RealtimeBusStatus, ServiceConfig, ServiceStatus } from "../types";

type GraphNodeKind = "service" | "hub" | "module";
type HubId = "hub:user" | "hub:whatsapp" | "hub:runner" | "hub:vision" | "hub:system";
type ModuleNodeId =
  | "mod:llm"
  | "mod:rag"
  | "mod:ocr"
  | "mod:audio"
  | "mod:vlm"
  | "mod:yolo"
  | "mod:image"
  | "mod:clone"
  | "mod:aider"
  | "mod:sms"
  | "mod:web"
  | "mod:medical";
type GraphNodeId = `svc:${string}` | HubId | ModuleNodeId;

interface GraphNode {
  id: GraphNodeId;
  label: string;
  kind: GraphNodeKind;
  category: SourceCategory;
  serviceId?: string;
  state?: ServiceStatus["state"];
  inbound: number;
  outbound: number;
  lastSeenTs?: number;
}

interface GraphEdge {
  id: string;
  source: GraphNodeId;
  target: GraphNodeId;
  sourceCategory: SourceCategory;
  weight: number;
  severity: ControlFeedEvent["severity"];
  lastSeenTs: number;
}

interface SimNode {
  id: GraphNodeId;
  x: number;
  y: number;
  vx: number;
  vy: number;
  pinned: boolean;
}

const HUBS: Array<{ id: HubId; label: string }> = [
  { id: "hub:user", label: "User" },
  { id: "hub:whatsapp", label: "WhatsApp" },
  { id: "hub:runner", label: "Runner" },
  { id: "hub:vision", label: "Vision" },
  { id: "hub:system", label: "System" },
];

const MODULE_DEFS: Array<{
  id: ModuleNodeId;
  label: string;
  patterns: RegExp[];
}> = [
  { id: "mod:llm", label: "LLM", patterns: [/\bllm\b/i, /\bllama\b/i, /\bmistral\b/i, /\bdeepseek\b/i, /\bdolphin\b/i, /\bunholy\b/i, /\bmytho\b/i] },
  { id: "mod:rag", label: "RAG", patterns: [/\brag\b/i, /\bretriev/i, /\bwikirag\b/i] },
  { id: "mod:ocr", label: "OCR", patterns: [/\bocr\b/i, /\bpaddleocr\b/i, /\btext\s+detect/i] },
  { id: "mod:audio", label: "Audio", patterns: [/\baudio\b/i, /\bstt\b/i, /\bwhisper\b/i, /\btranscrib/i] },
  { id: "mod:vlm", label: "VLM", patterns: [/\bvlm\b/i, /\bqwen2\.5-vl\b/i, /\bvisual\b/i, /\bcaption\b/i] },
  { id: "mod:yolo", label: "YOLO", patterns: [/\byolo\b/i, /\bdetect/i, /\bultralytics/i] },
  { id: "mod:image", label: "Image", patterns: [/\b\/img\b/i, /\bdiffusion\b/i, /\bsdxl\b/i, /\bimage\s+gen/i] },
  { id: "mod:clone", label: "Clone", patterns: [/\bclone\b/i, /\btts\b/i, /\bvoice\b/i, /\bxtts\b/i] },
  { id: "mod:aider", label: "Aider", patterns: [/\baider\b/i, /\bgit\s+ls-files\b/i, /\bedit\b/i] },
  { id: "mod:sms", label: "SMS", patterns: [/\bsms\b/i, /\bmessages\.app\b/i, /\bosascript\b/i] },
  { id: "mod:web", label: "Web", patterns: [/\bweb\b/i, /\bscrap/i, /\burl\b/i, /\bfetch\b/i] },
  { id: "mod:medical", label: "Medical", patterns: [/\bmedical\b/i, /\bmeditron\b/i, /\bsalud\b/i, /\becg\b/i, /\blab\b/i] },
];

const PULSE_VISIBLE_MS = 9000;
const PULSE_DURATION_MS = 1400;
const MAX_EVENTS = 700;

function normalizeText(value: string) {
  return value
    .toLowerCase()
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function detectModulesInText(text: string): ModuleNodeId[] {
  const content = String(text || "");
  const matches: ModuleNodeId[] = [];
  MODULE_DEFS.forEach((moduleDef) => {
    if (moduleDef.patterns.some((pattern) => pattern.test(content))) {
      matches.push(moduleDef.id);
    }
  });
  return matches;
}

function nodeRadius(node: GraphNode, now: number) {
  const recencyBoost = node.lastSeenTs ? Math.max(0, 1 - (now - node.lastSeenTs) / 12000) : 0;
  const volume = Math.min(18, node.inbound + node.outbound);
  const base = node.kind === "hub" ? 15 : node.kind === "module" ? 9 : 11;
  return base + volume * 0.35 + recencyBoost * 3;
}

function edgeColor(severity: ControlFeedEvent["severity"], sourceCategory: SourceCategory) {
  if (severity === "error") return "rgb(239 68 68)";
  if (severity === "warn") return categoryPalette(sourceCategory, "2");
  return categoryPalette(sourceCategory, "1");
}

function hubCategory(id: HubId): SourceCategory {
  if (id === "hub:whatsapp") return "systems";
  if (id === "hub:vision") return "vision";
  if (id === "hub:runner") return "dev";
  return "unknown";
}

function buildGraph(
  services: ServiceConfig[],
  statuses: Record<string, ServiceStatus>,
  feedEvents: ControlFeedEvent[],
) {
  const nodes = new Map<GraphNodeId, GraphNode>();
  const edges = new Map<string, GraphEdge>();

  HUBS.forEach((hub) => {
    nodes.set(hub.id, {
      id: hub.id,
      label: hub.label,
      kind: "hub",
      category: hubCategory(hub.id),
      inbound: 0,
      outbound: 0,
    });
  });

  MODULE_DEFS.forEach((moduleDef) => {
    nodes.set(moduleDef.id, {
      id: moduleDef.id,
      label: moduleDef.label,
      kind: "module",
      category: categoryFromModuleId(moduleDef.id),
      inbound: 0,
      outbound: 0,
    });
  });

  const serviceMatcher = services.map((service) => ({
    serviceId: service.id,
    nodeId: `svc:${service.id}` as const,
    idNorm: normalizeText(service.id),
    nameNorm: normalizeText(service.name),
  }));

  serviceMatcher.forEach((entry) => {
    nodes.set(entry.nodeId, {
      id: entry.nodeId,
      label: services.find((service) => service.id === entry.serviceId)?.name ?? entry.serviceId,
      kind: "service",
      category: classifySource(entry.serviceId, services.find((service) => service.id === entry.serviceId)?.name, ""),
      serviceId: entry.serviceId,
      state: statuses[entry.serviceId]?.state ?? "stopped",
      inbound: 0,
      outbound: 0,
    });
  });

  const touchNode = (nodeId: GraphNodeId, direction: "inbound" | "outbound", ts: number, amount = 1) => {
    const node = nodes.get(nodeId);
    if (!node) return;
    if (direction === "inbound") node.inbound += amount;
    else node.outbound += amount;
    node.lastSeenTs = ts;
  };

  const addEdge = (
    source: GraphNodeId,
    target: GraphNodeId,
    severity: ControlFeedEvent["severity"],
    ts: number,
    amount = 1,
  ) => {
    if (source === target) return;
    const edgeId = `${source}->${target}`;
    const current = edges.get(edgeId);
    const sourceCategory = nodes.get(source)?.category ?? "unknown";
    edges.set(edgeId, {
      id: edgeId,
      source,
      target,
      sourceCategory,
      weight: (current?.weight ?? 0) + amount,
      severity:
        severity === "error" || current?.severity === "error"
          ? "error"
          : severity === "warn" || current?.severity === "warn"
            ? "warn"
            : "info",
      lastSeenTs: ts,
    });

    touchNode(source, "outbound", ts, amount);
    touchNode(target, "inbound", ts, amount);
  };

  const findServiceInText = (text: string, exclude?: GraphNodeId): GraphNodeId | undefined => {
    const norm = normalizeText(text);
    if (!norm) return undefined;
    for (const candidate of serviceMatcher) {
      if (exclude === candidate.nodeId) continue;
      if (!candidate.idNorm && !candidate.nameNorm) continue;
      if (candidate.idNorm && norm.includes(candidate.idNorm)) return candidate.nodeId;
      if (candidate.nameNorm && norm.includes(candidate.nameNorm)) return candidate.nodeId;
    }
    return undefined;
  };

  const resolveSource = (event: ControlFeedEvent): GraphNodeId => {
    const bySource = findServiceInText(event.source);
    if (bySource) return bySource;
    const sourceModules = detectModulesInText(event.source);
    if (sourceModules.length > 0) return sourceModules[0];
    if (event.category === "runner") return "hub:runner";
    if (event.category === "video") return "hub:vision";
    if (/whatsapp|wa[_-]?bridge|baileys/i.test(event.source)) return "hub:whatsapp";
    if (event.category === "agent") return "hub:user";
    return "hub:system";
  };

  const resolveTarget = (event: ControlFeedEvent, source: GraphNodeId): GraphNodeId => {
    const byMessage = findServiceInText(event.message, source);
    if (byMessage) return byMessage;

    const messageModules = detectModulesInText(event.message);
    if (messageModules.length > 0 && source !== messageModules[0]) return messageModules[0];

    if (source.startsWith("svc:")) {
      if (event.category === "video") return "hub:vision";
      if (event.category === "runner") return "hub:runner";
      return "hub:user";
    }
    if (source.startsWith("mod:")) return "hub:system";
    if (event.category === "runner") return "hub:system";
    if (event.category === "video") return "hub:vision";
    if (source === "hub:whatsapp") return "hub:user";
    return "hub:system";
  };

  const recent = [...feedEvents].slice(0, MAX_EVENTS).reverse();
  recent.forEach((event) => {
    const source = resolveSource(event);
    const target = resolveTarget(event, source);
    addEdge(source, target, event.severity, event.ts, 1);

    const modules = detectModulesInText(`${event.source} ${event.message}`);
    modules.forEach((moduleId, index) => {
      const amount = index === 0 ? 0.75 : 0.5;
      addEdge(source, moduleId, event.severity, event.ts, amount);
      addEdge(moduleId, target, event.severity, event.ts, amount);
    });
  });

  return {
    nodes: Array.from(nodes.values()),
    edges: Array.from(edges.values()),
  };
}

function seededPosition(id: string) {
  let hash = 0;
  for (let i = 0; i < id.length; i += 1) {
    hash = (hash * 31 + id.charCodeAt(i)) >>> 0;
  }
  const x = ((hash & 0xffff) / 0xffff) * 2 - 1;
  const y = (((hash >> 16) & 0xffff) / 0xffff) * 2 - 1;
  return { x, y };
}

function pinHubPosition(id: HubId, width: number, height: number) {
  const padX = Math.max(70, width * 0.08);
  const padY = Math.max(46, height * 0.1);
  if (id === "hub:user") return { x: width * 0.5, y: padY };
  if (id === "hub:whatsapp") return { x: padX, y: height * 0.34 };
  if (id === "hub:runner") return { x: padX + 14, y: height * 0.76 };
  if (id === "hub:vision") return { x: width - padX, y: height * 0.76 };
  return { x: width - padX, y: height * 0.34 };
}

export function NetworkGraphPanel({
  services,
  statuses,
  feedEvents,
  busStatus,
  expanded = false,
  onToggleExpanded,
}: {
  services: ServiceConfig[];
  statuses: Record<string, ServiceStatus>;
  feedEvents: ControlFeedEvent[];
  busStatus: RealtimeBusStatus;
  expanded?: boolean;
  onToggleExpanded?: () => void;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const simRef = useRef<Map<GraphNodeId, SimNode>>(new Map());
  const rafRef = useRef<number | null>(null);

  const [size, setSize] = useState({ width: 980, height: 420 });
  const [freeze, setFreeze] = useState(false);
  const [nowTs, setNowTs] = useState(() => Date.now());
  const [, setRenderTick] = useState(0);

  const graph = useMemo(() => buildGraph(services, statuses, feedEvents), [services, statuses, feedEvents]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setNowTs(Date.now());
    }, 220);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    const node = containerRef.current;
    if (!node) return;
    const update = () => {
      setSize({
        width: Math.max(420, node.clientWidth),
        height: Math.max(280, node.clientHeight),
      });
    };
    update();
    const observer = new ResizeObserver(update);
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const next = new Map<GraphNodeId, SimNode>();
    const prev = simRef.current;
    const cx = size.width / 2;
    const cy = size.height / 2;
    const serviceNodes = graph.nodes.filter((node) => node.kind === "service");

    graph.nodes.forEach((node, index) => {
      const existing = prev.get(node.id);
      if (existing) {
        next.set(node.id, { ...existing });
        return;
      }

      if (node.id.startsWith("hub:")) {
        const pinned = pinHubPosition(node.id as HubId, size.width, size.height);
        next.set(node.id, {
          id: node.id,
          x: pinned.x,
          y: pinned.y,
          vx: 0,
          vy: 0,
          pinned: true,
        });
        return;
      }

      const seed = seededPosition(node.id);
      const ring = node.id.startsWith("mod:") ? 110 + (index % 5) * 14 : 80 + (index % 6) * 12;
      next.set(node.id, {
        id: node.id,
        x: cx + seed.x * ring,
        y: cy + seed.y * ring,
        vx: 0,
        vy: 0,
        pinned: false,
      });
    });

    if (serviceNodes.length === 0) {
      HUBS.forEach((hub) => {
        const pinned = pinHubPosition(hub.id, size.width, size.height);
        const current = next.get(hub.id);
        if (current) {
          current.x = pinned.x;
          current.y = pinned.y;
          current.vx = 0;
          current.vy = 0;
          current.pinned = true;
        }
      });
    }

    simRef.current = next;
  }, [graph.nodes, size.height, size.width]);

  useEffect(() => {
    if (freeze) return;

    const damping = 0.9;
    const repulsionK = 6200;
    const springK = 0.0025;
    const centerK = 0.0052;
    const pad = 24;

    const step = () => {
      const nodes = simRef.current;
      if (nodes.size === 0) {
        rafRef.current = window.requestAnimationFrame(step);
        return;
      }

      HUBS.forEach((hub) => {
        const current = nodes.get(hub.id);
        if (!current) return;
        const pinned = pinHubPosition(hub.id, size.width, size.height);
        current.x = pinned.x;
        current.y = pinned.y;
        current.vx = 0;
        current.vy = 0;
      });

      const list = Array.from(nodes.values());
      for (let i = 0; i < list.length; i += 1) {
        for (let j = i + 1; j < list.length; j += 1) {
          const a = list[i];
          const b = list[j];
          const dx = b.x - a.x;
          const dy = b.y - a.y;
          const d2 = dx * dx + dy * dy + 0.001;
          const d = Math.sqrt(d2);
          const force = repulsionK / d2;
          const fx = (dx / d) * force;
          const fy = (dy / d) * force;
          if (!a.pinned) {
            a.vx -= fx;
            a.vy -= fy;
          }
          if (!b.pinned) {
            b.vx += fx;
            b.vy += fy;
          }
        }
      }

      graph.edges.forEach((edge) => {
        const source = nodes.get(edge.source);
        const target = nodes.get(edge.target);
        if (!source || !target) return;
        const dx = target.x - source.x;
        const dy = target.y - source.y;
        const d = Math.max(1, Math.hypot(dx, dy));
        const rest =
          edge.source.startsWith("hub:") || edge.target.startsWith("hub:")
            ? 130
            : edge.source.startsWith("mod:") || edge.target.startsWith("mod:")
              ? 105
              : 82;
        const stretch = d - rest;
        const force = stretch * springK * (1 + Math.min(3, edge.weight / 10));
        const fx = (dx / d) * force;
        const fy = (dy / d) * force;
        if (!source.pinned) {
          source.vx += fx;
          source.vy += fy;
        }
        if (!target.pinned) {
          target.vx -= fx;
          target.vy -= fy;
        }
      });

      const cx = size.width / 2;
      const cy = size.height / 2;
      list.forEach((node) => {
        if (node.pinned) return;
        node.vx += (cx - node.x) * centerK;
        node.vy += (cy - node.y) * centerK;

        node.vx *= damping;
        node.vy *= damping;
        node.x += node.vx;
        node.y += node.vy;

        if (node.x < pad) {
          node.x = pad;
          node.vx *= -0.3;
        }
        if (node.x > size.width - pad) {
          node.x = size.width - pad;
          node.vx *= -0.3;
        }
        if (node.y < pad) {
          node.y = pad;
          node.vy *= -0.3;
        }
        if (node.y > size.height - pad) {
          node.y = size.height - pad;
          node.vy *= -0.3;
        }
      });

      setRenderTick((value) => value + 1);
      rafRef.current = window.requestAnimationFrame(step);
    };

    rafRef.current = window.requestAnimationFrame(step);
    return () => {
      if (rafRef.current !== null) window.cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    };
  }, [freeze, graph.edges, size.height, size.width]);

  const eventRatePerMin = useMemo(() => {
    const fromTs = nowTs - 60000;
    return feedEvents.filter((event) => event.ts >= fromTs).length;
  }, [feedEvents, nowTs]);

  const positions = simRef.current;
  const online = busStatus.state === "online";

  return (
    <div className="controlroom-card flex h-full min-h-0 flex-col rounded-md border border-border/50 bg-card/35">
      <div className="cr-panel-header">
        <div className="cr-toolbar">
          <span className="cr-panel-title">Network View</span>
          <Badge variant={online ? "default" : "destructive"} className="cr-badge">
            {online ? "live" : busStatus.state}
          </Badge>
          <span className="cr-meta">{graph.nodes.length} nodes</span>
          <span className="cr-meta">{graph.edges.length} edges</span>
          <span className="cr-meta">{eventRatePerMin}/min</span>
        </div>
        <div className="cr-toolbar">
          {onToggleExpanded ? (
            <Button size="sm" variant="outline" className="cr-compact-btn" onClick={onToggleExpanded}>
              {expanded ? "Exit Fullscreen" : "Expand"}
            </Button>
          ) : null}
          <Button size="sm" variant={freeze ? "default" : "outline"} className="cr-compact-btn" onClick={() => setFreeze((prev) => !prev)}>
            {freeze ? "Resume" : "Freeze"}
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 border-t border-border/45 px-2 py-1">
        {CATEGORY_LEGEND_ORDER.map((category) => (
          <div key={category} className="inline-flex items-center gap-1 rounded border border-border/45 px-1.5 py-0.5">
            <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: categoryPalette(category, "2") }} />
            <span className="cr-meta">{categoryLabel(category)}</span>
          </div>
        ))}
      </div>

      <div ref={containerRef} className="min-h-0 flex-1 overflow-hidden p-2">
        <svg viewBox={`0 0 ${size.width} ${size.height}`} className="h-full w-full rounded-md border border-border/45 bg-background/40">
          <defs>
            <linearGradient id="edge-grad" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="rgba(168,85,247,0.2)" />
              <stop offset="100%" stopColor="rgba(249,115,22,0.2)" />
            </linearGradient>
          </defs>

          <rect x={0} y={0} width={size.width} height={size.height} fill="url(#edge-grad)" />

          {graph.edges.map((edge) => {
            const source = positions.get(edge.source);
            const target = positions.get(edge.target);
            if (!source || !target) return null;
            const age = Math.max(0, nowTs - edge.lastSeenTs);
            const active = age <= PULSE_VISIBLE_MS;
            const progress = (age % PULSE_DURATION_MS) / PULSE_DURATION_MS;
            const pulseX = source.x + (target.x - source.x) * progress;
            const pulseY = source.y + (target.y - source.y) * progress;

            return (
              <g key={edge.id}>
                <line
                  x1={source.x}
                  y1={source.y}
                  x2={target.x}
                  y2={target.y}
                  stroke={edgeColor(edge.severity, edge.sourceCategory)}
                  strokeOpacity={Math.min(0.95, 0.24 + edge.weight * 0.06)}
                  strokeWidth={Math.max(1, Math.min(5, 1 + edge.weight * 0.12))}
                />
                {active ? (
                  <circle
                    cx={pulseX}
                    cy={pulseY}
                    r={3.2}
                    fill={
                      edge.severity === "error"
                        ? "rgb(239 68 68 / 0.95)"
                        : categoryPalette(edge.sourceCategory, "3", 0.95)
                    }
                  />
                ) : null}
              </g>
            );
          })}

          {graph.nodes.map((node) => {
            const pos = positions.get(node.id);
            if (!pos) return null;
            const recencyGlow = node.lastSeenTs ? Math.max(0, 1 - (nowTs - node.lastSeenTs) / 8000) : 0;
            const radius = nodeRadius(node, nowTs);
            const nodeColor = categoryPalette(node.category, "2");
            const strokeColor =
              node.kind === "service" && node.state === "error"
                ? "rgb(239 68 68 / 0.95)"
                : "rgb(255 255 255 / 0.25)";
            return (
              <g key={node.id}>
                <circle
                  cx={pos.x}
                  cy={pos.y}
                  r={radius + recencyGlow * 6}
                  fill={nodeColor}
                  fillOpacity={0.14 + recencyGlow * 0.16}
                />
                <circle
                  cx={pos.x}
                  cy={pos.y}
                  r={radius}
                  fill={nodeColor}
                  fillOpacity={0.85}
                  stroke={strokeColor}
                  strokeWidth={1.2}
                />
                <text
                  x={pos.x}
                  y={pos.y + radius + 13}
                  textAnchor="middle"
                  className="select-none fill-foreground"
                  style={{ fontSize: "10px", fontWeight: 600 }}
                >
                  {node.label}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}
