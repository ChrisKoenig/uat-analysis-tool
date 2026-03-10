/**
 * Field Portal — App Root
 *
 * Wizard-style routing: each route is a step in the 9-step flow.
 * Wrapped in MSAL auth + WizardContext for SSO and stepper navigation.
 */
import React, { lazy, Suspense, useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { PublicClientApplication } from '@azure/msal-browser';
import { MsalProvider } from '@azure/msal-react';
import { loadRuntimeConfig, getMsalConfig } from './auth/authConfig';
import AuthGate from './auth/AuthGate';
import NoAuthProvider from './auth/NoAuthProvider';
import { useAuth } from './auth/AuthContext';
import { WizardProvider } from './auth/WizardContext';

import { setTokenGetter } from './api/fieldApi';
import LoadingSpinner from './components/LoadingSpinner';

// When true, skip MSAL entirely (container / offline builds)
const AUTH_DISABLED = import.meta.env.VITE_AUTH_DISABLED === 'true';

// MSAL instance — created after runtime config loads
let msalInstance = null;

// Lazy-load pages for code splitting
const SubmitPage = lazy(() => import('./pages/SubmitPage'));
const QualityReviewPage = lazy(() => import('./pages/QualityReviewPage'));
const AnalyzingPage = lazy(() => import('./pages/AnalyzingPage'));
const AnalysisPage = lazy(() => import('./pages/AnalysisPage'));
const AnalysisDetailPage = lazy(() => import('./pages/AnalysisDetailPage'));
const SearchingPage = lazy(() => import('./pages/SearchingPage'));
const SearchResultsPage = lazy(() => import('./pages/SearchResultsPage'));
const DonePage = lazy(() => import('./pages/DonePage'));
const UATInputPage = lazy(() => import('./pages/UATInputPage'));
const SearchingUATsPage = lazy(() => import('./pages/SearchingUATsPage'));
const RelatedUATsPage = lazy(() => import('./pages/RelatedUATsPage'));
const CreateUATPage = lazy(() => import('./pages/CreateUATPage'));

/** Authenticated shell — shows user info in header */
function AppShell() {
  const { account, getToken, logout } = useAuth();
  const displayName = account?.name || account?.username || 'User';

  // Wire auth tokens into the API client
  useEffect(() => {
    setTokenGetter(getToken);
  }, [getToken]);

  return (
    <WizardProvider>
      <div className="app-shell">
        {/* Header */}
        <header className="app-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <h1 style={{ margin: 0 }}>Field Submission Portal</h1>
            <span style={{ fontSize: 13, opacity: 0.8 }}>
              Intelligent Context Analysis System
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, fontSize: 13 }}>
            <span style={{ opacity: 0.9 }}>{displayName}</span>
            <button
              onClick={logout}
              style={{
                background: 'rgba(255,255,255,0.15)',
                border: '1px solid rgba(255,255,255,0.3)',
                color: 'white',
                borderRadius: 4,
                padding: '4px 12px',
                cursor: 'pointer',
                fontSize: 12,
              }}
            >
              Sign out
            </button>
          </div>
        </header>

        {/* Main Content */}
        <main className="app-main">
          <Suspense fallback={<LoadingSpinner message="Loading..." />}>
            <Routes>
              {/* Step 1: Submit Issue */}
              <Route path="/" element={<SubmitPage />} />

              {/* Step 2: Quality Review */}
              <Route path="/quality" element={<QualityReviewPage />} />

              {/* Step 3: Analyzing (loading) */}
              <Route path="/analyzing" element={<AnalyzingPage />} />

              {/* Step 3-4: Analysis Results + Correction */}
              <Route path="/analysis" element={<AnalysisPage />} />

              {/* Step 3-4: Detailed Analysis Review */}
              <Route path="/analysis/detail/:sessionId" element={<AnalysisDetailPage />} />

              {/* Step 5: Searching (loading) */}
              <Route path="/searching" element={<SearchingPage />} />

              {/* Step 5: Search Results + Feature Selection */}
              <Route path="/search-results" element={<SearchResultsPage />} />

              {/* Deflect exit — category handled outside UAT flow */}
              <Route path="/done" element={<DonePage />} />

              {/* Step 6: UAT Input (Opportunity / Milestone) */}
              <Route path="/uat-input" element={<UATInputPage />} />

              {/* Step 7: Searching UATs (loading) */}
              <Route path="/searching-uats" element={<SearchingUATsPage />} />

              {/* Step 7-8: Related UATs + Selection */}
              <Route path="/related-uats" element={<RelatedUATsPage />} />

              {/* Step 9: Create UAT (loading + result) */}
              <Route path="/create-uat" element={<CreateUATPage />} />
            </Routes>
          </Suspense>
        </main>

        {/* Footer */}
        <footer style={{
          textAlign: 'center',
          padding: '12px 24px',
          fontSize: 12,
          color: '#a19f9d',
          borderTop: '1px solid #edebe9',
        }}>
          Intelligent Context Analysis System — Field Portal v1.0
        </footer>


      </div>
    </WizardProvider>
  );
}

export default function App() {
  const [ready, setReady] = useState(AUTH_DISABLED || !!msalInstance);

  useEffect(() => {
    if (AUTH_DISABLED || msalInstance) return;

    (async () => {
      // Load /config.json (Azure deployment) or fall back to VITE_ env vars
      await loadRuntimeConfig();
      msalInstance = new PublicClientApplication(getMsalConfig());
      await msalInstance.initialize();
      setReady(true);
    })();
  }, []);

  if (!ready) {
    return <LoadingSpinner message="Initializing authentication..." />;
  }

  // ── Auth-disabled mode (container / offline) ──
  if (AUTH_DISABLED) {
    return (
      <NoAuthProvider>
        <BrowserRouter>
          <AppShell />
        </BrowserRouter>
      </NoAuthProvider>
    );
  }

  // ── Normal MSAL mode ──
  return (
    <MsalProvider instance={msalInstance}>
      <BrowserRouter>
        <AuthGate>
          <AppShell />
        </AuthGate>
      </BrowserRouter>
    </MsalProvider>
  );
}
