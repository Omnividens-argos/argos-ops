// PREVIEW de curation d'un pôle (archi v2, S7). Montre AVANT toute suppression :
// la liste « safe to delete » (cochable, validée par l'humain) ET les faits
// protégés (jamais supprimables — l'important est ici, visiblement hors d'atteinte).
// « Supprimer la sélection validée » → POST /clean (gardé côté Python).

import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, Eye, ShieldCheck, Trash2 } from "lucide-react";
import {
  type CleanupResult,
  type CurationPlan,
  type FactDetail,
  type PendingDeletion,
  approveDeletions,
  cleanMemoire,
  fetchMemoireFact,
  fetchMemoirePlan,
  fetchPendingDeletions,
} from "../api.ts";
import { Badge, Button, Flash } from "../../components/ui.tsx";
import { Modal } from "../../components/Modal.tsx";
import { MarkdownPreview } from "../../components/MarkdownPreview.tsx";
import { fmtDate, fmtDateTime } from "./lib.ts";

export function CurationPreview({
  poles,
  onChanged,
}: {
  poles: { pole: string; active: boolean }[];
  onChanged?: () => void;
}) {
  const firstActive = poles.find((p) => p.active)?.pole ?? poles[0]?.pole ?? "";
  const [pole, setPole] = useState<string>(firstActive);
  const [plan, setPlan] = useState<CurationPlan | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<CleanupResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const [approveBusy, setApproveBusy] = useState(false);
  const [pending, setPending] = useState<PendingDeletion[]>([]);

  // Preview du contenu COMPLET d'un fait (candidat à suppression ou protégé),
  // pour décider en connaissance de cause avant de cocher / supprimer.
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewFact, setPreviewFact] = useState<FactDetail | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);

  const key = useCallback((script: string, id: string) => `${script}/${id}`, []);

  const openPreview = useCallback(
    async (script: string, recordId: string) => {
      setPreviewOpen(true);
      setPreviewFact(null);
      setPreviewError(null);
      setPreviewLoading(true);
      try {
        const fact = await fetchMemoireFact(pole, script, recordId);
        setPreviewFact(fact);
      } catch (err: unknown) {
        setPreviewError(
          err instanceof Error ? err.message : "Erreur de chargement du fait",
        );
      } finally {
        setPreviewLoading(false);
      }
    },
    [pole],
  );

  const closePreview = useCallback(() => {
    setPreviewOpen(false);
    setPreviewFact(null);
    setPreviewError(null);
  }, []);

  // Reset du résultat au CHANGEMENT DE PÔLE uniquement — pas au reloadKey, sinon
  // le rechargement déclenché par un clean effacerait le flash de feedback qu'on
  // vient de poser (la preuve visible « Python tranche » : combien refusés/supprimés).
  useEffect(() => {
    setResult(null);
  }, [pole]);

  useEffect(() => {
    if (!pole) return;
    const controller = new AbortController();
    setError(null);
    fetchMemoirePlan(pole, controller.signal)
      .then((p) => {
        setPlan(p);
        // Par défaut : tout le « safe to delete » est pré-sélectionné.
        setSelected(new Set(p.to_delete.map((c) => key(c.script, c.record_id))));
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setError(err instanceof Error ? err.message : "Erreur de chargement du plan");
      });
    return () => controller.abort();
  }, [pole, reloadKey, key]);

  // Liste persistée des suppressions APPROUVÉES, en attente d'exécution par le bot.
  useEffect(() => {
    if (!pole) {
      setPending([]);
      return;
    }
    const controller = new AbortController();
    fetchPendingDeletions(pole, controller.signal)
      .then(setPending)
      .catch(() => {
        if (controller.signal.aborted) return;
        setPending([]);
      });
    return () => controller.abort();
  }, [pole, reloadKey]);

  const toggle = useCallback((k: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(k)) next.delete(k);
      else next.add(k);
      return next;
    });
  }, []);

  const selectedTargets = useMemo(() => {
    if (!plan) return [];
    return plan.to_delete
      .filter((c) => selected.has(key(c.script, c.record_id)))
      .map((c) => ({ script: c.script, record_id: c.record_id }));
  }, [plan, selected, key]);

  const runClean = useCallback(async () => {
    if (!pole || selectedTargets.length === 0) return;
    setBusy(true);
    setError(null);
    setResult(null); // efface le feedback précédent AVANT la requête (pas dans l'effet reload)
    try {
      const res = await cleanMemoire({ pole, targets: selectedTargets });
      setResult(res);
      setReloadKey((k) => k + 1);
      onChanged?.();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Échec de la suppression");
    } finally {
      setBusy(false);
    }
  }, [pole, selectedTargets, onChanged]);

  // PERSISTE la sélection validée comme suppressions « en attente d'exécution »
  // (le bot tranchera côté Python), sans rien supprimer ici. Recharge le compteur.
  const runApprove = useCallback(async () => {
    if (!pole || selectedTargets.length === 0) return;
    setApproveBusy(true);
    setError(null);
    try {
      await approveDeletions(pole, selectedTargets);
      const refreshed = await fetchPendingDeletions(pole);
      setPending(refreshed);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Échec de l'approbation");
    } finally {
      setApproveBusy(false);
    }
  }, [pole, selectedTargets]);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1">
          <span className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary">
            Pôle à curer
          </span>
          <select
            value={pole}
            onChange={(e) => setPole(e.target.value)}
            className="bg-argos-bg border border-argos-border-subtle rounded-md px-2.5 py-1.5 font-mono text-xs text-argos-fg"
          >
            {poles.map((p) => (
              <option key={p.pole} value={p.pole}>
                {p.pole}
                {p.active ? "" : " (inactif)"}
              </option>
            ))}
          </select>
        </label>
        {plan && (
          <div className="flex items-center gap-4 font-mono text-[11px]">
            <span className="text-argos-fg-tertiary">{plan.scanned} scanné(s)</span>
            <span className="text-argos-danger">{plan.n_delete} à supprimer</span>
            <span className="text-argos-warning">{plan.n_important} important(s)</span>
            <span className="text-argos-healthy">{plan.kept} conservé(s)</span>
          </div>
        )}
      </div>

      {error && <Flash variant="error" message={error} onDismiss={() => setError(null)} />}
      {result && (
        <Flash
          variant="success"
          message={`${result.n_deleted} supprimé(s), ${result.n_refused} refusé(s)${
            result.skipped > 0 ? `, ${result.skipped} ignoré(s)` : ""
          } sur ${result.requested} validé(s).`}
          onDismiss={() => setResult(null)}
        />
      )}

      {plan && !plan.active && (
        <div className="rounded-md border border-dashed border-argos-border-subtle bg-argos-surface px-4 py-6 text-center font-mono text-[11px] text-argos-fg-tertiary">
          Pôle non actif pour la curation (cf. Activation) — {plan.scanned} fait(s) intacts.
        </div>
      )}

      {plan && plan.active && (
        <>
          {/* Safe to delete — cochable. */}
          <section className="flex flex-col gap-2">
            <div className="flex items-center justify-between gap-2">
              <h3 className="flex items-center gap-1.5 font-mono text-[11px] font-medium text-argos-danger">
                <Trash2 className="h-3.5 w-3.5" aria-hidden /> Safe to delete (
                {selected.size}/{plan.n_delete} sélectionné(s))
              </h3>
              <div className="flex items-center gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={approveBusy || busy || selected.size === 0}
                  onClick={runApprove}
                >
                  Approuver la sélection
                </Button>
                <Button
                  variant="danger"
                  size="sm"
                  disabled={busy || selected.size === 0}
                  onClick={runClean}
                >
                  Supprimer la sélection validée
                </Button>
              </div>
            </div>
            {pending.length > 0 && (
              <p className="font-mono text-[10px] text-argos-fg-tertiary">
                {pending.length} suppression(s) en attente d'exécution
              </p>
            )}
            {plan.to_delete.length === 0 ? (
              <div className="rounded-md border border-dashed border-argos-border-subtle bg-argos-surface px-4 py-5 text-center font-mono text-[11px] text-argos-fg-tertiary">
                Rien à supprimer — la mémoire de ce pôle est saine.
              </div>
            ) : (
              <ul className="flex flex-col gap-1.5">
                {plan.to_delete.map((c) => {
                  const k = key(c.script, c.record_id);
                  return (
                    <li
                      key={k}
                      className="flex items-start gap-2.5 rounded-md border border-argos-danger/30 bg-argos-danger/5 px-3 py-2"
                    >
                      <input
                        type="checkbox"
                        checked={selected.has(k)}
                        onChange={() => toggle(k)}
                        className="mt-1 accent-argos-danger"
                        aria-label={`supprimer ${c.script}/${c.record_id}`}
                      />
                      <div className="flex min-w-0 flex-1 flex-col gap-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge tone="danger">{c.reason}</Badge>
                          <Badge tone="neutral">{c.kind}</Badge>
                          <span className="font-mono text-[10px] text-argos-fg-tertiary">
                            {c.script} · {fmtDate(c.created_at)} · {c.age_days} j
                          </span>
                        </div>
                        <span className="font-mono text-[11px] text-argos-fg">
                          {c.body_preview}
                        </span>
                        <span className="font-mono text-[10px] text-argos-fg-disabled">
                          {c.detail}
                        </span>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="shrink-0"
                        onClick={() => openPreview(c.script, c.record_id)}
                        aria-label={`voir le contenu de ${c.script}/${c.record_id}`}
                      >
                        <Eye className="mr-1 inline h-3 w-3" aria-hidden /> voir le contenu
                      </Button>
                    </li>
                  );
                })}
              </ul>
            )}
          </section>

          {/* Protégés — jamais supprimables (l'important est ici). */}
          <section className="flex flex-col gap-2">
            <h3 className="flex items-center gap-1.5 font-mono text-[11px] font-medium text-argos-healthy">
              <ShieldCheck className="h-3.5 w-3.5" aria-hidden /> Protégés —
              non supprimables ({plan.n_protected}, dont {plan.n_saved_from_delete} sauvé(s) du
              nettoyage)
            </h3>
            {plan.protected.length === 0 ? (
              <div className="rounded-md border border-dashed border-argos-border-subtle bg-argos-surface px-4 py-4 text-center font-mono text-[11px] text-argos-fg-tertiary">
                Aucun fait protégé dans ce pôle.
              </div>
            ) : (
              <ul className="flex flex-col gap-1.5">
                {plan.protected.map((p) => (
                  <li
                    key={`${p.script}/${p.record_id}`}
                    className="flex items-start gap-2.5 rounded-md border border-argos-healthy/30 bg-argos-healthy/5 px-3 py-2"
                  >
                    <ShieldCheck
                      className="mt-0.5 h-3.5 w-3.5 shrink-0 text-argos-healthy"
                      aria-hidden
                    />
                    <div className="flex min-w-0 flex-1 flex-col gap-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge tone={p.reason === "important" ? "warning" : "info"}>
                          {p.reason}
                        </Badge>
                        <Badge tone="neutral">{p.kind}</Badge>
                        {p.would_delete && (
                          <span className="flex items-center gap-1 font-mono text-[10px] text-argos-warning">
                            <AlertTriangle className="h-3 w-3" aria-hidden /> aurait été supprimé (
                            {p.would_delete_reason}) — sauvé
                          </span>
                        )}
                      </div>
                      <span className="font-mono text-[11px] text-argos-fg">{p.body_preview}</span>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="shrink-0"
                      onClick={() => openPreview(p.script, p.record_id)}
                      aria-label={`voir le contenu de ${p.script}/${p.record_id}`}
                    >
                      <Eye className="mr-1 inline h-3 w-3" aria-hidden /> voir le contenu
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {result && result.refused.length > 0 && (
            <section className="flex flex-col gap-1">
              <h4 className="font-mono text-[10px] uppercase tracking-widest text-argos-warning">
                Refusés par garde-fou
              </h4>
              <ul className="flex flex-col gap-1">
                {result.refused.map((r) => (
                  <li
                    key={`${r.script}/${r.record_id}`}
                    className="font-mono text-[11px] text-argos-fg-secondary"
                  >
                    {r.script}/{r.record_id} — {r.reason}
                  </li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}

      <Modal
        open={previewOpen}
        onClose={closePreview}
        title={
          previewFact
            ? `${previewFact.script} · ${previewFact.kind}`
            : "Contenu du fait"
        }
        size="lg"
        footer={
          <Button variant="secondary" size="sm" onClick={closePreview}>
            Fermer
          </Button>
        }
      >
        {previewLoading && (
          <p className="font-mono text-[11px] text-argos-fg-tertiary">Chargement…</p>
        )}
        {previewError && (
          <Flash
            variant="error"
            message={previewError}
            onDismiss={() => setPreviewError(null)}
          />
        )}
        {previewFact && (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={previewFact.important ? "warning" : "neutral"}>
                {previewFact.important ? "important" : previewFact.kind}
              </Badge>
              <span className="font-mono text-[10px] text-argos-fg-tertiary">
                {previewFact.pole} · {previewFact.script} · {fmtDateTime(previewFact.created_at)}
              </span>
            </div>
            {previewFact.tags.length > 0 && (
              <div className="flex flex-wrap items-center gap-1.5">
                {previewFact.tags.map((t) => (
                  <Badge key={t} tone="info">
                    {t}
                  </Badge>
                ))}
              </div>
            )}
            {previewFact.source && (
              <p className="font-mono text-[10px] text-argos-fg-tertiary">
                source : {previewFact.source}
              </p>
            )}
            <div className="rounded-md border border-argos-border-subtle bg-argos-bg/40 p-3">
              <MarkdownPreview content={previewFact.body} />
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
