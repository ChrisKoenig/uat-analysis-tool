/**
 * MSAL Configuration for Azure AD authentication.
 *
 * Configuration is resolved in this order:
 *   1. Runtime config from /config.json  (deployed in Azure - no rebuild needed)
 *   2. Vite env vars VITE_MSAL_*         (local dev via .env)
 *   3. Hard-coded defaults               (fallback)
 */
import { LogLevel } from '@azure/msal-browser';

// -- Defaults (used until loadRuntimeConfig resolves) --
let clientId = import.meta.env.VITE_MSAL_CLIENT_ID || '2e7ef202-d148-4388-be40-651321742402';
let tenantId = import.meta.env.VITE_MSAL_TENANT_ID || '16b3c013-d300-468d-ac64-7eda0820b6d3';
let redirectUri = import.meta.env.VITE_MSAL_REDIRECT_URI || window.location.origin;
let apiBaseUrl = '';  // set from config.json at runtime

/**
 * Load runtime config from /config.json (served from public/).
 * Call this ONCE before creating the MSAL instance.
 */
export async function loadRuntimeConfig() {
  try {
    const resp = await fetch('/config.json');
    if (resp.ok) {
      const cfg = await resp.json();
      if (cfg.msal?.clientId) clientId = cfg.msal.clientId;
      if (cfg.msal?.tenantId) tenantId = cfg.msal.tenantId;
      if (cfg.msal?.redirectUri) redirectUri = cfg.msal.redirectUri;
      if (cfg.api?.baseUrl) apiBaseUrl = cfg.api.baseUrl;
    }
  } catch {
    // config.json not available - fall through to env vars / defaults
  }
  return { clientId, tenantId, redirectUri, apiBaseUrl };
}

/** Build the msalConfig object (call after loadRuntimeConfig). */
export function getMsalConfig() {
  return {
    auth: {
      clientId,
      authority: `https://login.microsoftonline.com/${tenantId}`,
      redirectUri,
      postLogoutRedirectUri: redirectUri,
      navigateToLoginRequestUrl: true,
    },
    cache: {
      cacheLocation: 'localStorage',
      storeAuthStateInCookie: false,
    },
    system: {
      loggerOptions: {
        logLevel: LogLevel.Warning,
        loggerCallback: (level, message) => {
          if (level === LogLevel.Error) console.error('[MSAL]', message);
        },
      },
    },
  };
}

/** Scopes requested during login. */
export const loginRequest = {
  scopes: ['User.Read', 'openid', 'profile', 'email'],
};

/** Scopes for backend API tokens. */
export function getApiTokenRequest() {
  return { scopes: clientId ? [`${clientId}/.default`] : [] };
}

/** Return the runtime API base URL (e.g. 'https://app-triage-api-nonprod.azurewebsites.net'). */
export function getApiBaseUrl() {
  return apiBaseUrl;
}
