import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandShortcut,
} from "@/components/ui/command";
import { useEffect, useMemo, useState } from "react";

export interface PaletteAction {
  id: string;
  label: string;
  group: string;
  shortcut?: string;
  run: () => void;
}

function parseShortcut(shortcut: string) {
  const tokens = shortcut
    .split("+")
    .map((token) => token.trim().toLowerCase())
    .filter(Boolean);
  return {
    meta: tokens.includes("meta") || tokens.includes("cmd"),
    ctrl: tokens.includes("ctrl") || tokens.includes("control"),
    shift: tokens.includes("shift"),
    alt: tokens.includes("alt") || tokens.includes("option"),
    key: tokens[tokens.length - 1],
  };
}

export function CommandPalette({ shortcut, actions }: { shortcut: string; actions: PaletteAction[] }) {
  const [open, setOpen] = useState(false);
  const parsed = useMemo(() => parseShortcut(shortcut), [shortcut]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      const key = event.key.toLowerCase();
      const matches =
        key === parsed.key &&
        (!!parsed.meta === event.metaKey) &&
        (!!parsed.ctrl === event.ctrlKey) &&
        (!!parsed.shift === event.shiftKey) &&
        (!!parsed.alt === event.altKey);

      if (!matches) return;
      event.preventDefault();
      setOpen((prev) => !prev);
    }

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [parsed]);

  const grouped = useMemo(() => {
    const map = new Map<string, PaletteAction[]>();
    actions.forEach((action) => {
      const bucket = map.get(action.group) ?? [];
      bucket.push(action);
      map.set(action.group, bucket);
    });
    return map;
  }, [actions]);

  return (
    <CommandDialog open={open} onOpenChange={setOpen}>
      <CommandInput placeholder="Omnibar: escribe /comando, servicio, workspace o acción..." />
      <CommandList>
        <CommandEmpty>No results found.</CommandEmpty>
        {Array.from(grouped.entries()).map(([group, groupActions]) => (
          <CommandGroup key={group} heading={group}>
            {groupActions.map((action) => (
              <CommandItem
                key={action.id}
                onSelect={() => {
                  action.run();
                  setOpen(false);
                }}
              >
                <span>{action.label}</span>
                {action.shortcut ? <CommandShortcut>{action.shortcut}</CommandShortcut> : null}
              </CommandItem>
            ))}
          </CommandGroup>
        ))}
      </CommandList>
    </CommandDialog>
  );
}
