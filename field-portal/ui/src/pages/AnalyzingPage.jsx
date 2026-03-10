/**
 * Step 3: Analyzing (loading interstitial)
 *
 * Automatically calls POST /api/field/analyze/{session_id} on mount.
 * The backend runs HybridContextAnalyzer (LLM + pattern matching + vector
 * search + corrections history) to classify the issue's category, intent,
 * business impact, and technical complexity.
 *
 * While waiting, shows a LoadingSpinner. On completion, navigates to
 * /analysis with the full analysisData in router state.
 */
import React, { useEffect, useRef, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import ProgressStepper from '../components/ProgressStepper';
import LoadingSpinner from '../components/LoadingSpinner';
import { analyzeContext } from '../api/fieldApi';
import { useWizard } from '../auth/WizardContext';

export default function AnalyzingPage() {
  const navigate = useNavigate();
  const { state } = useLocation();
  const sessionId = state?.sessionId;
  const [error, setError] = useState('');
  const { initSession } = useWizard();
  const hasRun = useRef(false);

  useEffect(() => {
    if (sessionId) initSession(sessionId);
  }, [sessionId, initSession]);

  useEffect(() => {
    if (!sessionId) {
      navigate('/');
      return;
    }
    if (hasRun.current) return;
    hasRun.current = true;

    (async () => {
      try {
        const result = await analyzeContext(sessionId);
        navigate('/analysis', { state: { analysisData: result, sessionId } });
      } catch (err) {
        setError(err.message);
      }
    })();
  }, [sessionId, navigate]);

  return (
    <>
      <ProgressStepper currentStep={3} />
      {error ? (
        <div className="card">
          <div className="alert alert-danger">
            <h3>Analysis Failed</h3>
            <p>{error}</p>
          </div>
          <button className="btn btn-secondary" onClick={() => navigate('/')}>
            ← Start Over
          </button>
        </div>
      ) : (
        <LoadingSpinner message="Running AI context analysis... This may take 10-15 seconds." />
      )}
    </>
  );
}
