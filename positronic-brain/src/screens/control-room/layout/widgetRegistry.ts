export interface ControlRoomWidgetMeta {
  id: string;
  title: string;
  critical?: boolean;
}

export const CONTROLROOM_WIDGETS: ControlRoomWidgetMeta[] = [
  { id: "service_wall", title: "Service Wall", critical: true },
  { id: "runner", title: "Runner", critical: true },
  { id: "terminal", title: "Terminal", critical: false },
  { id: "mission", title: "Mission Board", critical: false },
  { id: "agents", title: "Agents", critical: false },
  { id: "feed", title: "Live Feed", critical: false },
  { id: "channels", title: "Channels", critical: false },
  { id: "video", title: "Video Wall", critical: false },
];

export const CONTROLROOM_WIDGET_INDEX = new Map(
  CONTROLROOM_WIDGETS.map((entry) => [entry.id, entry]),
);
