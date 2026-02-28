import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ChevronRight, Folder, FolderOpen, FileText, Loader2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { WorkspaceConfig, WorkspaceEntry } from "../types";

interface WorkspaceTreePanelProps {
  workspaces: WorkspaceConfig[];
  activeWorkspaceId: string | null;
  onSelectWorkspace: (workspaceId: string) => void;
  fetchWorkspaceEntries: (workspaceId: string, relativePath?: string) => Promise<WorkspaceEntry[]>;
  onSelectFile?: (workspaceId: string, relativePath: string, fileName: string) => void;
  selectedFilePath?: string | null;
}

export function WorkspaceTreePanel({
  workspaces,
  activeWorkspaceId,
  onSelectWorkspace,
  fetchWorkspaceEntries,
  onSelectFile,
  selectedFilePath,
}: WorkspaceTreePanelProps) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [cache, setCache] = useState<Record<string, WorkspaceEntry[]>>({});
  const [loading, setLoading] = useState<Record<string, boolean>>({});

  const activeWorkspace = useMemo(
    () => workspaces.find((workspace) => workspace.id === activeWorkspaceId) ?? null,
    [workspaces, activeWorkspaceId]
  );

  useEffect(() => {
    if (!activeWorkspace) return;
    const rootKey = `${activeWorkspace.id}::`;
    if (cache[rootKey]) return;
    void loadEntries(activeWorkspace.id, "");
  }, [activeWorkspace, cache]);

  async function loadEntries(workspaceId: string, relativePath = "") {
    const key = `${workspaceId}::${relativePath}`;
    setLoading((prev) => ({ ...prev, [key]: true }));
    try {
      const entries = await fetchWorkspaceEntries(workspaceId, relativePath);
      setCache((prev) => ({ ...prev, [key]: entries }));
    } finally {
      setLoading((prev) => ({ ...prev, [key]: false }));
    }
  }

  function toggleDir(workspaceId: string, relativePath: string) {
    const key = `${workspaceId}::${relativePath}`;
    setExpanded((prev) => ({ ...prev, [key]: !prev[key] }));
    if (!cache[key]) {
      void loadEntries(workspaceId, relativePath);
    }
  }

  function renderEntries(workspaceId: string, basePath: string, depth: number) {
    const key = `${workspaceId}::${basePath}`;
    const entries = cache[key] ?? [];

    return entries.map((entry) => {
      const relative = entry.path;
      const nodeKey = `${workspaceId}::${relative}`;
      const isOpen = Boolean(expanded[nodeKey]);
      const isDir = entry.isDirectory;
      const isSelectedFile = !isDir && selectedFilePath === relative;
      return (
        <div key={nodeKey}>
          <button
            className={`flex w-full items-center gap-1 rounded px-1 py-0.5 text-left text-xs hover:bg-accent ${
              isSelectedFile ? "bg-accent text-accent-foreground" : ""
            }`}
            style={{ paddingLeft: `${depth * 14 + 4}px` }}
            onClick={() => {
              if (isDir) {
                toggleDir(workspaceId, relative);
                return;
              }
              onSelectFile?.(workspaceId, relative, entry.name);
            }}
          >
            {isDir ? (
              <ChevronRight className={`h-3 w-3 transition-transform ${isOpen ? "rotate-90" : ""}`} />
            ) : (
              <span className="w-3" />
            )}
            {isDir ? (isOpen ? <FolderOpen className="h-3 w-3" /> : <Folder className="h-3 w-3" />) : <FileText className="h-3 w-3" />}
            <span className="truncate">{entry.name}</span>
          </button>
          {isDir && isOpen ? (
            <>
              {loading[nodeKey] ? (
                <div className="flex items-center gap-1 px-2 py-1 text-xs text-muted-foreground" style={{ paddingLeft: `${depth * 14 + 20}px` }}>
                  <Loader2 className="h-3 w-3 animate-spin" /> loading...
                </div>
              ) : (
                renderEntries(workspaceId, relative, depth + 1)
              )}
            </>
          ) : null}
        </div>
      );
    });
  }

  return (
    <div className="h-full min-h-0 flex flex-col">
      <div className="border-b p-2 space-y-2">
        <div className="text-sm font-semibold">Workspaces</div>
        <div className="grid grid-cols-1 gap-1">
          {workspaces.map((workspace) => (
            <Button
              key={workspace.id}
              size="sm"
              variant={workspace.id === activeWorkspaceId ? "default" : "outline"}
              className="justify-start"
              onClick={() => onSelectWorkspace(workspace.id)}
            >
              {workspace.name}
            </Button>
          ))}
        </div>
      </div>
      <ScrollArea className="min-h-0 flex-1">
        <div className="p-1">
          {activeWorkspace ? (
            <>
              {loading[`${activeWorkspace.id}::`] ? (
                <div className="px-2 py-2 text-xs text-muted-foreground">Loading...</div>
              ) : (
                renderEntries(activeWorkspace.id, "", 0)
              )}
            </>
          ) : (
            <div className="px-2 py-2 text-xs text-muted-foreground">No workspace selected</div>
          )}
        </div>
      </ScrollArea>
    </div>
  );
}
