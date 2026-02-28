import { Button } from "@/components/ui/button";
import { useEffect, useMemo, useRef, useState } from "react";
import { useVirtualWindow } from "../perf/virtualization";
import type { GitCommit } from "../types";

const ROW_HEIGHT = 84;

export function CommitsPanel({
  workspaceName,
  commits,
  loading,
  error,
  onRefresh,
}: {
  workspaceName?: string;
  commits: GitCommit[];
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
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
    total: commits.length,
    rowHeight: ROW_HEIGHT,
    viewportHeight,
    scrollTop,
    overscan: 10,
  });

  const visibleCommits = useMemo(
    () => commits.slice(virtual.start, virtual.end),
    [commits, virtual.start, virtual.end],
  );

  return (
    <div className="h-full min-h-0 flex flex-col">
      <div className="flex items-center justify-between p-2">
        <div>
          <div className="text-sm font-semibold">Commits</div>
          <div className="text-xs text-muted-foreground">{workspaceName ?? "No workspace selected"}</div>
        </div>
        <Button size="sm" variant="outline" onClick={onRefresh} disabled={loading}>
          {loading ? "Loading..." : "Refresh"}
        </Button>
      </div>
      {error ? <div className="px-2 text-xs text-rose-400">{error}</div> : null}
      <div
        ref={viewportRef}
        className="min-h-0 flex-1 overflow-auto"
        onScroll={(event) => setScrollTop((event.currentTarget as HTMLDivElement).scrollTop)}
      >
        <div style={{ height: virtual.offsetTop }} />
        {visibleCommits.map((commit) => (
          <div key={commit.hash} className="mx-2 mb-2 rounded-md border bg-background p-2" style={{ minHeight: ROW_HEIGHT - 8 }}>
            <div className="text-xs font-mono text-primary">{commit.shortHash}</div>
            <div className="line-clamp-2 text-sm">{commit.message}</div>
            <div className="text-xs text-muted-foreground">
              {commit.author} · {commit.date}
            </div>
          </div>
        ))}
        <div style={{ height: virtual.offsetBottom }} />
        {!loading && commits.length === 0 ? (
          <div className="px-2 text-xs text-muted-foreground">No commits available.</div>
        ) : null}
      </div>
    </div>
  );
}
