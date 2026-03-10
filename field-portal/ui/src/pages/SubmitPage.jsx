/**
 * Step 1: Issue Submission
 *
 * Entry point for the 9-step wizard. The user enters:
 *   - Title — short issue summary (required)
 *   - Description / Customer Scenario — detailed context (required)
 *   - Business Impact — revenue/timeline impact (recommended)
 *
 * On submit, POSTs to /api/field/submit which returns a quality score.
 * Form values are cached in WizardContext so the ProgressStepper can
 * navigate back to this page without losing input.
 *
 * After submit, navigates → /quality with qualityData in router state.
 */
import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams, useLocation } from 'react-router-dom';
import ProgressStepper from '../components/ProgressStepper';
import { submitIssue } from '../api/fieldApi';
import { useWizard } from '../auth/WizardContext';

export default function SubmitPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { state: locState } = useLocation();
  const { cacheStep, initSession, resetWizard } = useWizard();

  // Pre-fill from: (1) location.state (stepper back-nav), (2) query params ("Update Input"),
  // or (3) empty
  const [title, setTitle] = useState(
    locState?.title || searchParams.get('title') || ''
  );
  const [description, setDescription] = useState(
    locState?.description || searchParams.get('description') || ''
  );
  const [impact, setImpact] = useState(
    locState?.impact || searchParams.get('impact') || ''
  );
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  // Cache form values for stepper back-navigation (update on every keystroke)
  useEffect(() => {
    cacheStep(1, { title, description, impact });
  }, [title, description, impact, cacheStep]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (!title.trim()) { setError('Title is required.'); return; }
    if (!description.trim()) { setError('Description / Customer Scenario is required.'); return; }

    setSubmitting(true);
    // Reset wizard state from any previous session so the stepper
    // doesn't carry over a stale flowPath (e.g. 'deflect' → 5 steps).
    resetWizard();
    try {
      const result = await submitIssue(title.trim(), description.trim(), impact.trim());
      // Track session in wizard context
      if (result.session_id) initSession(result.session_id);
      // Navigate to quality review with the session data
      navigate('/quality', { state: { qualityData: result } });
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <ProgressStepper currentStep={1} />

      {/* Loading overlay while AI evaluates quality */}
      {submitting && (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 1000,
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          background: 'rgba(255,255,255,0.75)', backdropFilter: 'blur(2px)',
        }}>
          <div style={{
            width: 48, height: 48, border: '4px solid #e0e0e0',
            borderTopColor: '#0078d4', borderRadius: '50%',
            animation: 'spin 0.8s linear infinite',
          }} />
          <p style={{ marginTop: 16, fontSize: '1.05em', color: '#333', fontWeight: 500 }}>
            Evaluating submission quality&hellip;
          </p>
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </div>
      )}

      <div className="card">
        <div className="card-header">Submit an Issue</div>

        {error && <div className="alert alert-danger">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="title">Issue Title *</label>
            <div className="hint">Be specific — include the Azure service or product name</div>
            <input
              id="title"
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g., Azure Route Server capacity request for East US region"
            />
          </div>

          <div className="form-group">
            <label htmlFor="description">Customer Scenario / Description *</label>
            <div className="hint">
              Describe what the customer needs, why, and any technical details.
              Minimum 5 words recommended.
            </div>
            <textarea
              id="description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={6}
              placeholder="Describe the customer scenario, what they need, and any relevant context..."
            />
          </div>

          <div className="form-group">
            <label htmlFor="impact">Business Impact</label>
            <div className="hint">
              Describe the business impact if this issue is not resolved (recommended).
            </div>
            <textarea
              id="impact"
              value={impact}
              onChange={(e) => setImpact(e.target.value)}
              rows={3}
              placeholder="e.g., Customer's production deployment is blocked, affecting $2M deal..."
            />
          </div>

          <div className="btn-group">
            <button type="submit" className="btn btn-primary" disabled={submitting}>
              {submitting ? 'Submitting...' : 'Submit for Analysis'}
            </button>
          </div>
        </form>
      </div>
    </>
  );
}
