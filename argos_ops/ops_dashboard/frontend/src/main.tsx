import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { AppShell } from "./AppShell.tsx";
import { ToastProvider } from "./components/Toast.tsx";
import { UserPrefsProvider } from "./hooks/useUserPrefs.tsx";
import { queryClient } from "./lib/queryClient.ts";
import "./index.css";

// Entrée UNIQUE du cockpit unifié (refonte SF). Providers : React Query
// (data-fetching) + UserPrefs (densité/mode) + Toast (notifications).
const rootElement = document.getElementById("root");
if (!rootElement) {
  throw new Error("#root introuvable dans index.html");
}

createRoot(rootElement).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <UserPrefsProvider>
        <ToastProvider>
          <AppShell />
        </ToastProvider>
      </UserPrefsProvider>
    </QueryClientProvider>
  </StrictMode>,
);
