/**
 * React Entry Point
 * =================
 *
 * Initializes MSAL (Azure AD auth) and mounts the root <App />.
 *
 * MSAL Browser v4 requires `await initialize()` and
 * `handleRedirectPromise()` to complete BEFORE React renders.
 * Doing this outside the React tree avoids StrictMode
 * double-mount issues that cause an auth redirect loop.
 */

import React from 'react';
import ReactDOM from 'react-dom/client';
import { PublicClientApplication, EventType } from '@azure/msal-browser';
import { loadRuntimeConfig, getMsalConfig } from './auth/authConfig';
import App from './App';
import './index.css';

const AUTH_DISABLED = import.meta.env.VITE_AUTH_DISABLED === 'true';

async function startApp() {
  let msalInstance = null;

  if (!AUTH_DISABLED) {
    // Load /config.json to pick up pre-prod clientId/tenantId/redirectUri
    await loadRuntimeConfig();
    msalInstance = new PublicClientApplication(getMsalConfig());
    await msalInstance.initialize();

    // Process the redirect response BEFORE React mounts so StrictMode
    // double-mount cannot re-trigger handleRedirectPromise().
    const response = await msalInstance.handleRedirectPromise();
    if (response?.account) {
      msalInstance.setActiveAccount(response.account);
    } else {
      // Restore active account from cache (page refresh / new tab)
      const accounts = msalInstance.getAllAccounts();
      if (accounts.length > 0) {
        msalInstance.setActiveAccount(accounts[0]);
      }
    }

    // Keep active account in sync after future login/logout events
    msalInstance.addEventCallback((event) => {
      if (event.eventType === EventType.LOGIN_SUCCESS && event.payload?.account) {
        msalInstance.setActiveAccount(event.payload.account);
      }
      if (event.eventType === EventType.LOGOUT_SUCCESS) {
        msalInstance.setActiveAccount(null);
      }
    });
  }

  ReactDOM.createRoot(document.getElementById('root')).render(
    <React.StrictMode>
      <App msalInstance={msalInstance} />
    </React.StrictMode>
  );
}

startApp();
