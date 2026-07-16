/**
 * ErrorBoundary — Catches render-time crashes so the whole app doesn't go blank.
 *
 * === WHY THIS EXISTS ===
 * If any component throws during render (e.g. a page reads a field that
 * turned out to be undefined), React unmounts the entire tree by default —
 * the subject sees a blank white page with no indication anything went
 * wrong. Wrapping the app in an ErrorBoundary catches that crash and shows a
 * fallback message instead, so failures are visible instead of silent.
 *
 * === WHY A CLASS COMPONENT ===
 * Error boundaries must be class components — React does not yet provide a
 * hook equivalent of `componentDidCatch` / `getDerivedStateFromError`.
 */

import { Component, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('Unhandled render error caught by ErrorBoundary:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-white flex items-center justify-center p-6">
          <div className="max-w-md w-full p-6 bg-red-50 rounded-xl text-red-700">
            <h2 className="font-semibold mb-2">Something went wrong</h2>
            <p className="text-sm mb-4">
              This page hit an unexpected error and couldn't continue. Please
              refresh, or let the moderator know if this keeps happening.
            </p>
            <button
              onClick={() => window.location.reload()}
              className="px-4 py-1.5 rounded-lg text-sm font-medium bg-red-600 text-white hover:bg-red-700 transition-colors"
            >
              Reload
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
