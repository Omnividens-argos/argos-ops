import { Activity, Command, Inbox, LayoutDashboard } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useEffect, useState } from "react";
import { Button } from "./ui";

// Tour d'onboarding 5 étapes au premier lancement. Stockage localStorage
// pour ne pas re-déclencher après la première fermeture. Re-déclenchable
// via Help & Glossary (Phase 3) ou la palette (« onboarding tour »).
//
// Pas d'overlay/highlight pour le moment (pas de positionnement DOM lourd) —
// on présente un carousel modal avec illustrations en lucide. Au step final,
// on bascule sur Today.

const STORAGE_KEY = "argos.onboardingSeen.v1";

interface Step {
  icon: LucideIcon;
  iconColor: string;
  title: string;
  body: string;
}

const STEPS: Step[] = [
  {
    icon: LayoutDashboard,
    iconColor: "text-argos-info",
    title: "Bienvenue sur Argos Ops",
    body: "C'est ton cockpit. Une flotte de bots automatise ton acquisition, ton support, ta finance, ta veille. Toi tu pilotes, tu valides, tu décides — eux exécutent.",
  },
  {
    icon: LayoutDashboard,
    iconColor: "text-argos-healthy",
    title: "« Aujourd'hui » — ta page d'accueil",
    body: "À l'ouverture, tu vois en 30 secondes : combien d'alertes, combien de drafts à valider, combien de runs aujourd'hui, et où ton attention est demandée. Pas plus.",
  },
  {
    icon: Inbox,
    iconColor: "text-argos-warning",
    title: "« Inbox » — ce que les bots attendent de toi",
    body: "Quand un bot drafte un email, un post LinkedIn, un devis ou un CP, il pose le brouillon là. Tu valides, ajustes, ou rejettes. C'est le seul endroit où tu agis quotidiennement.",
  },
  {
    icon: Activity,
    iconColor: "text-argos-fg",
    title: "« Catalogue » — la flotte complète",
    body: "79 bots regroupés en 12 services (Finance, Sales, Marketing, Tech, etc.). Tu peux toggle on/off, mettre en pause 1h ou 24h, ouvrir la page détail pour configurer chaque bot.",
  },
  {
    icon: Command,
    iconColor: "text-argos-info",
    title: "Raccourcis qui vont te sauver",
    body: "Appuie sur Ctrl+K à tout moment pour ouvrir la palette : tape « run uptime », « inbox », « finance », ce que tu veux. Touches 1/2/3/4/5 pour switcher de vue. ⌘+/ pour la liste complète (à venir).",
  },
];

interface Props {
  /** Force l'ouverture (depuis Help). */
  forceOpen?: boolean;
  onFinish?: () => void;
}

export function OnboardingTour({ forceOpen, onFinish }: Props) {
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState(0);

  useEffect(() => {
    if (forceOpen) {
      setOpen(true);
      setStep(0);
      return;
    }
    try {
      const seen = window.localStorage.getItem(STORAGE_KEY);
      if (seen !== "1") {
        setOpen(true);
      }
    } catch {
      // localStorage indisponible (mode privé) — on skip.
    }
  }, [forceOpen]);

  if (!open) return null;

  const current = STEPS[step];
  const isLast = step === STEPS.length - 1;
  const Icon = current.icon;

  const close = () => {
    try {
      window.localStorage.setItem(STORAGE_KEY, "1");
    } catch {
      // ignore
    }
    setOpen(false);
    onFinish?.();
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="onboarding-title"
    >
      <div className="absolute inset-0 bg-argos-bg/80 backdrop-blur-sm" />
      <div className="relative w-full max-w-md bg-argos-surface border border-argos-border rounded-lg shadow-2xl overflow-hidden">
        <div className="p-6 space-y-4">
          <div
            className={`size-12 rounded-md bg-argos-surface-2 flex items-center justify-center ${current.iconColor}`}
          >
            <Icon size={24} strokeWidth={1.5} />
          </div>
          <div className="space-y-2">
            <h2
              id="onboarding-title"
              className="text-lg font-semibold text-argos-fg"
            >
              {current.title}
            </h2>
            <p className="text-sm text-argos-fg-secondary leading-relaxed">
              {current.body}
            </p>
          </div>
        </div>

        <div className="px-6 py-3 border-t border-argos-border-subtle flex items-center justify-between bg-argos-surface-2/40">
          <div className="flex items-center gap-1.5">
            {STEPS.map((_, idx) => (
              <span
                key={idx}
                className={`size-1.5 rounded-full transition-colors ${
                  idx === step ? "bg-argos-info" : "bg-argos-border"
                }`}
              />
            ))}
          </div>
          <div className="flex items-center gap-2">
            {!isLast && (
              <Button variant="ghost" size="sm" onClick={close}>
                Passer
              </Button>
            )}
            <Button
              variant="primary"
              size="sm"
              onClick={() => {
                if (isLast) close();
                else setStep((s) => s + 1);
              }}
            >
              {isLast ? "Commencer" : "Suivant →"}
            </Button>
          </div>
        </div>

        {/* Footer info: shortcut for re-opening later */}
        <div className="px-6 pb-3 -mt-1 font-mono text-[10px] text-argos-fg-tertiary text-right">
          step {step + 1} / {STEPS.length}
        </div>
      </div>
    </div>
  );
}

export function resetOnboardingFlag(): void {
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // ignore
  }
}
