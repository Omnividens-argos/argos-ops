// Modale contextuelle « voir la donnée » derrière une card IN/OUT (onglet
// Travail). Selon l'IOItem :
//   - ref = URL http(s)  → bouton d'ouverture externe
//   - ref = fichier repo → lecture du contenu (peek backend, whitelist texte)
//   - sinon              → métadonnées + détail (résumé) seuls

import { ExternalLink, FileText, X } from "lucide-react";
import { useEffect, useState } from "react";
import { fetchFilePeek, type RunIOItem } from "../../api";
import { EmptyState } from "../../components/EmptyState";
import { MarkdownPreview } from "../../components/MarkdownPreview";
import { Badge, Button, Flash } from "../../components/ui";

function isHttp(ref: string | null): ref is string {
  return !!ref && /^https?:\/\//i.test(ref);
}

function isFileRef(ref: string | null): ref is string {
  return !!ref && !isHttp(ref) && /\.[a-z0-9]+$/i.test(ref);
}

export function IODetailModal({
  item,
  direction,
  onClose,
}: {
  item: RunIOItem;
  direction: "IN" | "OUT";
  onClose: () => void;
}) {
  const fileRef = isFileRef(item.ref) ? item.ref : null;
  const httpRef = isHttp(item.ref) ? item.ref : null;

  const [content, setContent] = useState<string | null>(null);
  const [suffix, setSuffix] = useState<string>("");
  const [truncated, setTruncated] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!fileRef) return;
    const controller = new AbortController();
    setContent(null);
    setError(null);
    fetchFilePeek(fileRef, controller.signal)
      .then((r) => {
        setContent(r.content);
        setSuffix(r.suffix);
        setTruncated(r.truncated);
      })
      .catch((e) => {
        if (e instanceof DOMException && e.name === "AbortError") return;
        setError((e as Error).message);
      });
    return () => controller.abort();
  }, [fileRef]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const accent = direction === "IN" ? "text-argos-info" : "text-argos-healthy";

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center p-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
    >
      <div className="absolute inset-0 bg-argos-bg/70 backdrop-blur-[2px]" />
      <div
        className="relative w-full max-w-3xl max-h-[85vh] bg-argos-surface border border-argos-border rounded-lg shadow-2xl flex flex-col overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="px-5 py-3 border-b border-argos-border-subtle flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 mb-1 flex-wrap">
              <span className={`font-mono text-[10px] uppercase tracking-widest ${accent}`}>
                {direction}
              </span>
              <h2 className="text-sm font-semibold text-argos-fg truncate">
                {item.label}
              </h2>
              <Badge tone="neutral">{item.kind}</Badge>
              {item.count !== null && <Badge tone="info">{item.count}</Badge>}
            </div>
            {item.ref && (
              <div className="font-mono text-[10px] text-argos-fg-tertiary truncate">
                {item.ref}
              </div>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="shrink-0 font-mono text-[11px] text-argos-fg-tertiary hover:text-argos-fg flex items-center gap-1"
          >
            <X size={12} strokeWidth={2} />
            esc
          </button>
        </header>

        <div className="flex-1 overflow-y-auto">
          {/* Détail / résumé */}
          {item.detail && (
            <div className="px-5 py-3 border-b border-argos-border-subtle text-sm text-argos-fg-secondary leading-relaxed break-words">
              {item.detail}
            </div>
          )}

          {/* URL externe */}
          {httpRef && (
            <div className="p-5">
              <a href={httpRef} target="_blank" rel="noreferrer">
                <Button size="sm" variant="primary">
                  <span className="inline-flex items-center gap-1.5">
                    <ExternalLink size={12} strokeWidth={2} />
                    Ouvrir dans un nouvel onglet
                  </span>
                </Button>
              </a>
            </div>
          )}

          {/* Contenu fichier */}
          {fileRef && (
            <div className="px-5 py-4">
              {error ? (
                <Flash variant="error" message={error} />
              ) : content === null ? (
                <EmptyState tone="loading" title="Lecture du fichier…" compact />
              ) : suffix === ".md" ? (
                <MarkdownPreview content={content} />
              ) : (
                <pre className="font-mono text-[11px] text-argos-fg-secondary whitespace-pre-wrap break-words bg-argos-bg/50 rounded-md p-3 border border-argos-border-subtle">
                  {content}
                </pre>
              )}
              {truncated && (
                <p className="mt-2 font-mono text-[10px] text-argos-warning">
                  Fichier tronqué (aperçu des premiers 200 Ko).
                </p>
              )}
            </div>
          )}

          {/* Rien d'exploitable : juste l'icône d'info */}
          {!item.detail && !httpRef && !fileRef && (
            <div className="p-5">
              <EmptyState
                tone="neutral"
                title="Pas de donnée détaillée"
                body="Cette source n'expose pas de contenu lisible depuis le panel (table DB, API, ou flux interne)."
                compact
              />
            </div>
          )}
        </div>

        <footer className="px-5 py-2 border-t border-argos-border-subtle bg-argos-surface-2/40 font-mono text-[10px] text-argos-fg-tertiary flex items-center gap-1.5">
          <FileText size={11} strokeWidth={2} />
          Lecture seule depuis le panel.
        </footer>
      </div>
    </div>
  );
}
