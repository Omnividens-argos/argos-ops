import {
  Activity,
  Banknote,
  BookOpen,
  Command,
  HeartPulse,
  Inbox,
  LayoutDashboard,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { View } from "../App";

// Bottom-nav mobile (< md). Garde 6 actions essentielles : 5 vues + palette.
// Pour les toggles Densité / Mode interface / Help, l'user passe par la
// palette (⌘K) qui reste accessible via le bouton dédié. C'est volontairement
// minimaliste — la version mobile est en lecture / consultation, pas de
// configuration profonde.

interface Item {
  id: View | "palette";
  label: string;
  icon: LucideIcon;
}

const ITEMS: Item[] = [
  { id: "today", label: "Today", icon: LayoutDashboard },
  { id: "inbox", label: "Inbox", icon: Inbox },
  { id: "agents", label: "Bots", icon: Activity },
  { id: "cash", label: "Cash", icon: Banknote },
  { id: "health", label: "Health", icon: HeartPulse },
  { id: "palette", label: "Action", icon: Command },
];

interface Props {
  current: View;
  onChange: (view: View) => void;
  onOpenPalette: () => void;
}

export function MobileBottomNav({ current, onChange, onOpenPalette }: Props) {
  return (
    <nav
      className="md:hidden fixed bottom-0 inset-x-0 h-14 z-30 bg-argos-surface border-t border-argos-border-subtle flex items-stretch"
      aria-label="Navigation mobile"
    >
      {ITEMS.map((item) => {
        const Icon = item.icon;
        const active = item.id === current;
        const onClick = () => {
          if (item.id === "palette") onOpenPalette();
          else onChange(item.id);
        };
        return (
          <button
            key={item.id}
            type="button"
            onClick={onClick}
            className={`flex-1 flex flex-col items-center justify-center gap-0.5 transition-colors ${
              active
                ? "text-argos-info"
                : "text-argos-fg-tertiary hover:text-argos-fg"
            }`}
            aria-current={active ? "page" : undefined}
            title={item.label}
          >
            <Icon size={16} strokeWidth={2} />
            <span className="font-mono text-[9px] uppercase tracking-widest">
              {item.label}
            </span>
          </button>
        );
      })}
    </nav>
  );
}

// Astuce — sur mobile la sidebar est masquée (md:flex sur la sidebar)
// et on ajoute un padding-bottom au main pour ne pas que la bottom-nav
// recouvre le contenu :
//   <main class="pb-14 md:pb-0 ..."> dans App.tsx.
void BookOpen;
