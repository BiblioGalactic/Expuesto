export interface ControlRoomWidgetLayout {
  id: string;
  x: number;
  y: number;
  w: number;
  h: number;
  collapsed?: boolean;
  order?: number;
  visible?: boolean;
}

export interface ControlRoomLayoutState {
  version: 2;
  widgets: ControlRoomWidgetLayout[];
}

export const CONTROLROOM_LAYOUT_STORAGE_KEY = "controlroom.layout.v2";

export function parseLayoutState(raw: string | null): ControlRoomLayoutState | null {
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as ControlRoomLayoutState;
    if (!parsed || parsed.version !== 2 || !Array.isArray(parsed.widgets)) {
      return null;
    }
    return {
      version: 2,
      widgets: parsed.widgets
        .map((item) => ({
          id: String(item?.id || "").trim(),
          x: Number(item?.x || 0),
          y: Number(item?.y || 0),
          w: Number(item?.w || 1),
          h: Number(item?.h || 1),
          collapsed: Boolean(item?.collapsed),
          order: Number(item?.order || 0),
          visible: item?.visible !== false,
        }))
        .filter((item) => Boolean(item.id)),
    };
  } catch {
    return null;
  }
}

export function serializeLayoutState(state: ControlRoomLayoutState): string {
  return JSON.stringify(state);
}
