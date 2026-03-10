/**
 * AppLayout — Main Application Shell
 * ====================================
 *
 * Blade-style layout with:
 *   - Fixed dark sidebar on the left
 *   - Scrollable content area on the right
 *
 * This mirrors the Azure portal's layout paradigm where
 * navigation stays fixed and content scrolls independently.
 */

import React from 'react';
import Sidebar from './Sidebar';
import DiagnosticsPanel from '../common/DiagnosticsPanel';
import './AppLayout.css';


export default function AppLayout({ children }) {
  return (
    <div className="app-layout">
      <Sidebar />
      <main className="app-content">
        {children}
      </main>
      <DiagnosticsPanel />
    </div>
  );
}
