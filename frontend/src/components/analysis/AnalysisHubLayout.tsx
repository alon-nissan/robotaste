/**
 * AnalysisHubLayout — Shell for the Analysis Hub mini-app.
 * Sidebar on the left, content area on the right (via Outlet).
 */

import { Outlet } from 'react-router-dom';
import AnalysisSidebar from './AnalysisSidebar';
import Logo from '../Logo';

export default function AnalysisHubLayout() {
  return (
    <div className="min-h-screen flex flex-col bg-white">
      {/* Header */}
      <header className="shrink-0 border-b border-border bg-white px-6 py-3 flex items-center gap-4">
        <Logo />
        <div className="border-l border-border pl-4">
          <h1 className="text-lg font-semibold text-text-primary">Analysis Hub</h1>
          <p className="text-xs text-text-secondary">Explore experiment data</p>
        </div>
      </header>

      {/* Body: sidebar + content */}
      <div className="flex flex-1 min-h-0">
        <AnalysisSidebar />
        <div className="flex-1 overflow-y-auto p-8">
          <Outlet />
        </div>
      </div>
    </div>
  );
}
