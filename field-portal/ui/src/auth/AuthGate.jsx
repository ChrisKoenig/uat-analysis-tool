/**
 * AuthGate — blocks the app behind Microsoft SSO login.
 *
 * Shows a login screen when the user is not authenticated.
 * Provides the user's account info and a getToken() helper
 * via a React context so any component can access auth state.
 */
import React, { useCallback } from 'react';
import {
  AuthenticatedTemplate,
  UnauthenticatedTemplate,
  useMsal,
} from '@azure/msal-react';
import { loginRequest } from './authConfig';
import AuthCtx, { useAuth } from './AuthContext';

export { useAuth };

// ── Login screen shown to unauthenticated users ──
function LoginScreen() {
  const { instance } = useMsal();

  const handleLogin = () => {
    instance.loginRedirect(loginRequest).catch(console.error);
  };

  return (
    <div className="app-shell">
      <header className="app-header">
        <h1>Field Submission Portal</h1>
        <span style={{ fontSize: 13, opacity: 0.8 }}>
          Intelligent Context Analysis System
        </span>
      </header>
      <main className="app-main" style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: '60vh',
      }}>
        <div className="card" style={{ maxWidth: 440, textAlign: 'center' }}>
          <div className="card-header">Sign in Required</div>
          <p style={{ margin: '24px 0 8px', color: '#605e5c' }}>
            Authenticate with your Microsoft account to access the portal.
          </p>
          <button
            className="btn btn-primary"
            onClick={handleLogin}
            style={{ margin: '16px auto', padding: '10px 32px', fontSize: 15 }}
          >
            Sign in with Microsoft
          </button>
        </div>
      </main>
    </div>
  );
}

// ── Main gate wrapper ──
export default function AuthGate({ children }) {
  const { instance, accounts } = useMsal();
  const account = accounts?.[0] ?? null;

  // NOTE: useMsalAuthentication(Silent) was removed — it conflicted with
  // MSAL redirect handling and triggered unexpected re-auth prompts.
  // The explicit login button in LoginScreen handles initial auth.

  /**
   * Get an access token for API calls.
   *
   * Currently returns null — the FastAPI backend does not validate bearer
   * tokens yet, so there is no reason to call acquireTokenSilent().
   * Calling it caused problems: when the cached token expired, MSAL's
   * hidden-iframe renewal could fail (third-party cookies, AAD session
   * timeout, etc.) and invalidate the cached account, which flipped the
   * UI back to the login screen mid-flow.
   *
   * TODO: Once FastAPI bearer-token validation is added, re-enable token
   *       acquisition here.  Use acquireTokenSilent with a try/catch and
   *       fall back to loginRedirect (not popup) on InteractionRequired.
   *       (Feb 2026)
   */
  const getToken = useCallback(async () => {
    return null;
  }, []);

  const handleLogout = useCallback(() => {
    instance.logoutRedirect().catch(console.error);
  }, [instance]);

  return (
    <>
      <UnauthenticatedTemplate>
        <LoginScreen />
      </UnauthenticatedTemplate>

      <AuthenticatedTemplate>
        <AuthCtx.Provider value={{ account, getToken, logout: handleLogout }}>
          {children}
        </AuthCtx.Provider>
      </AuthenticatedTemplate>
    </>
  );
}
