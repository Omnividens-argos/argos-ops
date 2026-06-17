// « Pousser vers … » — bouton(s) de handoff d'un signal de veille vers un pôle
// aval (Marketing / Pub / Vente). Enregistre une décision humaine via l'API
// (POST /api/poles/veille/handoff) ; aucune écriture cross-pôle automatique.

import { ArrowUpRight } from "lucide-react";
import { Button } from "../../components/ui.tsx";

const POLE_LABEL: Record<string, string> = {
  marketing: "Marketing",
  pub: "Pub",
  vente: "Vente",
  finance: "Finance",
  direction: "Direction",
};

export function poleLabel(id: string): string {
  return POLE_LABEL[id] ?? id;
}

export interface PushControlProps {
  poles: string[];
  pushedPoles: Set<string>;
  busyPole: string | null;
  onPush: (targetPole: string) => void;
}

export function PushControl({ poles, pushedPoles, busyPole, onPush }: PushControlProps) {
  if (poles.length === 0) {
    return (
      <span className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-disabled">
        aucun pôle aval
      </span>
    );
  }
  return (
    <div className="flex items-center gap-1.5">
      <span className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-disabled">
        pousser →
      </span>
      {poles.map((p) => {
        const done = pushedPoles.has(p);
        return (
          <Button
            key={p}
            size="sm"
            variant={done ? "ghost" : "secondary"}
            disabled={busyPole !== null || done}
            onClick={() => onPush(p)}
          >
            <ArrowUpRight className="mr-0.5 inline h-3 w-3" aria-hidden />
            {done ? `${poleLabel(p)} ✓` : busyPole === p ? "…" : poleLabel(p)}
          </Button>
        );
      })}
    </div>
  );
}
