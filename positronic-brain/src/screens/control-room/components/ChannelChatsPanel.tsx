import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { useEffect, useMemo, useRef, useState } from "react";
import { useVirtualWindow } from "../perf/virtualization";
import type { ServiceConfig, ServiceLogEvent } from "../types";

type ChannelId =
  | "whatsapp"
  | "telegram"
  | "discord"
  | "slack"
  | "imessage"
  | "openclaw"
  | "generic";

type MessageDirection = "inbound" | "outbound" | "system";

interface ChatLine {
  id: string;
  ts: number;
  text: string;
  level: ServiceLogEvent["level"];
  direction: MessageDirection;
  serviceId: string;
  correlationId?: string;
}

interface Conversation {
  key: string;
  channel: ChannelId;
  chatId: string;
  label: string;
  lastTs: number;
  inboundCount: number;
  outboundCount: number;
  totalCount: number;
  events: ChatLine[];
}

const CHANNEL_LABELS: Record<ChannelId, string> = {
  whatsapp: "WhatsApp",
  telegram: "Telegram",
  discord: "Discord",
  slack: "Slack",
  imessage: "iMessage",
  openclaw: "OpenClaw",
  generic: "Generic",
};

const CHANNEL_ORDER: ChannelId[] = ["whatsapp", "telegram", "discord", "slack", "imessage", "openclaw", "generic"];
const MAX_EVENTS_PER_CHAT = 800;
const CHAT_ROW_HEIGHT = 52;
const MESSAGE_ROW_HEIGHT = 72;

function inferChannel(service: ServiceConfig, line: string): ChannelId {
  const haystack = `${service.id} ${service.name} ${line}`.toLowerCase();
  if (haystack.includes("whatsapp") || haystack.includes("wa-bridge") || haystack.includes("@s.whatsapp.net")) return "whatsapp";
  if (haystack.includes("telegram")) return "telegram";
  if (haystack.includes("discord")) return "discord";
  if (haystack.includes("slack")) return "slack";
  if (haystack.includes("imessage")) return "imessage";
  if (haystack.includes("openclaw") || haystack.includes("gateway")) return "openclaw";
  return "generic";
}

function normalizePeer(raw: string): string {
  return raw.replace(/[),;]+$/g, "").trim();
}

function inferDirection(line: string): MessageDirection {
  const lower = line.toLowerCase();
  if (lower.includes("inbound message") || lower.includes("received message")) return "inbound";
  if (lower.includes("sending message") || lower.includes("sent message") || lower.includes("outbound message")) return "outbound";
  return "system";
}

function extractChatId(channel: ChannelId, line: string, serviceId: string): string {
  const inboundPair = line.match(/inbound message\s+([^\s]+)\s*->\s*([^\s]+)/i);
  if (inboundPair) {
    const left = normalizePeer(inboundPair[1]);
    const right = normalizePeer(inboundPair[2]);
    return left === right ? left : `${left} <-> ${right}`;
  }

  const outboundTarget = line.match(/(?:sending message|sent message(?:\s+\S+)?)\s*->\s*([^\s]+)/i);
  if (outboundTarget) return normalizePeer(outboundTarget[1]);

  if (channel === "whatsapp") {
    const jid = line.match(/([0-9]{6,}@s\.whatsapp\.net)/i);
    if (jid) return normalizePeer(jid[1]);
    const phone = line.match(/(\+[0-9]{6,})/);
    if (phone) return normalizePeer(phone[1]);
  }

  if (channel === "telegram") {
    const tgHandle = line.match(/(@[A-Za-z0-9_]+)/);
    if (tgHandle) return normalizePeer(tgHandle[1]);
  }

  const genericArrow = line.match(/->\s*([^\s]+)/);
  if (genericArrow) return normalizePeer(genericArrow[1]);

  return serviceId;
}

function messageTone(direction: MessageDirection, level: ServiceLogEvent["level"]): string {
  if (level === "error") return "border-rose-500/40 bg-rose-500/10 text-rose-200";
  if (direction === "inbound") return "border-emerald-500/35 bg-emerald-500/10 text-emerald-100";
  if (direction === "outbound") return "border-sky-500/35 bg-sky-500/10 text-sky-100";
  return "border-border/60 bg-background/70 text-muted-foreground";
}

function formatTime(ts: number): string {
  return new Date(ts).toLocaleTimeString();
}

