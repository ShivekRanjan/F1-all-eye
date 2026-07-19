import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";

export interface PaletteItem {
  id: string;
  label: string;
  group: string;
  icon?: ReactNode;
}

/** Ctrl/Cmd+K quick-jump — type to filter, arrows to move, Enter to go,
 *  Escape to close. Scoped to navigation (tabs) rather than reaching into
 *  each view's own local state (circuit/season pickers aren't globally
 *  addressable), so every result here is a real, complete destination. */
export function CommandPalette({
  open,
  onClose,
  items,
  onSelect,
}: {
  open: boolean;
  onClose: () => void;
  items: PaletteItem[];
  onSelect: (id: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter((it) => it.label.toLowerCase().includes(q) || it.group.toLowerCase().includes(q));
  }, [items, query]);

  useEffect(() => {
    if (!open) return;
    setQuery("");
    setActive(0);
    const raf = requestAnimationFrame(() => inputRef.current?.focus());
    return () => cancelAnimationFrame(raf);
  }, [open]);

  useEffect(() => {
    setActive(0);
  }, [query]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      } else if (e.key === "ArrowDown") {
        e.preventDefault();
        setActive((a) => Math.min(a + 1, filtered.length - 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setActive((a) => Math.max(a - 1, 0));
      } else if (e.key === "Enter") {
        e.preventDefault();
        const item = filtered[active];
        if (item) {
          onSelect(item.id);
          onClose();
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, filtered, active, onClose, onSelect]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-start justify-center bg-black/60 pt-[15vh]"
      onClick={onClose}
    >
      <div
        className="w-full max-w-lg overflow-hidden rounded-xl2 border border-line-card bg-carbon-800 shadow-card animate-fadein"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-2 border-b border-line px-4 py-3">
          <span className="text-accent">◆</span>
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Jump to…"
            className="w-full bg-transparent text-sm text-ink outline-none placeholder:text-ink-dim"
          />
          <kbd className="rounded border border-line-ctl px-1.5 py-0.5 font-mono text-[10px] text-ink-faint">
            esc
          </kbd>
        </div>
        <div className="max-h-80 overflow-y-auto p-2">
          {filtered.length === 0 && (
            <div className="px-3 py-6 text-center text-sm text-ink-muted">No matches.</div>
          )}
          {filtered.map((it, i) => (
            <button
              key={it.id}
              onMouseEnter={() => setActive(i)}
              onClick={() => {
                onSelect(it.id);
                onClose();
              }}
              className={`flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm transition ${
                i === active ? "bg-accent/15 text-accent" : "text-ink-dim hover:bg-surface-inset/70"
              }`}
            >
              <span className="shrink-0" aria-hidden>
                {it.icon}
              </span>
              <span className="flex-1 truncate">{it.label}</span>
              <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-ink-faint">{it.group}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

/** "?" cheat sheet — the other half of "keyboard shortcuts exist and are
 *  discoverable", not just Ctrl+K working silently. */
export function ShortcutsHelp({ open, onClose }: { open: boolean; onClose: () => void }) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const rows: [string, string][] = [
    ["Ctrl / Cmd + K", "Jump to any section"],
    ["↑ / ↓", "Move through results"],
    ["Enter", "Go"],
    ["Esc", "Close"],
    ["?", "This list"],
  ];

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60" onClick={onClose}>
      <div
        className="w-full max-w-sm overflow-hidden rounded-xl2 border border-line-card bg-carbon-800 p-5 shadow-card animate-fadein"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-3 font-mono text-[11px] uppercase tracking-[0.16em] text-accent">
          ◆ Keyboard shortcuts
        </div>
        <div className="space-y-2">
          {rows.map(([key, desc]) => (
            <div key={key} className="flex items-center justify-between text-sm">
              <span className="text-ink-muted">{desc}</span>
              <kbd className="rounded border border-line-ctl bg-surface-inset px-2 py-0.5 font-mono text-[11px] text-ink">
                {key}
              </kbd>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
