import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { ErrorBoundary } from "./components/ErrorBoundary";
import "./styles.css";

const rootElement = document.getElementById("root");

// Test-only hook (FLOW-10 regression coverage): ?mockingbird_test_crash=1
// deliberately throws during render instead of mounting the real app, so an
// e2e spec can prove the error boundary recovers from a genuine descendant
// render failure without needing to find or fabricate one elsewhere in the
// app. Inert otherwise -- a stray query param that does nothing.
function TestCrash(): never {
  throw new Error("Deliberate test render failure (FLOW-10 error boundary regression coverage).");
}

if (rootElement) {
  const shouldCrash = new URLSearchParams(window.location.search).has("mockingbird_test_crash");
  createRoot(rootElement).render(
    <StrictMode>
      <ErrorBoundary>{shouldCrash ? <TestCrash /> : <App />}</ErrorBoundary>
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