export function ChannelChatsPanel({
  services,
  logs,
}: {
  services: ServiceConfig[];
  logs: Record<string, ServiceLogEvent[]>;
}) {
  const [selectedChannel, setSelectedChannel] = useState<ChannelId | null>(null);
  const [selectedConversationKey, setSelectedConversationKey] = useState<string | null>(null);
  const [chatQuery, setChatQuery] = useState("");

  const [chatViewportHeight, setChatViewportHeight] = useState(260);
  const [chatScrollTop, setChatScrollTop] = useState(0);
  const [messageViewportHeight, setMessageViewportHeight] = useState(260);
  const [messageScrollTop, setMessageScrollTop] = useState(0);

  const chatViewportRef = useRef<HTMLDivElement | null>(null);
  const messageViewportRef = useRef<HTMLDivElement | null>(null);

  const { channelEntries, conversationsByChannel, totalEvents } = useMemo(() => {
    const channelCounts = new Map<ChannelId, number>();
    const conversationMap = new Map<string, Conversation>();
    let eventsCount = 0;

    services.forEach((service) => {
      const serviceLogs = logs[service.id] ?? [];
      serviceLogs.forEach((entry, idx) => {
        const line = entry.line.trim();
        if (!line) return;

        const channel = inferChannel(service, line);
        const chatId = extractChatId(channel, line, service.id);
        const direction = inferDirection(line);
        const key = `${channel}::${chatId}`;
        const existing = conversationMap.get(key);

        const item: ChatLine = {
          id: `${service.id}-${entry.ts}-${idx}`,
          ts: entry.ts,
          text: line,
          level: entry.level,
          direction,
          serviceId: service.id,
          correlationId: entry.correlationId,
        };

        if (!existing) {
          conversationMap.set(key, {
            key,
            channel,
            chatId,
            label: chatId,
            lastTs: entry.ts,
            inboundCount: direction === "inbound" ? 1 : 0,
            outboundCount: direction === "outbound" ? 1 : 0,
            totalCount: 1,
            events: [item],
          });
        } else {
          existing.lastTs = Math.max(existing.lastTs, entry.ts);
          existing.totalCount += 1;
          if (direction === "inbound") existing.inboundCount += 1;
          if (direction === "outbound") existing.outboundCount += 1;
          existing.events.push(item);
          if (existing.events.length > MAX_EVENTS_PER_CHAT) {
            existing.events = existing.events.slice(-MAX_EVENTS_PER_CHAT);
          }
        }

        channelCounts.set(channel, (channelCounts.get(channel) ?? 0) + 1);
        eventsCount += 1;
      });
    });

    const grouped = new Map<ChannelId, Conversation[]>();
    conversationMap.forEach((value) => {
      const current = grouped.get(value.channel) ?? [];
      current.push(value);
      grouped.set(value.channel, current);
    });

    grouped.forEach((items, key) => {
      grouped.set(
        key,
        items.sort((a, b) => b.lastTs - a.lastTs),
      );
    });

    const channels = CHANNEL_ORDER.filter((id) => (channelCounts.get(id) ?? 0) > 0).map((id) => ({
      id,
      label: CHANNEL_LABELS[id],
      count: channelCounts.get(id) ?? 0,
      chats: (grouped.get(id) ?? []).length,
    }));

    return {
      channelEntries: channels,
      conversationsByChannel: grouped,
      totalEvents: eventsCount,
    };
  }, [logs, services]);

  useEffect(() => {
    if (!selectedChannel || !channelEntries.some((entry) => entry.id === selectedChannel)) {
      setSelectedChannel(channelEntries[0]?.id ?? null);
    }
  }, [channelEntries, selectedChannel]);

  const visibleConversations = useMemo(() => {
    if (!selectedChannel) return [];
    const query = chatQuery.trim().toLowerCase();
    const source = conversationsByChannel.get(selectedChannel) ?? [];
    if (!query) return source;
    return source.filter((item) => item.label.toLowerCase().includes(query) || item.chatId.toLowerCase().includes(query));
  }, [chatQuery, conversationsByChannel, selectedChannel]);

  useEffect(() => {
    if (!selectedConversationKey || !visibleConversations.some((entry) => entry.key === selectedConversationKey)) {
      setSelectedConversationKey(visibleConversations[0]?.key ?? null);
    }
  }, [selectedConversationKey, visibleConversations]);

  const activeConversation = useMemo(() => {
    return visibleConversations.find((entry) => entry.key === selectedConversationKey) ?? visibleConversations[0] ?? null;
  }, [selectedConversationKey, visibleConversations]);

  useEffect(() => {
    const node = chatViewportRef.current;
    if (!node) return;
    const update = () => setChatViewportHeight(node.clientHeight || 260);
    update();
    const observer = new ResizeObserver(update);
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const node = messageViewportRef.current;
    if (!node) return;
    const update = () => setMessageViewportHeight(node.clientHeight || 260);
    update();
    const observer = new ResizeObserver(update);
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const node = messageViewportRef.current;
    if (!node) return;
    node.scrollTop = node.scrollHeight;
    setMessageScrollTop(node.scrollTop);
  }, [activeConversation?.events.length]);

  const conversationVirtual = useVirtualWindow({
    total: visibleConversations.length,
    rowHeight: CHAT_ROW_HEIGHT,
    viewportHeight: chatViewportHeight,
    scrollTop: chatScrollTop,
    overscan: 8,
  });

  const messageCount = activeConversation?.events.length ?? 0;
  const messageVirtual = useVirtualWindow({
    total: messageCount,
    rowHeight: MESSAGE_ROW_HEIGHT,
    viewportHeight: messageViewportHeight,
    scrollTop: messageScrollTop,
    overscan: 10,
  });

  const visibleChats = useMemo(
    () => visibleConversations.slice(conversationVirtual.start, conversationVirtual.end),
    [visibleConversations, conversationVirtual.start, conversationVirtual.end],
  );

  const visibleMessages = useMemo(() => {
    if (!activeConversation) return [] as ChatLine[];
    return activeConversation.events.slice(messageVirtual.start, messageVirtual.end);
  }, [activeConversation, messageVirtual.start, messageVirtual.end]);

  return (
    <div className="h-full min-h-0 flex flex-col rounded-md border bg-card">
      <div className="cr-panel-header">
        <div className="cr-panel-title">Channels Live</div>
        <div className="cr-toolbar">
          <Badge variant="outline" className="cr-badge">
            {channelEntries.length} channels
          </Badge>
          <Badge variant="secondary" className="cr-badge">
            {totalEvents} events
          </Badge>
        </div>
      </div>

      <div className="flex flex-wrap gap-1 border-b px-2 py-1">
        {channelEntries.map((channel) => (
          <button
            type="button"
            key={channel.id}
            onClick={() => setSelectedChannel(channel.id)}
            className={`rounded border px-2 py-1 text-[10px] uppercase transition-colors ${
              selectedChannel === channel.id
                ? "border-primary bg-primary/20 text-primary"
                : "border-border text-muted-foreground hover:text-foreground"
            }`}
          >
            {channel.label} ({channel.chats})
          </button>
        ))}
      </div>

      <div className="border-b px-2 py-1">
        <Input value={chatQuery} onChange={(event) => setChatQuery(event.target.value)} placeholder="Buscar chat" className="cr-compact-input" />
      </div>

      <div className="grid min-h-0 flex-1 grid-cols-[42%_58%]">
        <div
          ref={chatViewportRef}
          className="min-h-0 overflow-auto border-r"
          onScroll={(event) => setChatScrollTop((event.currentTarget as HTMLDivElement).scrollTop)}
        >
          <div style={{ height: conversationVirtual.offsetTop }} />
          {visibleChats.map((chat) => (
            <button
              key={chat.key}
              type="button"
              onClick={() => setSelectedConversationKey(chat.key)}
              className={`m-2 w-[calc(100%-1rem)] rounded border px-2 py-1 text-left text-xs transition-colors ${
                activeConversation?.key === chat.key ? "border-primary bg-primary/10" : "bg-background/40 hover:bg-background/60"
              }`}
              style={{ minHeight: CHAT_ROW_HEIGHT - 8 }}
            >
              <div className="truncate font-medium">{chat.label}</div>
              <div className="mt-1 flex items-center justify-between text-[10px] text-muted-foreground">
                <span>
                  in {chat.inboundCount} · out {chat.outboundCount}
                </span>
                <span>{formatTime(chat.lastTs)}</span>
              </div>
            </button>
          ))}
          <div style={{ height: conversationVirtual.offsetBottom }} />
          {visibleConversations.length === 0 ? <div className="p-2 text-xs text-muted-foreground">No chats found.</div> : null}
        </div>

        <div className="min-h-0 flex flex-col">
          <div className="border-b px-2 py-1">
            <div className="truncate text-xs font-medium">
              {activeConversation ? `${CHANNEL_LABELS[activeConversation.channel]} · ${activeConversation.label}` : "Selecciona un chat"}
            </div>
            <div className="text-[10px] text-muted-foreground">
              {activeConversation ? `${activeConversation.totalCount} events` : "Sin datos"}
            </div>
          </div>

          <div
            ref={messageViewportRef}
            className="min-h-0 flex-1 overflow-auto"
            onScroll={(event) => setMessageScrollTop((event.currentTarget as HTMLDivElement).scrollTop)}
          >
            <div style={{ height: messageVirtual.offsetTop }} />
            {visibleMessages.map((event) => (
              <div
                key={event.id}
                className={`m-2 rounded border px-2 py-1 text-xs ${messageTone(event.direction, event.level)}`}
                style={{ minHeight: MESSAGE_ROW_HEIGHT - 8 }}
              >
                <div className="mb-1 flex items-center justify-between gap-2 text-[10px] opacity-80">
                  <span className="uppercase">
                    {event.direction} · {event.level}
                  </span>
                  <span>{formatTime(event.ts)}</span>
                </div>
                <div className="line-clamp-2 break-words">{event.text}</div>
                {event.correlationId ? (
                  <div className="mt-1 text-[10px] opacity-70">cid={event.correlationId}</div>
                ) : null}
              </div>
            ))}
            <div style={{ height: messageVirtual.offsetBottom }} />
            {!activeConversation ? <div className="p-2 text-muted-foreground">No live conversation selected.</div> : null}
          </div>
        </div>
      </div>
    </div>
  );
}
