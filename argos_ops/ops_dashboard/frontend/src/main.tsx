import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App.tsx";
import "./index.css";

// Bootstrap React 18+ avec StrictMode. Le panel est privé (un seul user, le
// fondateur) donc pas besoin de gestion de routes complexe — les vues
// (Overview / Agents / Runs) seront switchées via état local en session 2.
const rootElement = document.getElementById("root");
if (!rootElement) {
  throw new Error("#root introuvable dans index.html");
}

createRoot(rootElement).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
