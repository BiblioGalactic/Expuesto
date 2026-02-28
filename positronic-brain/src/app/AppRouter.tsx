import { invoke } from "@tauri-apps/api/core";
import { useEffect, useMemo, useState } from "react";
import ClassicShellScreen from "@/screens/classic/ClassicShellScreen";
import { ControlRoomScreen } from "@/screens/control-room/ControlRoomScreen";
import { parseControlRoomConfig } from "@/screens/control-room/schema";
import type { ControlRoomConfig } from "@/screens/control-room/types";
import { Button } from "@/components/ui/button";
import { AlertTriangle } from "lucide-react";

const LAST_VIEW_KEY = "controlroom:last-view";

type ViewMode = "classic" | "control-room";

function getRememberedView(): ViewMode | null {
  const value = localStorage.getItem(LAST_VIEW_KEY);
  if (value === "classic" || value === "control-room") return value;
  return null;
}

function resolveInitialView(config: ControlRoomConfig): ViewMode {
  const preferred = config.ui.defaultView;
  if (config.ui.rememberLastView) {
    const remembered = getRememberedView();
    if (remembered) return remembered;
  }
  if (!config.featureFlags.controlRoomEnabled) return "classic";
  return preferred === "control-room" ? "control-room" : "classic";
}

export function AppRouter() {
  const [config, setConfig] = useState<ControlRoomConfig | null>(null);
  const [view, setView] = useState<ViewMode>("classic");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      setLoading(true);
      setError(null);
      try {
        const raw = await invoke("controlroom_load_config");
        const parsed = parseControlRoomConfig(raw);
        if (cancelled) return;
        setConfig(parsed);
        setView(resolveInitialView(parsed));
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : String(err));
        setConfig(null);
        setView("classic");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void bootstrap();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!config?.ui.rememberLastView) return;
    localStorage.setItem(LAST_VIEW_KEY, view);
  }, [view, config?.ui.rememberLastView]);

  const canUseControlRoom = useMemo(() => {
    return Boolean(config?.featureFlags.controlRoomEnabled);
  }, [config]);

  if (loading) {
    return (
      <div className="h-screen w-screen flex items-center justify-center bg-background text-foreground">
        <div className="text-sm text-muted-foreground">Loading ControlRoom config...</div>
      </div>
    );
  }

  if (canUseControlRoom && config) {
    if (view === "control-room") {
      return <ControlRoomScreen config={config} onSwitchClassic={() => setView("classic")} />;
    }
    return (
      <div className="h-screen w-screen relative">
        <div className="absolute right-3 top-3 z-50">
          <Button size="sm" variant="outline" onClick={() => setView("control-room")}>
            Open ControlRoom
          </Button>
        </div>
        <ClassicShellScreen />
      </div>
    );
  }

  return (
    <div className="h-screen w-screen relative">
      {error ? (
        <div className="absolute right-3 top-3 z-50 max-w-md rounded-md border bg-card p-3 text-xs text-muted-foreground shadow">
          <div className="mb-1 flex items-center gap-2 text-foreground">
            <AlertTriangle className="h-4 w-4 text-amber-500" />
            <span>ControlRoom disabled</span>
          </div>
          <div>{error}</div>
        </div>
      ) : null}
      <ClassicShellScreen />
    </div>
  );
}
