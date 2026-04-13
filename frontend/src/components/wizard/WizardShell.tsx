/**
 * WizardShell — Main layout for the protocol creation wizard.
 * Sidebar on the left, step content in the center, navigation at the bottom.
 */

import { type ReactNode } from 'react';
import WizardSidebar from './WizardSidebar';
import WizardNavigation from './WizardNavigation';

interface Props {
  children: ReactNode;
  onSave: () => void;
  saving?: boolean;
}

export default function WizardShell({ children, onSave, saving }: Props) {
  return (
    <div className="min-h-screen flex flex-col bg-white">
      {/* Header */}
      <header className="shrink-0 border-b border-gray-200 bg-white px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold text-gray-900">Create Protocol</h1>
            <p className="text-sm text-gray-500">Build your experiment step by step</p>
          </div>
          <a
            href="/protocols"
            className="text-sm text-gray-500 hover:text-gray-700 transition-colors"
          >
            Cancel
          </a>
        </div>
      </header>

      {/* Body: sidebar + content */}
      <div className="flex flex-1 min-h-0">
        <WizardSidebar />
        <div className="flex-1 flex flex-col min-h-0">
          <div className="flex-1 overflow-y-auto p-8">
            <div className="max-w-3xl mx-auto">
              {children}
            </div>
          </div>
          <WizardNavigation onSave={onSave} saving={saving} />
        </div>
      </div>
    </div>
  );
}
