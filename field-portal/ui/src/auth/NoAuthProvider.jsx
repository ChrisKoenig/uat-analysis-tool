/**
 * NoAuthProvider — bypasses MSAL entirely for container / offline builds.
 *
 * Activate by setting VITE_AUTH_DISABLED=true in .env or at build time.
 * Provides the same AuthCtx shape as AuthGate so the rest of the app
 * (useAuth(), AppShell header, fieldApi token getter) keeps working.
 */
import React, { useCallback } from 'react';
import AuthCtx, { useAuth } from './AuthContext';

export { useAuth };

export default function NoAuthProvider({ children }) {
  const mockAccount = {
    name: 'Local User',
    username: 'local@container',
  };

  const getToken = useCallback(async () => null, []);
  const logout = useCallback(() => {
    console.log('[NoAuth] logout is a no-op in auth-disabled mode');
  }, []);

  return (
    <AuthCtx.Provider value={{ account: mockAccount, getToken, logout }}>
      {children}
    </AuthCtx.Provider>
  );
}
