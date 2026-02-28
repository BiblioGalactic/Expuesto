import { invoke } from "@tauri-apps/api/core";
import { useEffect, useMemo, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PtyTerminal } from "@/components/pty-terminal";
import { toast } from "sonner";
import type { ServiceConfig } from "../types";

type AuthMode = "publickey" | "password";
type ConnectionState = "disconnected" | "connecting" | "connected";

interface ConnectResponse {
  success: boolean;
  output?: string | null;
  error?: string | null;
}

interface ConnectRequest {
  connection_id: string;
  host: string;
  port: number;
  username: string;
  auth_method: AuthMode;
  password?: string | null;
  key_path?: string | null;
  passphrase?: string | null;
}

interface QuickCommandPreset {
  id: string;
  label: string;
  command: string;
  description: string;
}

function stateBadgeVariant(state: ConnectionState): "default" | "secondary" | "outline" {
  if (state === "connected") return "default";
  if (state === "connecting") return "secondary";
  return "outline";
}

function defaultKeyCandidates(host: string, username: string): string[] {
  const trimmedHost = host.trim().toLowerCase();
  const trimmedUser = username.trim();
  if (!trimmedUser) return [];
  const isLocal = trimmedHost === "127.0.0.1" || trimmedHost === "localhost";
  if (!isLocal) return [];
  return [`/Users/${trimmedUser}/.ssh/id_ed25519`, `/Users/${trimmedUser}/.ssh/id_rsa`];
}

const BASE_QUICK_COMMAND_PRESETS: QuickCommandPreset[] = [
  {
    id: "whoami",
    label: "Identidad",
    command: "whoami && hostname && date",
    description: "Muestra usuario, host y hora actual.",
  },
  {
    id: "bridge-health",
    label: "Bridge Health",
    command:
      "cd \"$HOME/externo/wa-llama-bridge\" && pgrep -fl \"node bridge.js\" || true && ls -la data | head -n 10",
    description: "Comprueba proceso bridge y directorio de estado.",
  },
  {
    id: "models-status",
    label: "Modelos Aux",
    command: "cd \"$HOME/externo/wa-llama-bridge\" && ./scripts/llm_aux.sh status",
    description: "Estado rápido de DeepSeek y Dolphin (llm_aux).",
  },
  {
    id: "controlroom-tail",
    label: "Front-end Logs",
    command: "cd \"$HOME/modelo/front-end\" && ls -la src-tauri | head -n 20",
    description: "Inspección rápida del proyecto ControlRoom.",
  },
  {
    id: "system-memory",
    label: "Memoria/Carga",
    command: "vm_stat | head -n 20 && sysctl -n vm.loadavg",
    description: "Diagnóstico de memoria y carga del sistema.",
  },
];

function shellQuote(value: string): string {
  if (!value) return "''";
  return `'${value.replace(/'/g, `'\\''`)}'`;
}

function commandFromSpec(spec?: ServiceConfig["start"]): string | null {
  if (!spec?.program) return null;
  const run = [shellQuote(spec.program), ...(spec.args ?? []).map((arg) => shellQuote(arg))].join(" ");
  if (spec.cwd) return `cd ${shellQuote(spec.cwd)} && ${run}`;
  return run;
}

function extractServicePort(service: ServiceConfig): number | null {
  const args = service.start.args ?? [];
  for (let index = 0; index < args.length; index += 1) {
    const value = args[index];
    if ((value === "--port" || value === "-p") && args[index + 1]) {
      const port = Number.parseInt(args[index + 1], 10);
      if (Number.isFinite(port) && port > 0 && port <= 65535) return port;
    }
    if (value.startsWith("--port=")) {
      const port = Number.parseInt(value.split("=")[1] ?? "", 10);
      if (Number.isFinite(port) && port > 0 && port <= 65535) return port;
    }
  }
  return null;
}

function buildContextPresets(activeService: ServiceConfig | null): QuickCommandPreset[] {
  if (!activeService) return [];

  const presets: QuickCommandPreset[] = [];
  const startCommand = commandFromSpec(activeService.start);
  const stopCommand = commandFromSpec(activeService.stop);
  const restartCommand = commandFromSpec(activeService.restart);
  const programName = activeService.start.program.split("/").pop() || activeService.start.program;
  const port = extractServicePort(activeService);

  presets.push({
    id: `ctx-${activeService.id}-inspect`,
    label: `Inspect ${activeService.name}`,
    command: `pgrep -fl ${shellQuote(programName)} || true`,
    description: `Estado rápido del proceso para ${activeService.name}.`,
  });

  if (startCommand) {
    presets.push({
      id: `ctx-${activeService.id}-start`,
      label: `Start ${activeService.name}`,
      command: startCommand,
      description: `Arranque del servicio activo (${activeService.name}).`,
    });
  }

  if (stopCommand) {
    presets.push({
      id: `ctx-${activeService.id}-stop`,
      label: `Stop ${activeService.name}`,
      command: stopCommand,
      description: `Parada del servicio activo (${activeService.name}).`,
    });
  }

  if (restartCommand) {
    presets.push({
      id: `ctx-${activeService.id}-restart`,
      label: `Restart ${activeService.name}`,
      command: restartCommand,
      description: `Reinicio del servicio activo (${activeService.name}).`,
    });
  }

  if (port) {
    presets.push({
      id: `ctx-${activeService.id}-health`,
      label: `Health ${activeService.name}`,
      command: `curl -sS --max-time 3 http://127.0.0.1:${port}/v1/models | head -n 40 || curl -sS --max-time 3 http://127.0.0.1:${port}/health || true`,
      description: `Sonda HTTP para ${activeService.name} en puerto ${port}.`,
    });
  }

  return presets;
}

