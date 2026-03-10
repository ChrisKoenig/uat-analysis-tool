/**
 * Step 7 Loading: Searching for Similar UATs (interstitial)
 *
 * Automatically calls POST /api/field/related-uats/{session_id}.
 * The backend uses AzureDevOpsSearcher to find UATs from the last
 * 180 days with similar titles, sorted by cosine similarity.
 *
 * On completion → always navigates to /related-uats (Step 8)
 * so the user can review results (or see "no matches found").
 */
import React, { useEffect, useState, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import ProgressStepper from '../components/ProgressStepper';
import LoadingSpinner from '../components/LoadingSpinner';
import { searchRelatedUATs } from '../api/fieldApi';

export default function SearchingUATsPage() {
  const navigate = useNavigate();
  const { state } = useLocation();
  const sessionId = state?.sessionId;
  const [error, setError] = useState('');
  const [retryCount, setRetryCount] = useState(0);
  const hasRun = useRef(false);

  useEffect(() => {
    if (!sessionId) { navigate('/'); return; }
    if (hasRun.current) return;
    hasRun.current = true;

    (async () => {
      try {
        const result = await searchRelatedUATs(sessionId);
        if (result.search_error) {
          setError(`Similar UAT search failed: ${result.search_error}`);
        } else {
          navigate('/related-uats', { state: { uatData: result, sessionId } });
        }
      } catch (err) {
        setError(err.message);
      }
    })();
  }, [sessionId, navigate, retryCount]);

  return (
    <>
      <ProgressStepper currentStep={7} />
      {error ? (
        <div className="card">
          <div className="alert alert-danger">
            <h3>UAT Search Failed</h3>
            <p>{error}</p>
          </div>
          <div className="btn-group">
            <button className="btn btn-primary" onClick={() => { setError(''); hasRun.current = false; setRetryCount(c => c + 1); }}>
              ↻ Retry Search
            </button>
            <button className="btn btn-secondary" onClick={() => navigate('/create-uat', { state: { sessionId } })}>
              Skip & Create UAT →
            </button>
            <button className="btn btn-secondary" onClick={() => navigate('/')}>← Start Over</button>
          </div>
        </div>
      ) : (
        <LoadingSpinner message="Searching for similar UATs in Azure DevOps (last 180 days)..." />
      )}
    </>
  );
}
