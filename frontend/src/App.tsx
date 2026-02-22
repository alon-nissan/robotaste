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
import LandingPage from './pages/LandingPage';
import ConsentPage from './pages/ConsentPage';
import RegistrationPage from './pages/RegistrationPage';
import InstructionsPage from './pages/InstructionsPage';
import SelectionPage from './pages/SelectionPage';
import QuestionnairePage from './pages/QuestionnairePage';
import RobotPreparingPage from './pages/RobotPreparingPage';
import CompletionPage from './pages/CompletionPage';
import CustomPhasePage from './pages/CustomPhasePage';
import ProtocolManagerPage from './pages/ProtocolManagerPage';
import SubjectAutoJoinPage from './pages/SubjectAutoJoinPage';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Landing */}
        <Route path="/" element={<LandingPage />} />

        {/* Moderator routes */}
        <Route path="/moderator/setup" element={<ModeratorSetupPage />} />
        <Route path="/moderator/monitoring" element={<ModeratorMonitoringPage />} />
        <Route path="/protocols" element={<ProtocolManagerPage />} />

        {/* Subject routes */}
        <Route path="/subject" element={<SubjectAutoJoinPage />} />
        <Route path="/subject/:sessionId/consent" element={<ConsentPage />} />
        <Route path="/subject/:sessionId/register" element={<RegistrationPage />} />
        <Route path="/subject/:sessionId/instructions" element={<InstructionsPage />} />
        <Route path="/subject/:sessionId/select" element={<SelectionPage />} />
        <Route path="/subject/:sessionId/questionnaire" element={<QuestionnairePage />} />
        <Route path="/subject/:sessionId/preparing" element={<RobotPreparingPage />} />
        <Route path="/subject/:sessionId/complete" element={<CompletionPage />} />
        <Route path="/subject/:sessionId/phase/:phaseId" element={<CustomPhasePage />} />

        {/* Catch-all */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
