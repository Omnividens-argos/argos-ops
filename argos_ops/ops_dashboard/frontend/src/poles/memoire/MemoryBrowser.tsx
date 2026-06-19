// Navigateur mémoire par pôle / script (archi v2, S7). Recherche plein texte +
// filtre `important`, et toggle du flag `important` par fait (POST /flag).
// C'est le seul endroit du cockpit où l'on (dé)protège un fait à la main.

import { useCallback, useEffect, useMemo, useState } from "react";
import { RefreshCw, Shield, ShieldOff } from "lucide-react";
import {
  type MemoireBrowse,
  type MemoryFact,
  browseMemoire,
  flagMemoireFact,
} from "../api.ts";
import { Badge, Button, Flash, TextInput } from "../../components/ui.tsx";
import { fmtDateTime } from "./lib.ts";

export function MemoryBrowser({ poles }: { poles: string[] }) {
  const [pole, setPole] = useState<string>("");
  const [script, setScript] = useState<string>("");
  const [query, setQuery] = useState<string>("");
  const [importantOnly, setImportantOnly] = useState(false);
  const [data, setData] = useState<MemoireBrowse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setError(null);
    browseMemoire(
      {
        pole: pole || undefined,
        script: script || undefined,
        q: query || undefined,
        important: importantOnly ? true : undefined,
      },
      controller.signal,
    )
      .then(setData)
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setError(err instanceof Error ? err.message : "Erreur de chargement");
      });
    return () => controller.abort();
  }, [pole, script, query, importantOnly, reloadKey]);

  const toggleFlag = useCallback(
    async (fact: MemoryFact) => {
      setBusy(fact.id);
      setError(null);
      try {
        await flagMemoireFact({
          pole: fact.pole,
          script: fact.script,
          record_id: fact.id,
          important: !fact.important,
        });
        setReloadKey((k) => k + 1);
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Échec du toggle");
      } finally {
        setBusy(null);
      }
    },
    [],
  );

  const records = data?.records ?? [];

  // Autocomplete : suggestions tirées des facettes déjà présentes dans la
  // réponse browse (kinds + scripts + poles connus), dédupliquées et triées.
  const suggestions = useMemo(() => {
    if (!data) return [];
    return Array.from(
      new Set([...data.kinds, ...data.scripts, ...data.poles].filter(Boolean)),
    ).sort((a, b) => a.localeCompare(b));
  }, [data]);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1">
          <span className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary">
            Pôle
          </span>
          <select
            value={pole}
            onChange={(e) => {
              setPole(e.target.value);
              setScript("");
            }}
            className="bg-argos-bg border border-argos-border-subtle rounded-md px-2.5 py-1.5 font-mono text-xs text-argos-fg"
          >
            <option value="">Tous</option>
            {poles.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1">
          <span className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary">
            Script
          </span>
          <select
            value={script}
            onChange={(e) => setScript(e.target.value)}
            className="bg-argos-bg border border-argos-border-subtle rounded-md px-2.5 py-1.5 font-mono text-xs text-argos-fg"
          >
            <option value="">Tous</option>
            {(data?.scripts ?? []).map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
        <div className="min-w-[14rem] flex-1">
          <TextInput
            label="Recherche"
            placeholder="texte, kind ou script…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            list="memory-search-suggestions"
            autoComplete="off"
          />
          <datalist id="memory-search-suggestions">
            {suggestions.map((s) => (
              <option key={s} value={s} />
            ))}
          </datalist>
        </div>
        <Button
          variant={importantOnly ? "primary" : "secondary"}
          size="sm"
          onClick={() => setImportantOnly((v) => !v)}
        >
          important uniquement
        </Button>
        <Button variant="ghost" size="sm" onClick={() => setReloadKey((k) => k + 1)}>
          <RefreshCw className="mr-1 inline h-3 w-3" aria-hidden /> rafraîchir
        </Button>
      </div>

      {error && <Flash variant="error" message={error} onDismiss={() => setError(null)} />}

      <div className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-disabled">
        {data ? `${data.total} fait(s) · ${data.important} important(s)` : "chargement…"}
      </div>

      {records.length === 0 ? (
        <div className="rounded-md border border-dashed border-argos-border-subtle bg-argos-surface px-4 py-6 text-center font-mono text-[11px] text-argos-fg-tertiary">
          Aucun fait pour ce filtre.
        </div>
      ) : (
        <div className="overflow-x-auto rounded-md border border-argos-border-subtle bg-argos-surface">
          <table className="w-full border-collapse text-left">
            <thead>
              <tr className="border-b border-argos-border-subtle text-argos-fg-tertiary">
                {["Quand", "Pôle", "Script", "Kind", "Fait", ""].map((h) => (
                  <th
                    key={h || "act"}
                    className="px-3 py-2 font-mono text-[10px] uppercase tracking-widest font-medium"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {records.map((r) => (
                <tr
                  key={`${r.pole}/${r.script}/${r.id}`}
                  className="border-b border-argos-border-subtle/60 last:border-0 hover:bg-argos-surface-2"
                >
                  <td className="whitespace-nowrap px-3 py-2 font-mono text-[11px] text-argos-fg-tertiary">
                    {fmtDateTime(r.created_at)}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2 font-mono text-[11px] text-argos-fg-secondary">
                    {r.pole}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2 font-mono text-[11px] text-argos-fg-secondary">
                    {r.script}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2">
                    <Badge tone="info">{r.kind}</Badge>
                  </td>
                  <td className="px-3 py-2 font-mono text-[11px] text-argos-fg">
                    <span className="line-clamp-2">{r.body}</span>
                  </td>
                  <td className="whitespace-nowrap px-3 py-2 text-right">
                    <Button
                      variant={r.important ? "primary" : "ghost"}
                      size="sm"
                      disabled={busy === r.id}
                      onClick={() => toggleFlag(r)}
                      title={r.important ? "Retirer la protection" : "Protéger (important)"}
                    >
                      {r.important ? (
                        <Shield className="mr-1 inline h-3 w-3" aria-hidden />
                      ) : (
                        <ShieldOff className="mr-1 inline h-3 w-3" aria-hidden />
                      )}
                      {r.important ? "protégé" : "protéger"}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
