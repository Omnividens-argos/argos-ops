import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App.tsx";
import { ToastProvider } from "./components/Toast.tsx";
import { UserPrefsProvider } from "./hooks/useUserPrefs.tsx";
import "./index.css";

// Bootstrap React 18+ avec StrictMode + UserPrefs + Toast providers.
// L'ordre importe peu (les deux contexts sont indépendants), mais Toast
// englobe pour que n'importe quel descendant puisse useToast().
const rootElement = document.getElementById("root");
if (!rootElement) {
  throw new Error("#root introuvable dans index.html");
}

createRoot(rootElement).render(
  <StrictMode>
    <UserPrefsProvider>
      <ToastProvider>
        <App />
      </ToastProvider>
    </UserPrefsProvider>
  </StrictMode>,
);
