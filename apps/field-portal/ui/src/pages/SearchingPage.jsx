/**
 * Step 5 Loading: Searching Resources (interstitial)
 *
 * Automatically calls POST /api/field/search/{session_id} on mount.
 * The backend searches Microsoft Learn docs, TFT features (for
 * feature_request category), and returns category-specific guidance.
 *
 * On completion, navigates → /search-results with searchData in state.
 */
import React, { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import ProgressStepper from '../components/ProgressStepper';
import LoadingSpinner from '../components/LoadingSpinner';
import { searchResources } from '../api/fieldApi';

export default function SearchingPage() {
  const navigate = useNavigate();
  const { state } = useLocation();
  const sessionId = state?.sessionId;
  const [error, setError] = useState('');

  useEffect(() => {
    if (!sessionId) { navigate('/'); return; }

    let cancelled = false;

    (async () => {
      try {
        const result = await searchResources(sessionId);
        if (!cancelled) {
          navigate('/search-results', { state: { searchData: result, sessionId } });
        }
      } catch (err) {
        if (!cancelled) setError(err.message);
      }
    })();

    return () => { cancelled = true; };
  }, [sessionId, navigate]);

  return (
    <>
      <ProgressStepper currentStep={5} />
      {error ? (
        <div className="card">
          <div className="alert alert-danger">
            <h3>Search Failed</h3>
            <p>{error}</p>
          </div>
          <button className="btn btn-secondary" onClick={() => navigate('/')}>← Start Over</button>
        </div>
      ) : (
        <LoadingSpinner message="Searching resources, Microsoft Learn, TFT features..." />
      )}
    </>
  );
}
