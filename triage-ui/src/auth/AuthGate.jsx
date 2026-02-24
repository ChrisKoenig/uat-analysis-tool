/**
 * AuthGate - blocks the app behind Microsoft SSO login.
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

// -- Login screen shown to unauthenticated users --
function LoginScreen() {
  const { instance } = useMsal();

  const handleLogin = () => {
    instance.loginRedirect(loginRequest).catch(console.error);
  };

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: '100vh',
      backgroundColor: '#f3f2f1',
      fontFamily: "'Segoe UI', -apple-system, sans-serif",
    }}>
      <div style={{
        backgroundColor: 'white',
        borderRadius: 8,
        boxShadow: '0 2px 8px rgba(0,0,0,0.12)',
        padding: '48px 40px',
        maxWidth: 440,
        textAlign: 'center',
      }}>
        <div style={{ fontSize: 40, marginBottom: 16 }}>&#9881;&#65039;</div>
        <h1 style={{ margin: '0 0 8px', fontSize: 22, color: '#323130' }}>
          Triage Management System
        </h1>
        <p style={{ margin: '0 0 24px', color: '#605e5c', fontSize: 14 }}>
          Sign in with your Microsoft account to access the admin dashboard.
        </p>
        <button
          onClick={handleLogin}
          style={{
            backgroundColor: '#0078d4',
            color: 'white',
            border: 'none',
            borderRadius: 4,
            padding: '10px 32px',
            fontSize: 15,
            cursor: 'pointer',
            fontWeight: 600,
          }}
        >
          Sign in with Microsoft
        </button>
      </div>
    </div>
  );
}

// -- Main gate wrapper --
export default function AuthGate({ children }) {
  const { instance, accounts } = useMsal();
  const account = accounts?.[0] ?? null;

  /**
   * Get an access token for API calls.
   * Returns null for now - the FastAPI backend does not validate
   * bearer tokens yet.
   *
   * TODO: Once FastAPI bearer-token validation is added, re-enable
   *       token acquisition here.
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
