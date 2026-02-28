import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { GitCommit, ServiceConfig, ServiceLogEvent, WorkspaceConfig, WorkspaceEntry } from "../types";
import { ActionsPanel } from "./ActionsPanel";
import { CommitsPanel } from "./CommitsPanel";
import { RecordsPanel } from "./RecordsPanel";
import { WorkspaceTreePanel } from "./WorkspaceTreePanel";

export function LeftSidebar({
  services,
  logs,
  workspaces,
  activeWorkspaceId,
  commits,
  commitsLoading,
  commitsError,
  onSelectWorkspace,
  onFetchWorkspaceEntries,
  onSelectWorkspaceFile,
  selectedWorkspaceFilePath,
  onSelectService,
  onRefreshCommits,
  onStartAll,
  onStopAll,
  onRestartAll,
  onClearAllLogs,
  onExportServiceLogs,
  onOpenWorkspace,
}: {
  services: ServiceConfig[];
  logs: Record<string, ServiceLogEvent[]>;
  workspaces: WorkspaceConfig[];
  activeWorkspaceId: string | null;
  commits: GitCommit[];
  commitsLoading: boolean;
  commitsError: string | null;
  onSelectWorkspace: (workspaceId: string) => void;
  onFetchWorkspaceEntries: (workspaceId: string, relativePath?: string) => Promise<WorkspaceEntry[]>;
  onSelectWorkspaceFile?: (workspaceId: string, relativePath: string, fileName: string) => void;
  selectedWorkspaceFilePath?: string | null;
  onSelectService: (serviceId: string) => void;
  onRefreshCommits: () => void;
  onStartAll: () => void;
  onStopAll: () => void;
  onRestartAll: () => void;
  onClearAllLogs: () => void;
  onExportServiceLogs: (serviceId: string) => void;
  onOpenWorkspace: (workspaceId: string) => void;
}) {
  const workspaceName = workspaces.find((workspace) => workspace.id === activeWorkspaceId)?.name;

  return (
    <div className="controlroom-card flex h-full min-h-0 flex-col rounded-md border border-border/50 bg-card/35">
      <Tabs defaultValue="workspaces" className="h-full min-h-0 flex flex-col">
        <div className="border-b border-border/45 px-2 py-2">
          <TabsList className="grid w-full grid-cols-4">
            <TabsTrigger value="workspaces">Workspaces</TabsTrigger>
            <TabsTrigger value="records">Registros</TabsTrigger>
            <TabsTrigger value="commits">Commits</TabsTrigger>
            <TabsTrigger value="actions">Acciones</TabsTrigger>
          </TabsList>
        </div>

        <TabsContent value="workspaces" className="mt-0 min-h-0 flex-1 overflow-hidden p-2">
          <WorkspaceTreePanel
            workspaces={workspaces}
            activeWorkspaceId={activeWorkspaceId}
            onSelectWorkspace={onSelectWorkspace}
            fetchWorkspaceEntries={onFetchWorkspaceEntries}
            onSelectFile={onSelectWorkspaceFile}
            selectedFilePath={selectedWorkspaceFilePath}
          />
        </TabsContent>

        <TabsContent value="records" className="mt-0 min-h-0 flex-1 overflow-hidden p-2">
          <RecordsPanel services={services} logs={logs} onSelectService={onSelectService} />
        </TabsContent>

        <TabsContent value="commits" className="mt-0 min-h-0 flex-1 overflow-hidden p-2">
          <CommitsPanel
            workspaceName={workspaceName}
            commits={commits}
            loading={commitsLoading}
            error={commitsError}
            onRefresh={onRefreshCommits}
          />
        </TabsContent>

        <TabsContent value="actions" className="mt-0 min-h-0 flex-1 overflow-hidden p-2">
          <ActionsPanel
            services={services}
            workspaces={workspaces}
            onStartAll={onStartAll}
            onStopAll={onStopAll}
            onRestartAll={onRestartAll}
            onClearAllLogs={onClearAllLogs}
            onExportServiceLogs={onExportServiceLogs}
            onOpenWorkspace={onOpenWorkspace}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}
