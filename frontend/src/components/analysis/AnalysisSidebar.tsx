/**
 * AnalysisSidebar — Navigation sidebar for the Analysis Hub.
 */

import { NavLink } from 'react-router-dom';

const NAV_ITEMS = [
  { to: '/analysis/dashboard', icon: '📊', label: 'Dashboard', description: 'At-a-glance stats' },
  { to: '/analysis/explorer', icon: '🗄️', label: 'Data Explorer', description: 'Browse tables' },
  { to: '/analysis/query', icon: '🔍', label: 'Query Builder', description: 'Visual + SQL editor' },
  { to: '/analysis/sessions', icon: '📋', label: 'Session Manager', description: 'Archive & delete' },
  { to: '/analysis/dose-response', icon: '📈', label: 'Dose-Response', description: 'Curve visualization' },
];

export default function AnalysisSidebar() {
  return (
    <nav className="w-64 shrink-0 border-r border-border bg-surface p-4 flex flex-col">
      <h2 className="text-xs font-semibold uppercase tracking-wider text-text-secondary mb-4 px-1">
        Analysis
      </h2>
      <ul className="space-y-1 flex-1">
        {NAV_ITEMS.map((item) => (
          <li key={item.to}>
            <NavLink
              to={item.to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                  isActive
                    ? 'bg-primary/10 text-primary border-l-2 border-l-primary font-medium'
                    : 'text-text-primary hover:bg-gray-100'
                }`
              }
            >
              <span className="text-base shrink-0">{item.icon}</span>
              <div className="min-w-0">
                <div className="truncate">{item.label}</div>
                <div className="text-xs text-text-secondary truncate">{item.description}</div>
              </div>
            </NavLink>
          </li>
        ))}
      </ul>

      {/* Back link */}
      <div className="pt-4 border-t border-border">
        <NavLink
          to="/"
          className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-text-secondary hover:bg-gray-100 transition-colors"
        >
          <span>←</span>
          <span>Back to Home</span>
        </NavLink>
      </div>
    </nav>
  );
}
