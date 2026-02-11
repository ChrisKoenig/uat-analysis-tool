/**
 * React Entry Point
 * =================
 *
 * Mounts the root <App /> component into the DOM.
 * Wraps with StrictMode for development-time checks.
 */

import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
