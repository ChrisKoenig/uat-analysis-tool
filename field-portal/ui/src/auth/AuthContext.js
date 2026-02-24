/**
 * Shared Auth Context
 *
 * Single context used by both AuthGate (MSAL) and NoAuthProvider (bypass).
 * Components always call useAuth() from here — no need to know which provider is active.
 */
import { createContext, useContext } from 'react';

const AuthCtx = createContext(null);

export function useAuth() {
  return useContext(AuthCtx);
}

export default AuthCtx;
