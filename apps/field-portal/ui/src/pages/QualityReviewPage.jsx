/**
 * Step 2: Quality Review
 *
 * Displays AI-evaluated quality score (0-100) with four dimension breakdowns:
 *   - Title Clarity, Description Quality, Business Impact, Actionability
 * Each dimension scored 0-25. Falls back to rule-based scoring if AI is offline.
 *
 * User actions:
 *   - "Continue to Analysis" → navigates to /analyzing (Step 3)
 *   - "Update Input"        → navigates back to / with prefilled values
 *   - "Cancel"              → discards and returns to /
 *
 * If score < 50 (QUALITY_BLOCK_THRESHOLD), submission is blocked.
 * If score < 80 (QUALITY_WARN_THRESHOLD), improvement is suggested.
 */
import React, { useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import ProgressStepper from '../components/ProgressStepper';
import ConfidenceBar from '../components/ConfidenceBar';
import { useWizard } from '../auth/WizardContext';

export default function QualityReviewPage() {
  const navigate = useNavigate();
  const { state } = useLocation();
  const { cacheStep, initSession } = useWizard();
  const data = state?.qualityData;

  // Cache step data for backward navigation
  useEffect(() => {
    if (data) {
      cacheStep(2, { qualityData: data });
      if (data.session_id) initSession(data.session_id);
    }
  }, [data, cacheStep, initSession]);

  // If quality data is missing (e.g. after an auth redirect lost state),
  // redirect back to the submit page.
  useEffect(() => {
    if (!data) navigate('/', { replace: true });
  }, [data, navigate]);

  if (!data) return null;

  const {
    session_id, score, blocked, needs_improvement, issues, suggestions,
    garbage_detected, original_input, ai_evaluation, dimensions
  } = data;

  // Helper to get color for a dimension score (0-25)
  const dimColor = (s) => s >= 20 ? '#107c10' : s >= 12 ? '#ca5010' : '#d13438';
  const dimLabel = (s) => s >= 20 ? 'Good' : s >= 12 ? 'Fair' : 'Needs Work';

  const handleProceed = () => {
    navigate('/analyzing', { state: { sessionId: session_id } });
  };

  const handleUpdateInput = () => {
    const params = new URLSearchParams({
      title: original_input.title,
      description: original_input.description,
      impact: original_input.impact || '',
    });
    navigate(`/?${params.toString()}`);
  };

  const handleCancel = () => {
    navigate('/');
  };

  return (
    <>
      <ProgressStepper currentStep={2} />
      <div className="card">
        <div className="card-header">Input Quality Review</div>

        <ConfidenceBar value={score} label="Completeness Score" max={100} />

        {blocked && (
          <div className="alert alert-danger">
            <h3>Submission Blocked</h3>
            <p>Your input does not meet the minimum quality threshold (score: {score}/100). 
            Please update your input with more detail before continuing.</p>
          </div>
        )}

        {!blocked && needs_improvement && (
          <div className="alert alert-warning">
            <h3>Improvement Suggested</h3>
            <p>Your input could benefit from additional detail (score: {score}/100). 
            You may continue, but adding more context will improve analysis accuracy.</p>
          </div>
        )}

        {!blocked && !needs_improvement && (
          <div className="alert alert-success">
            <h3>Good Quality Input</h3>
            <p>Your input meets quality standards (score: {score}/100). Ready for analysis.</p>
          </div>
        )}

        {garbage_detected && (
          <div className="alert alert-danger">
            <strong>Invalid input detected.</strong> Please provide meaningful content.
          </div>
        )}

        {/* AI Dimension Breakdown */}
        {dimensions && (
          <div style={{ marginTop: 16 }}>
            <h3>Quality Breakdown {ai_evaluation && <span style={{ fontSize: '0.75em', color: '#666', fontWeight: 'normal' }}>(AI-evaluated)</span>}</h3>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginTop: 8 }}>
              {[
                { key: 'title_clarity', label: 'Title Clarity' },
                { key: 'description_quality', label: 'Description Quality' },
                { key: 'business_impact', label: 'Business Impact' },
                { key: 'actionability', label: 'Actionability' },
              ].map(({ key, label }) => {
                const dim = dimensions[key] || {};
                const s = dim.score ?? 0;
                return (
                  <div key={key} style={{ padding: 10, background: '#f9f9f9', borderRadius: 6, border: `1px solid ${dimColor(s)}22` }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                      <strong style={{ fontSize: '0.9em' }}>{label}</strong>
                      <span style={{ color: dimColor(s), fontWeight: 'bold', fontSize: '0.9em' }}>{s}/25 — {dimLabel(s)}</span>
                    </div>
                    <div style={{ height: 6, background: '#e0e0e0', borderRadius: 3 }}>
                      <div style={{ height: '100%', width: `${(s / 25) * 100}%`, background: dimColor(s), borderRadius: 3, transition: 'width 0.4s' }} />
                    </div>
                    {dim.reason && <p style={{ margin: '6px 0 0', fontSize: '0.82em', color: '#555' }}>{dim.reason}</p>}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Issues Found — only show when AI dimensions are NOT available (rules fallback) */}
        {!dimensions && issues.length > 0 && (
          <div style={{ marginTop: 16 }}>
            <h3>Issues Found</h3>
            <ul>
              {issues.map((issue, i) => (
                <li key={i}>
                  <strong>{issue.field}:</strong> {issue.message}
                </li>
              ))}
            </ul>
          </div>
        )}

        {suggestions.length > 0 && (
          <div style={{ marginTop: 16 }}>
            <h3>Suggestions</h3>
            <ul>
              {suggestions.map((s, i) => <li key={i}>{s}</li>)}
            </ul>
          </div>
        )}

        <div style={{ marginTop: 16, padding: 12, background: '#f3f2f1', borderRadius: 4 }}>
          <h3>Your Input</h3>
          <p><strong>Title:</strong> {original_input.title}</p>
          <p><strong>Description:</strong> {original_input.description}</p>
          {original_input.impact && <p><strong>Impact:</strong> {original_input.impact}</p>}
        </div>

        <div className="btn-group">
          <button className="btn btn-secondary" onClick={handleUpdateInput}>
            ← Update Input
          </button>
          <button className="btn btn-primary" onClick={handleProceed} disabled={blocked}>
            Continue to Analysis →
          </button>
          <button className="btn btn-secondary" onClick={handleCancel}>
            Cancel
          </button>
        </div>
      </div>
    </>
  );
}
