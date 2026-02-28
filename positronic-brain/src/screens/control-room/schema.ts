import { z } from "zod";
import type { ControlRoomConfig } from "./types";

function optionalNullable<T extends z.ZodTypeAny>(schema: T) {
  return z.preprocess((value) => (value === null ? undefined : value), schema.optional());
}

function extractPortFromArgs(args: string[]): number | null {
  for (let i = 0; i < args.length; i += 1) {
    const value = args[i];
    if ((value === "--port" || value === "-p") && args[i + 1]) {
      const parsed = Number.parseInt(args[i + 1], 10);
      if (Number.isFinite(parsed) && parsed > 0 && parsed <= 65535) return parsed;
    }
    if (value.startsWith("--port=")) {
      const parsed = Number.parseInt(value.split("=")[1] ?? "", 10);
      if (Number.isFinite(parsed) && parsed > 0 && parsed <= 65535) return parsed;
    }
  }
  return null;
}

const safeCommandSchema = z.object({
  program: z.string().min(1),
  args: z.array(z.string()).default([]),
  cwd: optionalNullable(z.string()),
  env: optionalNullable(z.record(z.string())),
});

const serviceSchema = z.object({
  id: z.string().min(1),
  name: z.string().min(1),
  tier: optionalNullable(z.enum(["stable", "experimental"])),
  cwd: optionalNullable(z.string()),
  start: safeCommandSchema,
  stop: optionalNullable(safeCommandSchema),
  restart: optionalNullable(safeCommandSchema),
  health: optionalNullable(
    z.object({
      program: z.string().min(1),
      args: z.array(z.string()).default([]),
      intervalSec: z.number().int().positive().optional(),
    }),
  ),
  logSources: z.array(z.string()).default(["stdout", "stderr"]),
});

const workspaceSchema = z.object({
  id: z.string().min(1),
  name: z.string().min(1),
  path: z.string().min(1),
});

const videoAutoPauseSchema = z.object({
  whenModeNotMultimedia: z.boolean().default(true),
  whenPanelHidden: z.boolean().default(true),
  whenAppHidden: z.boolean().default(true),
  whenHighLoad: z.boolean().default(true),
  highLoadLatencyMs: z.number().int().positive().default(350),
  highLoadConsecutiveSamples: z.number().int().positive().default(3),
});

const videoNativeLauncherSchema = z.object({
  id: z.string().min(1),
  name: z.string().min(1),
  command: safeCommandSchema,
});

const videoSnapshotSchema = z.object({
  enabled: z.boolean().default(false),
  timeoutMs: z.number().int().positive().default(20000),
  analyzerCommand: optionalNullable(safeCommandSchema),
});

const videoWallSchema = z.object({
  enabled: z.boolean().default(true),
  maxActiveFeeds: z.number().int().positive().default(2),
  autoPause: videoAutoPauseSchema.default({
    whenModeNotMultimedia: true,
    whenPanelHidden: true,
    whenAppHidden: true,
    whenHighLoad: true,
    highLoadLatencyMs: 350,
    highLoadConsecutiveSamples: 3,
  }),
  nativeLaunchers: z.array(videoNativeLauncherSchema).default([]),
  snapshot: videoSnapshotSchema.default({
    enabled: false,
    timeoutMs: 20000,
  }),
});

const configSchema = z
  .object({
    featureFlags: z.object({
      controlRoomEnabled: z.boolean().default(false),
    }),
    ui: z.object({
      defaultView: z.enum(["control-room", "classic"]).default("classic"),
      rememberLastView: z.boolean().default(true),
      shortcuts: z
        .object({
          commandPalette: z.string().default("Meta+K"),
        })
        .default({ commandPalette: "Meta+K" }),
      layout: z
        .object({
          showLeftSidebar: z.boolean().default(true),
          showTopBar: z.boolean().default(true),
        })
        .default({ showLeftSidebar: true, showTopBar: true }),
    }),
    services: z.array(serviceSchema).default([]),
    workspaces: z.array(workspaceSchema).default([]),
    git: z
      .object({
        enabled: z.boolean().default(true),
        maxCommits: z.number().int().positive().default(30),
      })
      .default({ enabled: true, maxCommits: 30 }),
    videoWall: optionalNullable(videoWallSchema),
  })
  .superRefine((value, ctx) => {
    const seenServiceIds = new Set<string>();
    const seenWorkspaceIds = new Set<string>();
    const servicePortByValue = new Map<number, string>();

    value.services.forEach((service, serviceIndex) => {
      if (seenServiceIds.has(service.id)) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["services", serviceIndex, "id"],
          message: `Duplicate service id '${service.id}'`,
        });
      }
      seenServiceIds.add(service.id);

      const port = extractPortFromArgs(service.start.args);
      if (port === null) return;
      const existingService = servicePortByValue.get(port);
      if (existingService && existingService !== service.id) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["services", serviceIndex, "start", "args"],
          message: `Port ${port} is already used by service '${existingService}'`,
        });
      } else {
        servicePortByValue.set(port, service.id);
      }
    });

    value.workspaces.forEach((workspace, workspaceIndex) => {
      if (seenWorkspaceIds.has(workspace.id)) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["workspaces", workspaceIndex, "id"],
          message: `Duplicate workspace id '${workspace.id}'`,
        });
      }
      seenWorkspaceIds.add(workspace.id);
    });

    if (value.featureFlags.controlRoomEnabled && value.services.length === 0) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["services"],
        message: "ControlRoom enabled but no services configured",
      });
    }
  });

export function parseControlRoomConfig(input: unknown): ControlRoomConfig {
  return configSchema.parse(input);
}

export type ControlRoomConfigSchema = z.infer<typeof configSchema>;
