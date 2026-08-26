import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles.css";

const rootElement = document.getElementById("root");

if (rootElement) {
  createRoot(rootElement).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
}

// Mobile & Remote Experience v1 -- bounded, safe static-shell caching only;
// see web/public/sw.js's own header comment for exactly what this does and
// does not do (never intercepts /api/, /health, or navigation requests).
// Production builds only: Vite's dev server serves unhashed /src/* module
// URLs the worker's own /assets/-only match never applies to anyway, so
// registering it there would add real-world risk (a stale worker surviving
// across dev sessions) for zero benefit.
if (import.meta.env.PROD && "serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    void navigator.serviceWorker.register("/sw.js");
  });
}
