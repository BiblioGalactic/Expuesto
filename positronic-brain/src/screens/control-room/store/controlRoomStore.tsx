import { createContext, useContext, useMemo, useReducer } from "react";
import type {
  ControlRoomConfig,
  GitCommit,
  RunnerCommandInput,
  RunnerExitEvent,
  RunnerOutputEvent,
  ServiceLogEvent,
  ServiceStatus,
  WorkspaceEntry,
} from "../types";

const MAX_SERVICE_LOGS = 2500;
const MAX_RUNNER_LINES = 4000;
const MAX_HISTORY = 60;

export interface ControlRoomStoreState {
  config: ControlRoomConfig;
  serviceStatuses: Record<string, ServiceStatus>;
  serviceLogs: Record<string, ServiceLogEvent[]>;
  runnerOutputs: Record<string, RunnerOutputEvent[]>;
  runnerExits: Record<string, RunnerExitEvent>;
  runnerHistory: RunnerCommandInput[];
  activeWorkspaceId: string | null;
  activeServiceId: string | null;
  workspaceCache: Record<string, WorkspaceEntry[]>;
  commitsByWorkspace: Record<string, GitCommit[]>;
}

type ControlRoomStoreAction =
  | { type: "UPSERT_SERVICE_STATUS"; payload: ServiceStatus }
  | { type: "SET_SERVICE_STATUSES"; payload: ServiceStatus[] }
  | { type: "APPEND_SERVICE_LOG"; payload: ServiceLogEvent }
  | { type: "SET_SERVICE_LOGS"; payload: { serviceId: string; logs: ServiceLogEvent[] } }
  | { type: "CLEAR_SERVICE_LOG"; payload: { serviceId: string } }
  | { type: "APPEND_RUNNER_OUTPUT"; payload: RunnerOutputEvent }
  | { type: "SET_RUNNER_EXIT"; payload: RunnerExitEvent }
  | { type: "PUSH_HISTORY"; payload: RunnerCommandInput }
  | { type: "SET_ACTIVE_WORKSPACE"; payload: string | null }
  | { type: "SET_ACTIVE_SERVICE"; payload: string | null }
  | { type: "SET_WORKSPACE_CACHE"; payload: { key: string; entries: WorkspaceEntry[] } }
  | { type: "SET_COMMITS"; payload: { workspaceId: string; commits: GitCommit[] } };

function buildInitialState(config: ControlRoomConfig): ControlRoomStoreState {
  return {
    config,
    serviceStatuses: {},
    serviceLogs: {},
    runnerOutputs: {},
    runnerExits: {},
    runnerHistory: [],
    activeWorkspaceId: config.workspaces[0]?.id ?? null,
    activeServiceId: config.services[0]?.id ?? null,
    workspaceCache: {},
    commitsByWorkspace: {},
  };
}

function reducer(state: ControlRoomStoreState, action: ControlRoomStoreAction): ControlRoomStoreState {
  switch (action.type) {
    case "UPSERT_SERVICE_STATUS": {
      return {
        ...state,
        serviceStatuses: {
          ...state.serviceStatuses,
          [action.payload.serviceId]: action.payload,
        },
      };
    }
    case "SET_SERVICE_STATUSES": {
      const next = { ...state.serviceStatuses };
      action.payload.forEach((status) => {
        next[status.serviceId] = status;
      });
      return {
        ...state,
        serviceStatuses: next,
      };
    }
    case "APPEND_SERVICE_LOG": {
      const current = state.serviceLogs[action.payload.serviceId] ?? [];
      const nextLogs = [...current, action.payload].slice(-MAX_SERVICE_LOGS);
      return {
        ...state,
        serviceLogs: {
          ...state.serviceLogs,
          [action.payload.serviceId]: nextLogs,
        },
      };
    }
    case "SET_SERVICE_LOGS": {
      return {
        ...state,
        serviceLogs: {
          ...state.serviceLogs,
          [action.payload.serviceId]: action.payload.logs.slice(-MAX_SERVICE_LOGS),
        },
      };
    }
    case "CLEAR_SERVICE_LOG": {
      return {
        ...state,
        serviceLogs: {
          ...state.serviceLogs,
          [action.payload.serviceId]: [],
        },
      };
    }
    case "APPEND_RUNNER_OUTPUT": {
      const current = state.runnerOutputs[action.payload.runId] ?? [];
      return {
        ...state,
        runnerOutputs: {
          ...state.runnerOutputs,
          [action.payload.runId]: [...current, action.payload].slice(-MAX_RUNNER_LINES),
        },
      };
    }
    case "SET_RUNNER_EXIT": {
      return {
        ...state,
        runnerExits: {
          ...state.runnerExits,
          [action.payload.runId]: action.payload,
        },
      };
    }
    case "PUSH_HISTORY": {
      return {
        ...state,
        runnerHistory: [action.payload, ...state.runnerHistory].slice(0, MAX_HISTORY),
      };
    }
    case "SET_ACTIVE_WORKSPACE": {
      return {
        ...state,
        activeWorkspaceId: action.payload,
      };
    }
    case "SET_ACTIVE_SERVICE": {
      return {
        ...state,
        activeServiceId: action.payload,
      };
    }
    case "SET_WORKSPACE_CACHE": {
      return {
        ...state,
        workspaceCache: {
          ...state.workspaceCache,
          [action.payload.key]: action.payload.entries,
        },
      };
    }
    case "SET_COMMITS": {
      return {
        ...state,
        commitsByWorkspace: {
          ...state.commitsByWorkspace,
          [action.payload.workspaceId]: action.payload.commits,
        },
      };
    }
    default:
      return state;
  }
}

interface ControlRoomStoreContextValue {
  state: ControlRoomStoreState;
  dispatch: React.Dispatch<ControlRoomStoreAction>;
}

const ControlRoomStoreContext = createContext<ControlRoomStoreContextValue | undefined>(undefined);

export function ControlRoomStoreProvider({
  config,
  children,
}: {
  config: ControlRoomConfig;
  children: React.ReactNode;
}) {
  const [state, dispatch] = useReducer(reducer, buildInitialState(config));
  const value = useMemo(() => ({ state, dispatch }), [state]);
  return <ControlRoomStoreContext.Provider value={value}>{children}</ControlRoomStoreContext.Provider>;
}

export function useControlRoomStore() {
  const context = useContext(ControlRoomStoreContext);
  if (!context) {
    throw new Error("useControlRoomStore must be used within ControlRoomStoreProvider");
  }
  return context;
}
