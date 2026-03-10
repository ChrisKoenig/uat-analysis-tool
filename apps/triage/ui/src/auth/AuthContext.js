/**
 * Shared Auth Context
 *
 * Single context used by both AuthGate (MSAL) and NoAuthProvider (bypass).
 * Components call useAuth() to access account info, getToken, and logout.
 */
import { createContext, useContext } from 'react';

const AuthCtx = createContext(null);

export function useAuth() {
  return useContext(AuthCtx);
}

export default AuthCtx;
