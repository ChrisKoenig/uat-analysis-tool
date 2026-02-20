/**
 * Step 7 Loading: Searching for Similar UATs (interstitial)
 *
 * Automatically calls POST /api/field/related-uats/{session_id}.
 * The backend uses AzureDevOpsSearcher to find UATs from the last
 * 180 days with similar titles, sorted by cosine similarity.
 *
 * On completion:
 *   - If matches found → navigates to /related-uats (Step 8)
 *   - If no matches     → skips to /create-uat (Step 9)
 */
import React, { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import ProgressStepper from '../components/ProgressStepper';
import LoadingSpinner from '../components/LoadingSpinner';
import { searchRelatedUATs } from '../api/fieldApi';

export default function SearchingUATsPage() {
  const navigate = useNavigate();
  const { state } = useLocation();
  const sessionId = state?.sessionId;
  const [error, setError] = useState('');

  useEffect(() => {
    if (!sessionId) { navigate('/'); return; }

    let cancelled = false;

    (async () => {
      try {
        const result = await searchRelatedUATs(sessionId);
        if (!cancelled) {
          if (result.related_uats.length === 0) {
            // No related UATs — skip to creation
            navigate('/create-uat', { state: { sessionId } });
          } else {
            navigate('/related-uats', { state: { uatData: result, sessionId } });
          }
        }
      } catch (err) {
        if (!cancelled) setError(err.message);
      }
    })();

    return () => { cancelled = true; };
  }, [sessionId, navigate]);

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
            <button className="btn btn-primary" onClick={() => navigate('/create-uat', { state: { sessionId } })}>
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
