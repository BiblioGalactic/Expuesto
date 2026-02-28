export type SourceCategory = "llm" | "vision" | "audio" | "systems" | "dev" | "unknown";
export type CategoryVariantKey = "1" | "2" | "3";

const CATEGORY_LABELS: Record<SourceCategory, string> = {
  llm: "LLM",
  vision: "Vision",
  audio: "Audio",
  systems: "Systems",
  dev: "Dev",
  unknown: "Unknown",
};

const CATEGORY_MATCHERS: Array<{ category: SourceCategory; pattern: RegExp }> = [
  {
    category: "llm",
    pattern: /\b(mistral|deepseek|dolphin|unholy|mytho|max|meditron|llama|instruct|gguf)\b/i,
  },
  {
    category: "vision",
    pattern: /\b(image|vision|vlm|yolo|ocr|paddleocr|diffusion|sdxl|caption|detect)\b/i,
  },
  {
    category: "audio",
    pattern: /\b(audio|clone|tts|stt|whisper|voice|xtts|wav|m4a|mp3)\b/i,
  },
  {
    category: "systems",
    pattern: /\b(wa[_-]?bridge|whatsapp|baileys|sms|web\s*scrape|gateway|openclaw|bridge)\b/i,
  },
  {
    category: "dev",
    pattern: /\b(aider|rag|wikirag|retriev|medical|salud|health)\b/i,
  },
];

const MODULE_CATEGORY_BY_ID: Record<string, SourceCategory> = {
  "mod:llm": "llm",
  "mod:rag": "dev",
  "mod:ocr": "vision",
  "mod:audio": "audio",
  "mod:vlm": "vision",
  "mod:yolo": "vision",
  "mod:image": "vision",
  "mod:clone": "audio",
  "mod:aider": "dev",
  "mod:sms": "systems",
  "mod:web": "systems",
  "mod:medical": "dev",
};

export const CATEGORY_LEGEND_ORDER: SourceCategory[] = [
  "llm",
  "vision",
  "audio",
  "systems",
  "dev",
  "unknown",
];

export function categoryLabel(category: SourceCategory): string {
  return CATEGORY_LABELS[category];
}

export function classifySource(serviceId?: string, serviceName?: string, line?: string): SourceCategory {
  const haystack = [serviceId ?? "", serviceName ?? "", line ?? ""].join(" ").toLowerCase();
  if (!haystack.trim()) return "unknown";
  const match = CATEGORY_MATCHERS.find((entry) => entry.pattern.test(haystack));
  return match?.category ?? "unknown";
}

export function categoryFromModuleId(moduleId: string): SourceCategory {
  return MODULE_CATEGORY_BY_ID[moduleId] ?? "unknown";
}

export function categoryPalette(
  category: SourceCategory,
  variant: CategoryVariantKey = "2",
  alpha?: number,
): string {
  const key = `--cr-${category}-${variant}`;
  if (alpha === undefined) return `rgb(var(${key}))`;
  return `rgb(var(${key}) / ${Math.max(0, Math.min(1, alpha))})`;
}
