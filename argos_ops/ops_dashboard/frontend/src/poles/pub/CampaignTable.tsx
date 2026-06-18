// Tableau de performance des campagnes (dernier export par plateforme). CPA
// coloré vs cible (80 € démo). Lecture seule — la donnée vient des CSV
// data/poles/pub/campaigns/. Miroir de pub/optimizer.CampaignRow.

import type { AdCampaign, AdPlatform } from "../api.ts";
import { eur, pct, platformLabel } from "./lib.ts";

const CPA_TARGET_EUR = 80;

export interface CampaignTableProps {
  campaigns: AdCampaign[];
  platforms: AdPlatform[];
}

export function CampaignTable({ campaigns, platforms }: CampaignTableProps) {
  if (campaigns.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-argos-border-subtle bg-argos-surface px-4 py-6 text-center font-mono text-[11px] text-argos-fg-tertiary">
        Aucun export de campagne (data/poles/pub/campaigns/&lt;date&gt;-&lt;plateforme&gt;.csv).
      </div>
    );
  }
  return (
    <div className="overflow-x-auto rounded-md border border-argos-border-subtle bg-argos-surface">
      <table className="w-full border-collapse font-mono text-[11px]">
        <thead>
          <tr className="border-b border-argos-border-subtle text-argos-fg-tertiary">
            <th className="px-3 py-2 text-left font-normal uppercase tracking-widest text-[10px]">
              Campagne
            </th>
            <th className="px-2 py-2 text-right font-normal">Impr.</th>
            <th className="px-2 py-2 text-right font-normal">Clics</th>
            <th className="px-2 py-2 text-right font-normal">CTR</th>
            <th className="px-2 py-2 text-right font-normal">Coût</th>
            <th className="px-2 py-2 text-right font-normal">Conv.</th>
            <th className="px-3 py-2 text-right font-normal">CPA</th>
          </tr>
        </thead>
        <tbody>
          {campaigns.map((c) => {
            const cpaTone =
              c.conversions === 0
                ? "text-argos-danger"
                : c.cpa > CPA_TARGET_EUR * 2
                  ? "text-argos-danger"
                  : c.cpa > CPA_TARGET_EUR
                    ? "text-argos-warning"
                    : "text-argos-healthy";
            return (
              <tr
                key={`${c.platform}-${c.campaign}`}
                className="border-b border-argos-border-subtle/50 last:border-0"
              >
                <td className="px-3 py-1.5 text-left">
                  <span className="text-argos-fg">{c.campaign}</span>
                  <span className="ml-1.5 text-[9px] text-argos-fg-disabled">
                    {platformLabel(platforms, c.platform)}
                  </span>
                </td>
                <td className="px-2 py-1.5 text-right text-argos-fg-secondary">
                  {c.impressions.toLocaleString("fr-FR")}
                </td>
                <td className="px-2 py-1.5 text-right text-argos-fg-secondary">{c.clicks}</td>
                <td className="px-2 py-1.5 text-right text-argos-fg-secondary">{pct(c.ctr)}</td>
                <td className="px-2 py-1.5 text-right text-argos-fg-secondary">{eur(c.cost_eur)}</td>
                <td className="px-2 py-1.5 text-right text-argos-fg-secondary">{c.conversions}</td>
                <td className={`px-3 py-1.5 text-right ${cpaTone}`}>
                  {c.conversions === 0 ? "—" : eur(c.cpa)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
