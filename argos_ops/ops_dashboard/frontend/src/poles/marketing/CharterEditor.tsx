// Éditeur de charte / ton de marque : tagline, domaine canonique, voix, principes,
// à éviter, termes bannis (anti-FUD), disclosure IA. Les listes s'éditent une
// ligne par item. Sauvegarde via PUT /charter (les writers la respectent).

import { useEffect, useState } from "react";
import { Save } from "lucide-react";
import type { MarketingCharter } from "../api.ts";
import { Button, TextInput } from "../../components/ui.tsx";

const TEXTAREA_CLS =
  "w-full rounded-md border border-argos-border-subtle bg-argos-bg px-2.5 py-1.5 font-mono text-[11px] text-argos-fg placeholder:text-argos-fg-disabled focus:outline-none focus:border-argos-info/60";

export interface CharterEditorProps {
  charter: MarketingCharter;
  saving: boolean;
  onSave: (charter: MarketingCharter) => void;
}

const toLines = (xs: string[]) => xs.join("\n");
const fromLines = (s: string): string[] =>
  s
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <label className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary">
        {label}
      </label>
      {children}
    </div>
  );
}

export function CharterEditor({ charter, saving, onSave }: CharterEditorProps) {
  const [tagline, setTagline] = useState(charter.tagline);
  const [domain, setDomain] = useState(charter.domain);
  const [voice, setVoice] = useState(charter.voice);
  const [principles, setPrinciples] = useState(toLines(charter.principles));
  const [avoid, setAvoid] = useState(toLines(charter.avoid));
  const [banned, setBanned] = useState(toLines(charter.banned_terms));
  const [disclosure, setDisclosure] = useState(charter.ai_disclosure);

  // Re-synchronise si la charte rechargée change (après save / refresh).
  useEffect(() => {
    setTagline(charter.tagline);
    setDomain(charter.domain);
    setVoice(charter.voice);
    setPrinciples(toLines(charter.principles));
    setAvoid(toLines(charter.avoid));
    setBanned(toLines(charter.banned_terms));
    setDisclosure(charter.ai_disclosure);
  }, [charter]);

  const submit = () =>
    onSave({
      tagline,
      domain,
      voice,
      principles: fromLines(principles),
      avoid: fromLines(avoid),
      banned_terms: fromLines(banned),
      ai_disclosure: disclosure,
    });

  return (
    <div className="flex flex-col gap-3 rounded-md border border-argos-border-subtle bg-argos-surface px-3 py-3">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <TextInput label="Tagline" value={tagline} onChange={(e) => setTagline(e.target.value)} />
        <TextInput label="Domaine canonique" value={domain} onChange={(e) => setDomain(e.target.value)} />
      </div>
      <Field label="Voix de marque">
        <textarea
          className={`${TEXTAREA_CLS} min-h-[60px] resize-y`}
          value={voice}
          onChange={(e) => setVoice(e.target.value)}
        />
      </Field>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <Field label="Principes (1 par ligne)">
          <textarea
            className={`${TEXTAREA_CLS} min-h-[90px] resize-y`}
            value={principles}
            onChange={(e) => setPrinciples(e.target.value)}
          />
        </Field>
        <Field label="À éviter (1 par ligne)">
          <textarea
            className={`${TEXTAREA_CLS} min-h-[90px] resize-y`}
            value={avoid}
            onChange={(e) => setAvoid(e.target.value)}
          />
        </Field>
      </div>
      <Field label="Termes bannis — anti-FUD (1 par ligne)">
        <textarea
          className={`${TEXTAREA_CLS} min-h-[70px] resize-y`}
          value={banned}
          onChange={(e) => setBanned(e.target.value)}
        />
      </Field>
      <Field label="Disclosure IA">
        <TextInput value={disclosure} onChange={(e) => setDisclosure(e.target.value)} />
      </Field>
      <div>
        <Button size="sm" variant="primary" disabled={saving} onClick={submit}>
          <Save className="mr-1 inline h-3 w-3" aria-hidden /> enregistrer la charte
        </Button>
      </div>
    </div>
  );
}
