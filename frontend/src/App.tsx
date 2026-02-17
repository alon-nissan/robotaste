/**
 * App.tsx — The Root Component (Application Router)
 *
 * === WHAT IS THIS? ===
 * This is the top-level component that controls which page to show.
 * It uses React Router to map URLs to page components:
 *   /moderator/setup      → ModeratorSetupPage
 *   /moderator/monitoring  → ModeratorMonitoringPage
 *   /                      → Redirects to /moderator/setup
 *
 * === KEY CONCEPTS ===
 * - BrowserRouter: Enables URL-based routing (like Streamlit's page navigation).
 * - Routes: Container for all route definitions.
 * - Route: Maps a URL path to a component.
 *   `<Route path="/moderator/setup" element={<ModeratorSetupPage />} />`
 *   means: "When the URL is /moderator/setup, render ModeratorSetupPage".
 * - Navigate: Redirects to another URL (like st.rerun() with new params).
 *
 * === DATA FLOW ===
 * App.tsx is the "root" — it renders first, then renders child components.
 * Each page component manages its own state and API calls.
 */

import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import ModeratorSetupPage from './pages/ModeratorSetupPage';
import ModeratorMonitoringPage from './pages/ModeratorMonitoringPage';

function App() {
  return (
    // BrowserRouter wraps the entire app to enable URL routing
    <BrowserRouter>
      <Routes>
        {/* Route: When URL matches path, render the element */}
        <Route path="/moderator/setup" element={<ModeratorSetupPage />} />
        <Route path="/moderator/monitoring" element={<ModeratorMonitoringPage />} />

        {/* Default: redirect root URL to moderator setup */}
        <Route path="/" element={<Navigate to="/moderator/setup" replace />} />

        {/* Catch-all: any unknown URL redirects to setup */}
        <Route path="*" element={<Navigate to="/moderator/setup" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
