import type { HealthCheck } from "../api";
import { formatAbsoluteTime } from "../lib/format";
import { ThemeToggle } from "./ThemeToggle";

interface Props {
  health: HealthCheck | null;
  lastRefreshedAt: Date | null;
  trippedBreakers: number;
}

export function Topbar({ health, lastRefreshedAt, trippedBreakers }: Props) {
  const dbOk = health?.ok ?? false;

  return (
    <header className="h-12 shrink-0 border-b border-argos-border-subtle bg-argos-surface flex items-center justify-between px-5 theme-transition">
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-2">
          <div
            className={`size-2 rounded-full ${dbOk ? "bg-argos-healthy" : "bg-argos-danger"}`}
            aria-label={dbOk ? "DB up" : "DB down"}
          />
          <span className="font-mono text-xs text-argos-fg-secondary">
            {dbOk ? "Postgres online" : "Postgres unreachable"}
          </span>
        </div>
        {health && (
          <span className="font-mono text-[11px] text-argos-fg-tertiary">
            v{health.version}
          </span>
        )}
      </div>

      <div className="flex items-center gap-4">
        {trippedBreakers > 0 && (
          <div className="flex items-center gap-2 px-2.5 py-1 rounded-md border border-argos-danger/40 bg-argos-danger/10">
            <span className="size-1.5 rounded-full bg-argos-danger animate-pulse" />
            <span className="font-mono text-xs text-argos-danger">
              {trippedBreakers} breaker{trippedBreakers > 1 ? "s" : ""} tripped
            </span>
          </div>
        )}
        <span className="font-mono text-[11px] text-argos-fg-tertiary hidden md:inline">
          Last refresh : {lastRefreshedAt ? formatAbsoluteTime(lastRefreshedAt.toISOString()) : "—"}
        </span>
        <ThemeToggle />
      </div>
    </header>
  );
}
