/**
 * Step 5 Loading: Searching Resources (interstitial)
 *
 * Automatically calls POST /api/field/search/{session_id} on mount.
 * The backend searches Microsoft Learn docs, TFT features (for
 * feature_request category), and returns category-specific guidance.
 *
 * On completion, navigates → /search-results with searchData in state.
 *
 * Shows an elapsed timer so the user can see the request is still active
 * (search can take 30-120s when embedding rate limits are hit).
 */
import React, { useEffect, useState, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import ProgressStepper from '../components/ProgressStepper';
import LoadingSpinner from '../components/LoadingSpinner';
import { searchResources } from '../api/fieldApi';

const DEFLECT_CATEGORIES = new Set([
  'technical_support', 'cost_billing', 'aoai_capacity',
  'capacity', 'support', 'support_escalation',
]);

const FEATURE_SEARCH_CATEGORIES = new Set([
  'feature_request', 'service_availability',
]);

function getPhaseMessages(category) {
  if (DEFLECT_CATEGORIES.has(category)) {
    return [
      { after: 0,  text: 'Gathering guidance for your request...' },
      { after: 10, text: 'Almost done...' },
      { after: 30, text: 'Still working — this is taking longer than usual...' },
      { after: 60, text: 'Something may be wrong. Try refreshing the page.' },
    ];
  }
  if (FEATURE_SEARCH_CATEGORIES.has(category)) {
    return [
      { after: 0,  text: 'Searching Microsoft Learn resources...' },
      { after: 8,  text: 'Querying TFT feature catalog...' },
      { after: 20, text: 'Computing similarity scores...' },
      { after: 40, text: 'Almost done...' },
      { after: 70, text: 'Still working — this is taking longer than usual...' },
      { after: 120, text: 'Something may be wrong. Try refreshing the page.' },
    ];
  }
  return [
    { after: 0,  text: 'Searching Microsoft Learn resources...' },
    { after: 10, text: 'Almost done...' },
    { after: 30, text: 'Still working — this is taking longer than usual...' },
    { after: 60, text: 'Something may be wrong. Try refreshing the page.' },
  ];
}

export default function SearchingPage() {
  const navigate = useNavigate();
  const { state } = useLocation();
  const sessionId = state?.sessionId;
  const category = state?.category || '';
  const [error, setError] = useState('');
  const [elapsed, setElapsed] = useState(0);
  const [debugLog, setDebugLog] = useState([]);
  const startRef = useRef(Date.now());
  const hasRun = useRef(false);

  const addDebug = (msg) => {
    const ts = ((performance.now()) / 1000).toFixed(1);
    const line = `[${ts}s] ${msg}`;
    console.log(`[SearchingPage] ${line}`);
    setDebugLog(prev => [...prev, line]);
  };

  // Elapsed timer — ticks every second while searching
  useEffect(() => {
    const iv = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startRef.current) / 1000));
    }, 1000);
    return () => clearInterval(iv);
  }, []);

  useEffect(() => {
    addDebug(`MOUNT — sessionId=${sessionId}, category=${category}`);
    if (!sessionId) { addDebug('No sessionId — redirecting to /'); navigate('/'); return; }
    if (hasRun.current) { addDebug('hasRun=true — skipping duplicate'); return; }
    hasRun.current = true;

    // NOTE: Do NOT use a `cancelled` flag — React 18 StrictMode runs
    // effects twice (mount → cleanup → mount).  The cleanup sets
    // cancelled=true, but hasRun.current prevents the second mount
    // from starting a new fetch.  The first fetch's callback must
    // still be allowed to navigate, so we never cancel it.

    (async () => {
      try {
        addDebug('Calling searchResources()...');
        const t0 = performance.now();
        const result = await searchResources(sessionId);
        const ms = (performance.now() - t0).toFixed(0);
        addDebug(`searchResources returned in ${ms}ms — flow_path=${result?.flow_path}, learn_docs=${result?.learn_docs?.length}`);
        const fp = result?.flow_path || 'create_uat';
        if (fp === 'deflect') {
          addDebug(`Navigating to /done (deflect)`);
          navigate('/done', { state: { searchData: result, sessionId } });
        } else {
          addDebug(`Navigating to /search-results (fp=${fp})`);
          navigate('/search-results', { state: { searchData: result, sessionId } });
        }
      } catch (err) {
        const msg = err?.message || String(err);
        addDebug(`ERROR: ${msg}`);
        setError(msg);
      }
    })();

    // No cleanup — the fetch must be allowed to navigate even after
    // StrictMode's synthetic unmount/remount cycle.
  }, [sessionId, navigate]);

  // Pick the latest phase message for the current elapsed time
  const messages = getPhaseMessages(category);
  const phaseMsg = [...messages]
    .reverse()
    .find((p) => elapsed >= p.after)?.text || messages[0].text;

  return (
    <>
      <ProgressStepper currentStep={5} />
      {error ? (
        <div className="card">
          <div className="alert alert-danger">
            <h3>Search Failed</h3>
            <p>{error}</p>
          </div>
          <button className="btn btn-secondary" onClick={() => navigate('/')}>
            &larr; Start Over
          </button>
        </div>
      ) : (
        <div style={{ textAlign: 'center' }}>
          <LoadingSpinner message={phaseMsg} />
          <p style={{ fontSize: 12, color: '#8a8886', marginTop: 8 }}>
            Elapsed: {elapsed}s
          </p>
        </div>
      )}
      {/* Debug panel — visible during development */}
      <div style={{
        position: 'fixed', bottom: 0, left: 0, right: 0,
        maxHeight: '30vh', overflow: 'auto',
        background: '#1e1e1e', color: '#0f0', fontFamily: 'Consolas, monospace',
        fontSize: 11, padding: '6px 10px', zIndex: 99999,
        borderTop: '2px solid #333',
      }}>
        <strong style={{ color: '#ff0' }}>SearchingPage Debug</strong>
        {debugLog.map((line, i) => <div key={i}>{line}</div>)}
      </div>
    </>
  );
}
