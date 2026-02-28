import { useMemo } from "react";

export interface VirtualWindowOptions {
  total: number;
  rowHeight: number;
  viewportHeight: number;
  scrollTop: number;
  overscan?: number;
}

export interface VirtualWindowState {
  start: number;
  end: number;
  offsetTop: number;
  offsetBottom: number;
}

export function computeVirtualWindow({
  total,
  rowHeight,
  viewportHeight,
  scrollTop,
  overscan = 12,
}: VirtualWindowOptions): VirtualWindowState {
  if (total <= 0 || rowHeight <= 0 || viewportHeight <= 0) {
    return {
      start: 0,
      end: total,
      offsetTop: 0,
      offsetBottom: 0,
    };
  }

  const maxVisible = Math.ceil(viewportHeight / rowHeight);
  const start = Math.max(0, Math.floor(scrollTop / rowHeight) - overscan);
  const end = Math.min(total, start + maxVisible + overscan * 2);
  const offsetTop = start * rowHeight;
  const offsetBottom = Math.max(0, (total - end) * rowHeight);

  return { start, end, offsetTop, offsetBottom };
}

export function useVirtualWindow(options: VirtualWindowOptions): VirtualWindowState {
  return useMemo(() => computeVirtualWindow(options), [
    options.total,
    options.rowHeight,
    options.viewportHeight,
    options.scrollTop,
    options.overscan,
  ]);
}
