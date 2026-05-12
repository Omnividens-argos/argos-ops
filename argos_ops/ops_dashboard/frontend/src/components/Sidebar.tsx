import type { View } from "../App";

interface NavItem {
  id: View;
  label: string;
  shortcut: string;
}

const ITEMS: NavItem[] = [
  { id: "overview", label: "Overview", shortcut: "1" },
  { id: "agents", label: "Agents", shortcut: "2" },
  { id: "runs", label: "Runs", shortcut: "3" },
  { id: "breakers", label: "Breakers", shortcut: "4" },
];

interface Props {
  current: View;
  onChange: (view: View) => void;
}

export function Sidebar({ current, onChange }: Props) {
  return (
    <aside className="w-56 shrink-0 border-r border-argos-border-subtle bg-argos-surface flex flex-col">
      <div className="px-5 py-5 border-b border-argos-border-subtle">
        <div className="flex items-center gap-2">
          <div className="size-2 rounded-full bg-argos-healthy" />
          <div className="font-mono text-[11px] uppercase tracking-widest text-argos-fg-tertiary">
            Argos Ops
          </div>
        </div>
        <div className="mt-1 text-sm font-semibold text-argos-fg">Admin Panel</div>
      </div>

      <nav className="flex-1 px-2 py-3 space-y-0.5">
        {ITEMS.map((item) => {
          const active = item.id === current;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onChange(item.id)}
              className={`w-full flex items-center justify-between px-3 py-2 rounded-md text-sm transition-colors ${
                active
                  ? "bg-argos-surface-2 text-argos-fg"
                  : "text-argos-fg-secondary hover:bg-argos-surface-2/60 hover:text-argos-fg"
              }`}
            >
              <span>{item.label}</span>
              <kbd className="font-mono text-[10px] text-argos-fg-tertiary border border-argos-border-subtle rounded px-1.5 py-0.5">
                {item.shortcut}
              </kbd>
            </button>
          );
        })}
      </nav>

      <div className="border-t border-argos-border-subtle px-5 py-3 text-[11px] font-mono text-argos-fg-tertiary leading-relaxed">
        <div>P16.B · controls live</div>
        <div className="mt-0.5">escalations → P16.C</div>
      </div>
    </aside>
  );
}
