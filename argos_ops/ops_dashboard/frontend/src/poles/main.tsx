import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { PolesShell } from "./PolesShell.tsx";
import "../index.css";

// Entrée du shell archi v2 (poles.html). Indépendant de l'app legacy
// (index.html / App.tsx) : les sessions pôle n'éditent que src/poles/**.
const rootElement = document.getElementById("root");
if (!rootElement) {
  throw new Error("#root introuvable dans poles.html");
}

createRoot(rootElement).render(
  <StrictMode>
    <PolesShell />
  </StrictMode>,
);
