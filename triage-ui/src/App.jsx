/**
 * App — Root Component
 * =====================
 *
 * Sets up React Router and the blade-style layout shell.
 * All page components are lazily loaded for code splitting.
 *
 * Routes:
 *   /            → Dashboard (system overview)
 *   /evaluate    → Evaluate triage queue
 *   /rules       → Rules CRUD
 *   /actions     → Actions CRUD
 *   /triggers    → Triggers CRUD
 *   /routes      → Routes CRUD
 *   /validation  → Validation warnings
 *   /audit       → Audit log
 */

import React, { Suspense, lazy, useState, useCallback } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import AppLayout from './components/layout/AppLayout';

// ---------------------------------------------------------------------------
// Lazy-loaded page components (code-split per route)
// ---------------------------------------------------------------------------
const Dashboard       = lazy(() => import('./pages/Dashboard'));
const EvaluatePage    = lazy(() => import('./pages/EvaluatePage'));
const QueuePage       = lazy(() => import('./pages/QueuePage'));
const RulesPage       = lazy(() => import('./pages/RulesPage'));
const ActionsPage     = lazy(() => import('./pages/ActionsPage'));
const TriggersPage    = lazy(() => import('./pages/TriggersPage'));
const RoutesPage      = lazy(() => import('./pages/RoutesPage'));
const ValidationPage  = lazy(() => import('./pages/ValidationPage'));
const AuditPage       = lazy(() => import('./pages/AuditPage'));
const EvalHistoryPage = lazy(() => import('./pages/EvalHistoryPage'));


// ---------------------------------------------------------------------------
// Loading fallback shown while page chunks load
// ---------------------------------------------------------------------------
function PageLoader() {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      height: '200px',
      color: 'var(--text-light)',
      fontSize: 'var(--font-size-lg)',
    }}>
      Loading…
    </div>
  );
}


// ---------------------------------------------------------------------------
// Toast notification system (shared via props)
// ---------------------------------------------------------------------------

/**
 * Custom hook for toast notifications.
 * Returns [toasts, addToast] where addToast accepts (message, type).
 */
function useToasts() {
  const [toasts, setToasts] = useState([]);

  const addToast = useCallback((message, type = 'success') => {
    const id = Date.now();
    setToasts((prev) => [...prev, { id, message, type }]);

    // Auto-dismiss after 4 seconds
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4000);
  }, []);

  return [toasts, addToast];
}


// ---------------------------------------------------------------------------
// App Component
// ---------------------------------------------------------------------------

export default function App() {
  const [toasts, addToast] = useToasts();

  return (
    <BrowserRouter>
      <AppLayout>
        {/* Toast notifications */}
        {toasts.length > 0 && (
          <div className="toast-container">
            {toasts.map((t) => (
              <div key={t.id} className={`toast toast-${t.type}`}>
                {t.message}
              </div>
            ))}
          </div>
        )}

        {/* Page routes */}
        <Suspense fallback={<PageLoader />}>
          <Routes>
            <Route path="/"           element={<Dashboard addToast={addToast} />} />
            <Route path="/queue"      element={<QueuePage addToast={addToast} />} />
            <Route path="/evaluate"   element={<EvaluatePage addToast={addToast} />} />
            <Route path="/rules"      element={<RulesPage addToast={addToast} />} />
            <Route path="/triggers"   element={<TriggersPage addToast={addToast} />} />
            <Route path="/routes"     element={<RoutesPage addToast={addToast} />} />
            <Route path="/actions"    element={<ActionsPage addToast={addToast} />} />
            <Route path="/validation" element={<ValidationPage addToast={addToast} />} />
            <Route path="/audit"      element={<AuditPage addToast={addToast} />} />
            <Route path="/history"    element={<EvalHistoryPage addToast={addToast} />} />
          </Routes>
        </Suspense>
      </AppLayout>
    </BrowserRouter>
  );
}
