import { Check, FileWarning, Save, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Button } from "./ui";

// YamlEditor — éditeur YAML in-page minimaliste. Pas de Monaco (lourd) :
// juste un <textarea> mono + un parser local (regex légère) qui pointe les
// erreurs basiques de syntaxe. Le backend revalide via PyYAML avant write.
//
// Convention :
//   - read-only si !canEdit (.csv ou fichier absent affiché brut)
//   - dirty détecté par diff string strict
//   - Save désactivé si parsing local échoue (UX : pas d'aller-retour serveur inutile)
//   - undo = restore depuis serverContent

interface YamlEditorProps {
  serverContent: string;
  relativePath: string;
  exists: boolean;
  canEdit: boolean;
  saving?: boolean;
  onSave: (next: string) => Promise<void>;
  onReload?: () => void;
}

export function YamlEditor({
  serverContent,
  relativePath,
  exists,
  canEdit,
  saving,
  onSave,
  onReload,
}: YamlEditorProps) {
  const [value, setValue] = useState(serverContent);
  const [error, setError] = useState<string | null>(null);
  const [showRevertConfirm, setShowRevertConfirm] = useState(false);

  // Resync quand le serveur renvoie une nouvelle version après save / reload.
  useEffect(() => {
    setValue(serverContent);
    setError(null);
  }, [serverContent]);

  // Validation locale très légère : repère les indentations impaires, les
  // tabs (PyYAML refuse), et les `key:value` sans espace. Pas exhaustif —
  // le backend a le dernier mot via yaml.safe_load.
  useEffect(() => {
    if (!canEdit) {
      setError(null);
      return;
    }
    const issue = quickValidate(value);
    setError(issue);
  }, [value, canEdit]);

  const dirty = value !== serverContent;
  const lineCount = value.split("\n").length;

  const handleSave = async () => {
    setError(null);
    try {
      await onSave(value);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <div className="rounded-md border border-argos-border-subtle bg-argos-surface overflow-hidden">
      {/* Header */}
      <div className="px-3 py-2 border-b border-argos-border-subtle flex items-center justify-between gap-3 bg-argos-surface-2/40">
        <div className="min-w-0">
          <div className="font-mono text-xs text-argos-fg truncate">{relativePath}</div>
          <div className="font-mono text-[10px] text-argos-fg-tertiary">
            {exists
              ? `${lineCount} ligne${lineCount > 1 ? "s" : ""}${
                  canEdit ? " · YAML éditable" : " · read-only"
                }`
              : "Fichier absent — sera créé à la sauvegarde"}
            {dirty && canEdit && <span className="text-argos-warning ml-2">· modifié</span>}
          </div>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          {onReload && (
            <Button size="sm" variant="ghost" onClick={onReload} disabled={saving}>
              Reload
            </Button>
          )}
          {canEdit && dirty && !showRevertConfirm && (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => setShowRevertConfirm(true)}
              disabled={saving}
            >
              <span className="inline-flex items-center gap-1">
                <X size={11} strokeWidth={2} />
                Annuler
              </span>
            </Button>
          )}
          {showRevertConfirm && (
            <>
              <span className="font-mono text-[10px] text-argos-warning">
                Perdre les modifs ?
              </span>
              <Button
                size="sm"
                variant="danger"
                onClick={() => {
                  setValue(serverContent);
                  setShowRevertConfirm(false);
                }}
              >
                Oui
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setShowRevertConfirm(false)}
              >
                Non
              </Button>
            </>
          )}
          {canEdit && (
            <Button
              size="sm"
              variant="primary"
              onClick={handleSave}
              disabled={!dirty || saving || error !== null}
              title={error ?? undefined}
            >
              <span className="inline-flex items-center gap-1">
                <Save size={11} strokeWidth={2} />
                {saving ? "Sauvegarde…" : "Sauvegarder"}
              </span>
            </Button>
          )}
        </div>
      </div>

      {/* Editor */}
      <div className="relative">
        <textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          spellCheck={false}
          readOnly={!canEdit}
          rows={Math.max(12, Math.min(28, lineCount + 2))}
          className={`w-full bg-argos-bg/40 px-4 py-3 font-mono text-[11.5px] text-argos-fg leading-relaxed focus:outline-none resize-y ${
            canEdit ? "" : "text-argos-fg-secondary"
          }`}
          onKeyDown={(e) => {
            if (!canEdit) return;
            // Tab insère 2 espaces au curseur (YAML-friendly autoindent).
            // Shift+Tab unindente 2 espaces si présents devant le curseur.
            if (e.key === "Tab") {
              e.preventDefault();
              const target = e.currentTarget;
              const { selectionStart, selectionEnd } = target;
              const before = value.slice(0, selectionStart);
              const after = value.slice(selectionEnd);
              if (e.shiftKey) {
                if (before.endsWith("  ")) {
                  const next = before.slice(0, -2) + after;
                  setValue(next);
                  // Re-place le curseur après le strip (next tick — React l'aura
                  // re-rendered).
                  requestAnimationFrame(() => {
                    target.selectionStart = target.selectionEnd = selectionStart - 2;
                  });
                }
              } else {
                const next = before + "  " + after;
                setValue(next);
                requestAnimationFrame(() => {
                  target.selectionStart = target.selectionEnd = selectionStart + 2;
                });
              }
            }
          }}
        />
      </div>

      {/* Validation feedback */}
      {error && (
        <div className="px-3 py-2 border-t border-argos-warning/30 bg-argos-warning/5 flex items-start gap-2">
          <FileWarning
            size={13}
            strokeWidth={2}
            className="text-argos-warning shrink-0 mt-0.5"
          />
          <span className="font-mono text-[11px] text-argos-warning leading-snug">
            {error}
          </span>
        </div>
      )}
      {!error && dirty && canEdit && (
        <div className="px-3 py-1.5 border-t border-argos-healthy/20 bg-argos-healthy/5 flex items-center gap-2">
          <Check size={11} strokeWidth={2} className="text-argos-healthy shrink-0" />
          <span className="font-mono text-[10px] text-argos-healthy">
            Syntaxe locale OK — le backend re-validera via PyYAML avant écriture.
          </span>
        </div>
      )}
    </div>
  );
}

// =============================================================================
// Validation locale ultra-light
// =============================================================================
function quickValidate(text: string): string | null {
  if (text.trim() === "") return null;
  const lines = text.split("\n");
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (line.includes("\t")) {
      return `Ligne ${i + 1} : tabulation détectée — YAML interdit les tabs, utilise des espaces.`;
    }
    // Détecte `key:value` sans espace après le ":" (sauf valeurs vides et listes).
    const inline = line.match(/^(\s*)([\w-]+):([^\s].*)/);
    if (inline && !inline[3].startsWith("//")) {
      return `Ligne ${i + 1} : espace requis après "${inline[2]}:".`;
    }
  }
  // Pile indentation grossière : doit rester ≥ 0
  let depth = 0;
  for (const line of lines) {
    const match = line.match(/^( *)/);
    if (match) {
      depth = match[1].length;
      if (depth % 2 !== 0 && line.trim() !== "" && !line.trim().startsWith("#")) {
        // PyYAML accepte les indentations impaires mais on prévient quand même.
        return `Indentation impaire détectée (${depth} espaces) — préfère 2 ou 4 espaces pour la lisibilité.`;
      }
    }
  }
  return null;
}