export function NativeTerminalPanel({ activeService = null }: { activeService?: ServiceConfig | null }) {
  const sessionIdRef = useRef(`controlroom-local-${crypto.randomUUID()}`);
  const autoConnectAttemptRef = useRef(false);
  const [state, setState] = useState<ConnectionState>("disconnected");

  const [host, setHost] = useState("127.0.0.1");
  const [port, setPort] = useState("22");
  const [username, setUsername] = useState("gustavosilvadacosta");
  const [authMode, setAuthMode] = useState<AuthMode>("publickey");
  const [password, setPassword] = useState("");
  const [keyPath, setKeyPath] = useState("");
  const [passphrase, setPassphrase] = useState("");
  const [autoConnectEnabled, setAutoConnectEnabled] = useState(true);
  const [showQuickCommands, setShowQuickCommands] = useState(true);
  const [selectedPresetId, setSelectedPresetId] = useState("");
  const [quickCommand, setQuickCommand] = useState("");
  const [quickOutput, setQuickOutput] = useState("");
  const [quickRunning, setQuickRunning] = useState(false);

  const isConnected = state === "connected";
  const isConnecting = state === "connecting";

  const contextPresets = useMemo(() => buildContextPresets(activeService), [activeService]);
  const quickPresets = useMemo(
    () => [...contextPresets, ...BASE_QUICK_COMMAND_PRESETS],
    [contextPresets],
  );

  useEffect(() => {
    if (quickPresets.length === 0) {
      setSelectedPresetId("");
      return;
    }

    const stillValid = quickPresets.some((preset) => preset.id === selectedPresetId);
    if (!stillValid) {
      setSelectedPresetId(quickPresets[0].id);
      setQuickCommand(quickPresets[0].command);
    }
  }, [quickPresets, selectedPresetId]);

  const parsedPort = useMemo(() => {
    const n = Number.parseInt(port, 10);
    if (!Number.isFinite(n) || n <= 0 || n > 65535) return 22;
    return n;
  }, [port]);

  const selectedPreset = useMemo(
    () => quickPresets.find((preset) => preset.id === selectedPresetId) ?? null,
    [quickPresets, selectedPresetId],
  );

  async function tryConnectWith(request: ConnectRequest): Promise<ConnectResponse> {
    return invoke<ConnectResponse>("ssh_connect", { request });
  }

  async function connect() {
    if (isConnected || isConnecting) return;
    if (!host.trim() || !username.trim()) {
      toast.error("Host y username son obligatorios");
      return;
    }

    setState("connecting");
    const base: ConnectRequest = {
      connection_id: sessionIdRef.current,
      host: host.trim(),
      port: parsedPort,
      username: username.trim(),
      auth_method: authMode,
      password: undefined,
      key_path: undefined,
      passphrase: undefined,
    };

    try {
      let result: ConnectResponse | null = null;

      if (authMode === "password") {
        result = await tryConnectWith({
          ...base,
          password: password || "",
        });
      } else {
        const candidates = keyPath.trim()
          ? [keyPath.trim()]
          : defaultKeyCandidates(base.host, base.username);

        if (candidates.length === 0) {
          toast.error("Indica key path o usa password");
          setState("disconnected");
          return;
        }

        for (const candidate of candidates) {
          result = await tryConnectWith({
            ...base,
            key_path: candidate,
            passphrase: passphrase.trim() || null,
          });
          if (result.success) {
            if (!keyPath.trim()) {
              setKeyPath(candidate);
            }
            break;
          }
        }
      }

      if (!result?.success) {
        setState("disconnected");
        toast.error(result?.error || "No se pudo conectar la terminal");
        return;
      }

      setState("connected");
      toast.success("Terminal conectada");
    } catch (error) {
      setState("disconnected");
      toast.error(`Error conectando terminal: ${error instanceof Error ? error.message : String(error)}`);
    }
  }

  async function disconnect() {
    try {
      await invoke<ConnectResponse>("ssh_disconnect", { connection_id: sessionIdRef.current });
    } catch {
      // Ignore disconnect races.
    } finally {
      setState("disconnected");
    }
  }

  async function runQuickCommand() {
    const command = quickCommand.trim();
    if (!command) {
      toast.error("No hay comando rápido para ejecutar");
      return;
    }
    if (!isConnected) {
      toast.error("Conecta la terminal antes de ejecutar comandos rápidos");
      return;
    }

    setQuickRunning(true);
    const startedAt = new Date().toLocaleTimeString();
    try {
      const result = await invoke<ConnectResponse>("ssh_execute_command", {
        connection_id: sessionIdRef.current,
        command,
      });
      if (!result.success) {
        const errorText = result.error || "Comando falló";
        setQuickOutput(`[${startedAt}] $ ${command}\nERROR: ${errorText}`);
        toast.error(errorText);
        return;
      }
      const output = (result.output || "").trim() || "(sin salida)";
      setQuickOutput(`[${startedAt}] $ ${command}\n${output}`);
      toast.success("Comando rápido ejecutado");
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setQuickOutput(`[${startedAt}] $ ${command}\nERROR: ${message}`);
      toast.error(`Quick command error: ${message}`);
    } finally {
      setQuickRunning(false);
    }
  }

  useEffect(() => {
    if (!autoConnectEnabled) return;
    if (autoConnectAttemptRef.current) return;
    if (state !== "disconnected") return;

    autoConnectAttemptRef.current = true;
    const timer = window.setTimeout(() => {
      void connect();
    }, 420);

    return () => {
      window.clearTimeout(timer);
    };
  }, [autoConnectEnabled, state]);

  useEffect(() => {
    return () => {
      if (state === "connected" || state === "connecting") {
        void invoke<ConnectResponse>("ssh_disconnect", { connection_id: sessionIdRef.current }).catch(() => {});
      }
    };
  }, [state]);

  return (
    <div className="h-full min-h-0 flex flex-col rounded-md border bg-card">
      <div className="flex flex-wrap items-center gap-2 border-b px-2 py-1">
        <div className="text-sm font-semibold">Terminal Local</div>
        <Badge variant={stateBadgeVariant(state)} className="text-[10px] uppercase">
          {state}
        </Badge>

        <Input
          value={host}
          onChange={(event) => setHost(event.target.value)}
          placeholder="host"
          className="h-7 w-[120px]"
          disabled={isConnected || isConnecting}
        />
        <Input
          value={port}
          onChange={(event) => setPort(event.target.value)}
          placeholder="port"
          className="h-7 w-[80px]"
          disabled={isConnected || isConnecting}
        />
        <Input
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          placeholder="username"
          className="h-7 w-[150px]"
          disabled={isConnected || isConnecting}
        />

        <div className="flex items-center rounded border p-0.5 text-xs">
          <button
            type="button"
            onClick={() => setAuthMode("publickey")}
            className={`rounded px-2 py-1 uppercase transition-colors ${
              authMode === "publickey" ? "bg-primary/20 text-primary" : "text-muted-foreground"
            }`}
            disabled={isConnected || isConnecting}
          >
            Key
          </button>
          <button
            type="button"
            onClick={() => setAuthMode("password")}
            className={`rounded px-2 py-1 uppercase transition-colors ${
              authMode === "password" ? "bg-primary/20 text-primary" : "text-muted-foreground"
            }`}
            disabled={isConnected || isConnecting}
          >
            Pass
          </button>
        </div>

        {authMode === "publickey" ? (
          <>
            <Input
              value={keyPath}
              onChange={(event) => setKeyPath(event.target.value)}
              placeholder="key path (optional si localhost)"
              className="h-7 w-[230px]"
              disabled={isConnected || isConnecting}
            />
            <Input
              value={passphrase}
              onChange={(event) => setPassphrase(event.target.value)}
              placeholder="passphrase (optional)"
              className="h-7 w-[170px]"
              type="password"
              disabled={isConnected || isConnecting}
            />
          </>
        ) : (
          <Input
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="password"
            className="h-7 w-[230px]"
            type="password"
            disabled={isConnected || isConnecting}
          />
        )}

        <Button size="sm" variant="outline" onClick={() => void connect()} disabled={isConnected || isConnecting}>
          Connect
        </Button>
        <Button size="sm" variant="outline" onClick={() => void disconnect()} disabled={!isConnected && !isConnecting}>
          Disconnect
        </Button>
        <Button size="sm" variant={showQuickCommands ? "default" : "outline"} onClick={() => setShowQuickCommands((prev) => !prev)}>
          Quick Cmds
        </Button>
        <Button
          size="sm"
          variant={autoConnectEnabled ? "default" : "outline"}
          onClick={() => setAutoConnectEnabled((prev) => !prev)}
          title="Con auto-connect activo, la ventana intenta iniciar terminal al abrir"
        >
          Auto Connect
        </Button>
      </div>

      {showQuickCommands ? (
        <div className="border-b bg-background/60 px-2 py-2">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <span className="text-xs font-semibold text-foreground">Leyenda/atajos terminal:</span>
            {activeService ? (
              <span className="rounded-md border border-primary/40 bg-primary/10 px-2 py-0.5 text-[11px] text-primary">
                contexto: {activeService.name}
              </span>
            ) : (
              <span className="rounded-md border border-border/60 bg-background/40 px-2 py-0.5 text-[11px] text-muted-foreground">
                sin servicio activo
              </span>
            )}
            <select
              value={selectedPresetId}
              onChange={(event) => {
                const nextId = event.target.value;
                setSelectedPresetId(nextId);
                const preset = quickPresets.find((item) => item.id === nextId);
                if (preset) setQuickCommand(preset.command);
              }}
              className="h-7 rounded-md border bg-background px-2 text-xs"
            >
              {quickPresets.map((preset) => (
                <option key={preset.id} value={preset.id}>
                  {preset.label}
                </option>
              ))}
            </select>
            <span className="text-xs text-muted-foreground">{selectedPreset?.description || ""}</span>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Input
              value={quickCommand}
              onChange={(event) => setQuickCommand(event.target.value)}
              placeholder="Comando rápido"
              className="h-7 min-w-[340px] flex-1"
            />
            <Button size="sm" variant="outline" onClick={() => void runQuickCommand()} disabled={!isConnected || quickRunning}>
              {quickRunning ? "Running..." : "Run Quick"}
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                navigator.clipboard.writeText(quickCommand).then(() => {
                  toast.success("Comando copiado");
                });
              }}
            >
              Copy
            </Button>
          </div>

          {quickOutput ? (
            <pre className="mt-2 max-h-28 overflow-auto rounded-md border bg-card/70 p-2 text-[11px] leading-relaxed text-muted-foreground">
              {quickOutput}
            </pre>
          ) : null}
        </div>
      ) : null}

      <div className="min-h-0 flex-1">
        {isConnected ? (
          <PtyTerminal
            connectionId={sessionIdRef.current}
            connectionName={`Terminal ${username}@${host}`}
            host={host}
            username={username}
            onConnectionStatusChange={(_, status) => {
              setState(status);
            }}
          />
        ) : (
          <div className="flex h-full items-center justify-center p-4 text-center text-sm text-muted-foreground">
            Conecta para abrir una terminal interactiva (PTY). Si es local, usa `127.0.0.1` y tu usuario.
          </div>
        )}
      </div>
    </div>
  );
}
