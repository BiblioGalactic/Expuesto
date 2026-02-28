import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { ServiceConfig, WorkspaceConfig } from "../types";

export function ActionsPanel({
  services,
  workspaces,
  onStartAll,
  onStopAll,
  onRestartAll,
  onClearAllLogs,
  onExportServiceLogs,
  onOpenWorkspace,
}: {
  services: ServiceConfig[];
  workspaces: WorkspaceConfig[];
  onStartAll: () => void;
  onStopAll: () => void;
  onRestartAll: () => void;
  onClearAllLogs: () => void;
  onExportServiceLogs: (serviceId: string) => void;
  onOpenWorkspace: (workspaceId: string) => void;
}) {
  return (
    <ScrollArea className="h-full min-h-0">
      <div className="space-y-4 p-2">
        <div className="space-y-2">
          <div className="text-sm font-semibold">Service Actions</div>
          <div className="grid grid-cols-2 gap-2">
            <Button size="sm" variant="outline" className="controlroom-btn-start" onClick={onStartAll}>
              Start all
            </Button>
            <Button size="sm" variant="outline" className="controlroom-btn-stop" onClick={onStopAll}>
              Stop all
            </Button>
            <Button size="sm" variant="outline" className="controlroom-btn-neutral" onClick={onRestartAll}>
              Restart all
            </Button>
            <Button size="sm" variant="outline" className="controlroom-btn-neutral" onClick={onClearAllLogs}>
              Clear all logs
            </Button>
          </div>
        </div>

        <div className="space-y-2">
          <div className="text-sm font-semibold">Export Logs</div>
          {services.map((service) => (
            <Button key={service.id} size="sm" className="w-full justify-start" variant="secondary" onClick={() => onExportServiceLogs(service.id)}>
              Export {service.name}
            </Button>
          ))}
        </div>

        <div className="space-y-2">
          <div className="text-sm font-semibold">Open Workspace</div>
          {workspaces.map((workspace) => (
            <Button
              key={workspace.id}
              size="sm"
              className="w-full justify-start"
              variant="secondary"
              onClick={() => onOpenWorkspace(workspace.id)}
            >
              {workspace.name}
            </Button>
          ))}
        </div>
      </div>
    </ScrollArea>
  );
}
