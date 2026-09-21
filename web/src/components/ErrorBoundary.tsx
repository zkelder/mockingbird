import { Component, type ErrorInfo, type ReactNode } from "react";

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
}

/**
 * Top-level render-failure boundary for the whole application (Pre-Release
 * Trust & Correctness Correction v1, FLOW-10). Without this, an unexpected
 * render error anywhere in the component tree turned the entire app into a
 * blank white screen with no recovery path.
 *
 * A class component on purpose -- React has no function-component error
 * boundary API. Logs to the browser console only, never a network call:
 * this product keeps no client-side telemetry/crash-reporting service (see
 * "Privacy and portability" in docs/product-doctrine.md), so the existing,
 * zero-infrastructure diagnostic path is the browser's own dev tools plus
 * the local `logs/mockingbird.log` file already documented elsewhere
 * (README-FIRST.txt) as the place to look when something goes wrong.
 */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error("MockingBird hit an unexpected error and stopped rendering.", error, errorInfo);
  }

  private handleReload = (): void => {
    window.location.reload();
  };

  render(): ReactNode {
    if (!this.state.hasError) {
      return this.props.children;
    }
    return (
      <div className="error-panel app-error-boundary" role="alert">
        <strong>MockingBird ran into a problem and couldn't continue.</strong>
        <span>
          Your reviewed history and evidence are safe -- this is a display problem, not data loss.
        </span>
        <span>
          Reloading usually fixes it. If it keeps happening, check{" "}
          <code>logs/mockingbird.log</code> in MockingBird's local data folder for more detail.
        </span>
        <button className="primary-action" onClick={this.handleReload} type="button">
          Reload MockingBird
        </button>
      </div>
    );
  }
}
