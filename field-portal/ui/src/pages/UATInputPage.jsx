/**
 * Step 6: UAT Input — Opportunity & Milestone IDs
 *
 * Collects optional business identifiers before UAT creation:
 *   - Opportunity ID — links the UAT to an MSX sales opportunity
 *   - Milestone ID   — links to a specific delivery milestone
 *
 * Both fields are recommended but skippable. If the user clicks Continue
 * without entering either, a warning is shown; clicking again skips.
 *
 * POSTs to /api/field/uat-input, then navigates → /searching-uats (Step 7).
 */
import React, { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import ProgressStepper from '../components/ProgressStepper';
import { saveUATInput } from '../api/fieldApi';
import { useWizard } from '../auth/WizardContext';

export default function UATInputPage() {
  const navigate = useNavigate();
  const { state } = useLocation();
  const sessionId = state?.sessionId;
  const { cacheStep } = useWizard();

  const [opportunityId, setOpportunityId] = useState('');
  const [milestoneId, setMilestoneId] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [showWarning, setShowWarning] = useState(false);

  // Cache for backward navigation
  useEffect(() => {
    if (sessionId) cacheStep(6, { sessionId });
  }, [sessionId, cacheStep]);

  if (!sessionId) { navigate('/'); return null; }

  const handleContinue = async () => {
    // Warn if no IDs but allow skip
    if (!opportunityId.trim() && !milestoneId.trim() && !showWarning) {
      setShowWarning(true);
      return;
    }

    setSubmitting(true);
    try {
      await saveUATInput(sessionId, opportunityId.trim(), milestoneId.trim());
      navigate('/searching-uats', { state: { sessionId } });
    } catch (err) {
      console.error(err);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <ProgressStepper currentStep={6} />
      <div className="card">
        <div className="card-header">Opportunity & Milestone IDs</div>

        <div className="alert alert-info">
          Providing Opportunity and Milestone IDs helps link this UAT to MSX. 
          These are recommended but not required.
        </div>

        {showWarning && (
          <div className="alert alert-warning">
            No IDs provided. Click "Continue" again to skip, or enter IDs above.
          </div>
        )}

        <div className="form-group">
          <label htmlFor="oppId">Opportunity ID</label>
          <input
            id="oppId"
            type="text"
            value={opportunityId}
            onChange={(e) => { setOpportunityId(e.target.value); setShowWarning(false); }}
            placeholder="e.g., 12345678"
          />
        </div>

        <div className="form-group">
          <label htmlFor="msId">Milestone ID</label>
          <input
            id="msId"
            type="text"
            value={milestoneId}
            onChange={(e) => { setMilestoneId(e.target.value); setShowWarning(false); }}
            placeholder="e.g., MS-2026-001"
          />
        </div>

        <div className="btn-group">
          <button className="btn btn-primary" onClick={handleContinue} disabled={submitting}>
            {submitting ? 'Saving...' : 'Continue →'}
          </button>
        </div>
      </div>
    </>
  );
}
