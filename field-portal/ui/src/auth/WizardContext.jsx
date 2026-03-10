/**
 * WizardContext — tracks session state across the 9-step flow.
 *
 * Stores:
 *  - sessionId (set once after Step 1)
 *  - maxStepReached (highest step the user has visited)
 *  - stepCache (location.state data per step, for backward navigation)
 *  - navigateToStep(n) — rebuilds location state & navigates
 *
 * Each interactive page calls `cacheStep(step, stateData)` on mount so
 * the stepper can navigate backward without re-fetching.
 */
import React, { createContext, useCallback, useContext, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';

// Maps stepper step number → the route to navigate to.
// Loading pages (analyzing, searching, searching-uats) are skipped;
// we go straight to their result page.
const STEP_ROUTES = {
  1: '/',
  2: '/quality',
  3: '/analysis',     // skip /analyzing
  4: '/analysis',     // same route — correction mode
  5: '/search-results', // skip /searching
  6: '/uat-input',
  7: '/related-uats',  // skip /searching-uats
  8: '/related-uats',  // same route — selection mode
  9: '/create-uat',
};

const WizardCtx = createContext(null);

export function WizardProvider({ children }) {
  const navigate = useNavigate();
  const [sessionId, setSessionId] = useState(null);
  const [maxStep, setMaxStep] = useState(1);
  const [flowPath, setFlowPath] = useState(null);

  // Cache is keyed by step number → the location.state object for that page.
  const cacheRef = useRef({});

  /** Mark a step as reached and cache its location state data. */
  const cacheStep = useCallback((step, stateData) => {
    cacheRef.current[step] = stateData;
    setMaxStep(prev => Math.max(prev, step));
  }, []);

  /** Store the sessionId for the current flow. */
  const initSession = useCallback((id) => {
    setSessionId(id);
  }, []);

  /** Navigate to a previously-visited step using cached state. */
  const navigateToStep = useCallback((step) => {
    let route = STEP_ROUTES[step];
    // Deflect flow: step 5 is the Done/Guidance page
    if (flowPath === 'deflect' && step === 5) route = '/done';
    if (!route) return;

    // Build the best location.state we can.
    // Fall back: for steps that share a route (3↔4, 7↔8), try the partner cache.
    let state = cacheRef.current[step];
    if (!state) {
      // Try the "partner" step that shares the same route
      const partner = { 3: 4, 4: 3, 7: 8, 8: 7 }[step];
      if (partner) state = cacheRef.current[partner];
    }
    // For steps that only need sessionId, synthesize minimal state
    if (!state && sessionId) {
      state = { sessionId };
    }

    navigate(route, { state: state || {} });
  }, [navigate, sessionId, flowPath]);

  /** Reset wizard (start over). */
  const resetWizard = useCallback(() => {
    setSessionId(null);
    setMaxStep(1);
    setFlowPath(null);
    cacheRef.current = {};
  }, []);

  return (
    <WizardCtx.Provider value={{
      sessionId,
      initSession,
      maxStep,
      flowPath,
      setFlowPath,
      cacheStep,
      navigateToStep,
      resetWizard,
    }}>
      {children}
    </WizardCtx.Provider>
  );
}

/** Hook to access wizard context. */
export function useWizard() {
  const ctx = useContext(WizardCtx);
  if (!ctx) throw new Error('useWizard must be inside <WizardProvider>');
  return ctx;
}
