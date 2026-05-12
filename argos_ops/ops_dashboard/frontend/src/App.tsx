// Bootstrap minimal P16.A session 1 — Hello placeholder.
// Les composants Overview / Agents / Runs arrivent en session 2.
export function App() {
  return (
    <main className="min-h-screen flex items-center justify-center p-8">
      <div className="max-w-md text-center space-y-4">
        <p className="font-mono text-xs uppercase tracking-widest text-argos-fg-tertiary">
          Argos Ops — Admin Control Panel
        </p>
        <h1 className="text-3xl font-semibold text-argos-fg">
          P16.A bootstrap — session 1
        </h1>
        <p className="text-argos-fg-secondary text-sm leading-relaxed">
          Backend FastAPI opérationnel sur{" "}
          <code className="font-mono text-argos-info">:9000</code>. UI dense
          dark-mode arrive en session 2 (Overview · Agents · Runs).
        </p>
        <p className="text-argos-fg-tertiary text-xs">
          <a
            href="/api/health"
            className="text-argos-healthy hover:underline"
            target="_blank"
            rel="noopener"
          >
            /api/health
          </a>{" "}
          ·{" "}
          <a
            href="/api/agents"
            className="text-argos-healthy hover:underline"
            target="_blank"
            rel="noopener"
          >
            /api/agents
          </a>{" "}
          ·{" "}
          <a
            href="/api/kpis/overview"
            className="text-argos-healthy hover:underline"
            target="_blank"
            rel="noopener"
          >
            /api/kpis/overview
          </a>
        </p>
      </div>
    </main>
  );
}
