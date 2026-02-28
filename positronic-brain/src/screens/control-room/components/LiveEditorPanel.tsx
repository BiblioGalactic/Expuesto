import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

export interface LiveEditorSelection {
  workspaceId: string;
  workspaceName: string;
  relativePath: string;
  fileName: string;
}

export function LiveEditorPanel({
  selection,
  content,
  loading,
  saving,
  dirty,
  error,
  onContentChange,
  onReload,
  onSave,
}: {
  selection: LiveEditorSelection | null;
  content: string;
  loading: boolean;
  saving: boolean;
  dirty: boolean;
  error: string | null;
  onContentChange: (value: string) => void;
  onReload: () => void;
  onSave: () => void;
}) {
  return (
    <div className="controlroom-card flex h-full min-h-0 flex-col rounded-md border border-border/50 bg-card/35">
      <div className="cr-panel-header">
        <div className="cr-toolbar min-w-0">
          <span className="cr-panel-title">Live Editor</span>
          {selection ? (
            <>
              <Badge variant="secondary" className="cr-badge">
                {selection.workspaceName}
              </Badge>
              <Badge variant="outline" className="cr-badge max-w-[220px] truncate">
                {selection.relativePath}
              </Badge>
            </>
          ) : (
            <span className="cr-meta">sin archivo</span>
          )}
        </div>
        <div className="cr-toolbar">
          <Button size="sm" variant="outline" className="cr-compact-btn" onClick={onReload} disabled={!selection || loading}>
            Reload
          </Button>
          <Button
            size="sm"
            variant={dirty ? "default" : "outline"}
            className={dirty ? "cr-compact-btn controlroom-btn-start" : "cr-compact-btn"}
            onClick={onSave}
            disabled={!selection || loading || saving || !dirty}
          >
            {saving ? "Saving..." : "Save"}
          </Button>
        </div>
      </div>

      <div className="min-h-0 flex-1 border-t border-border/45 p-2">
        {!selection ? (
          <div className="flex h-full items-center justify-center rounded-md border border-dashed border-border/45 text-sm text-muted-foreground">
            Selecciona un archivo desde Workspaces para editarlo.
          </div>
        ) : (
          <Textarea
            value={content}
            onChange={(event) => onContentChange(event.target.value)}
            className="h-full min-h-0 resize-none bg-background/55 font-mono text-[12px]"
            spellCheck={false}
            disabled={loading}
          />
        )}
      </div>

      <div className="flex items-center justify-between border-t border-border/45 px-2 py-1 text-[11px]">
        <span className="text-muted-foreground">
          {loading ? "loading..." : dirty ? "unsaved changes" : "synced"}
        </span>
        {error ? <span className="text-rose-300">{error}</span> : null}
      </div>
    </div>
  );
}
