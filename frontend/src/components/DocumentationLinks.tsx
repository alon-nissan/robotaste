/**
 * DocumentationLinks Component — Download buttons for protocol docs.
 *
 * === WHAT THIS DOES ===
 * Shows two download buttons: User Guide and Schema Reference.
 * Clicking them triggers a file download from the FastAPI backend.
 *
 * === KEY CONCEPT: window.open() ===
 * Instead of using axios (which returns JSON), we use window.open()
 * to navigate the browser directly to the download URL.
 * The browser handles the file download natively (save dialog, etc.).
 */

// This is the API base URL (same as in client.ts)
const API_BASE = 'http://localhost:8000/api';

export default function DocumentationLinks() {
  return (
    <div className="mt-6">
      <h4 className="text-sm font-semibold text-text-primary mb-2">
        Documentation
      </h4>

      {/* flex: horizontal layout, gap-3: spacing between buttons */}
      <div className="flex gap-3">
        {/* User Guide button */}
        <button
          onClick={() => window.open(`${API_BASE}/docs/user-guide`, '_blank')}
          className="flex items-center gap-2 px-4 py-2 text-sm
                     bg-surface text-text-primary rounded-lg
                     border border-border hover:bg-gray-100
                     transition-colors"
        >
          📖 User Guide
        </button>

        {/* Schema Reference button */}
        <button
          onClick={() => window.open(`${API_BASE}/docs/schema`, '_blank')}
          className="flex items-center gap-2 px-4 py-2 text-sm
                     bg-surface text-text-primary rounded-lg
                     border border-border hover:bg-gray-100
                     transition-colors"
        >
          📋 Schema Ref
        </button>
      </div>
    </div>
  );
}
