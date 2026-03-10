/**
 * Step 9: Create UAT — Loading + Success Result Page
 *
 * Automatically calls POST /api/field/create-uat on mount. The backend
 * creates a work item in the test ADO org (unifiedactiontrackertest)
 * with all accumulated context: title, description, impact, analysis,
 * selected TFT features, selected related UATs, and opportunity/milestone IDs.
 *
 * On success, displays:
 *   - Work Item ID (clickable link to ADO)
 *   - State, Assigned To, Title
 *   - Linked TFT Features (as "#id — title" links)
 *   - Linked Related UATs  (as "#id — title" links)
 *
 * Actions:
 *   - "Submit Another Issue" → resetWizard() + navigate to /
 *   - "View in Azure DevOps" → opens ADO work item in new tab
 *   - "Done"                 → resetWizard() + navigate to /
 */
import React, { useEffect, useState, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import ProgressStepper from '../components/ProgressStepper';
import LoadingSpinner from '../components/LoadingSpinner';
import { createUAT } from '../api/fieldApi';
import { useWizard } from '../auth/WizardContext';

export default function CreateUATPage() {
  const navigate = useNavigate();
  const { state } = useLocation();
  const sessionId = state?.sessionId;
  const { cacheStep, resetWizard } = useWizard();

  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const hasRun = useRef(false);

  // Cache for wizard tracking
  useEffect(() => {
    if (sessionId) cacheStep(9, { sessionId });
  }, [sessionId, cacheStep]);

  useEffect(() => {
    if (!sessionId) { navigate('/'); return; }
    if (hasRun.current) return;
    hasRun.current = true;

    (async () => {
      try {
        const data = await createUAT(sessionId);
        setResult(data);
      } catch (err) {
        setError(err.message);
      }
    })();
  }, [sessionId, navigate]);

  if (!sessionId) return null;

  // Loading state
  if (!result && !error) {
    return (
      <>
        <ProgressStepper currentStep={9} />
        <LoadingSpinner message="Creating UAT work item in Azure DevOps..." />
      </>
    );
  }

  // Error state
  if (error) {
    return (
      <>
        <ProgressStepper currentStep={9} />
        <div className="card">
          <div className="alert alert-danger">
            <h3>UAT Creation Failed</h3>
            <p>{error}</p>
          </div>
          <button className="btn btn-secondary" onClick={() => { resetWizard(); navigate('/'); }}>
            ← Start Over
          </button>
        </div>
      </>
    );
  }

  // Success state
  return (
    <>
      <ProgressStepper currentStep={9} />
      <div className="card">
        <div className="alert alert-success">
          <h3>UAT Created Successfully!</h3>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
          <div>
            <strong>Work Item ID:</strong>
            <div style={{ fontSize: 18, fontWeight: 600 }}>
              {result.work_item_url ? (
                <a href={result.work_item_url} target="_blank" rel="noopener noreferrer">
                  {result.work_item_id} ↗
                </a>
              ) : (
                result.work_item_id
              )}
            </div>
          </div>
          <div>
            <strong>State:</strong>
            <div>{result.work_item_state}</div>
          </div>
          <div>
            <strong>Assigned To:</strong>
            <div>{result.assigned_to || '—'}</div>
          </div>
          <div>
            <strong>Title:</strong>
            <div>{result.work_item_title}</div>
          </div>
        </div>

        {(result.opportunity_id || result.milestone_id) && (
          <div style={{ marginBottom: 16 }}>
            {result.opportunity_id && <p><strong>Opportunity ID:</strong> {result.opportunity_id}</p>}
            {result.milestone_id && <p><strong>Milestone ID:</strong> {result.milestone_id}</p>}
          </div>
        )}

        {result.selected_features?.length > 0 && (
          <div style={{ marginBottom: 16 }}>
            <h3>Linked TFT Features</h3>
            <ul>
              {result.selected_features.map((f) => (
                <li key={f.id}>
                  {f.url ? (
                    <a href={f.url} target="_blank" rel="noopener noreferrer">
                      #{f.id} — {f.title}
                    </a>
                  ) : (
                    `#${f.id} — ${f.title}`
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}

        {result.selected_uats?.length > 0 && (
          <div style={{ marginBottom: 16 }}>
            <h3>Linked Related UATs</h3>
            <ul>
              {result.selected_uats.map((u) => (
                <li key={u.id || u}>
                  {u.url ? (
                    <a href={u.url} target="_blank" rel="noopener noreferrer">
                      #{u.id} — {u.title}
                    </a>
                  ) : (
                    typeof u === 'object' ? `#${u.id} — ${u.title}` : u
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="btn-group">
          <button className="btn btn-primary" onClick={() => { resetWizard(); navigate('/'); }}>
            Submit Another Issue
          </button>
          {result.work_item_url && (
            <a href={result.work_item_url} target="_blank" rel="noopener noreferrer" className="btn btn-secondary">
              View in Azure DevOps ↗
            </a>
          )}
          <button className="btn btn-secondary" onClick={() => { resetWizard(); navigate('/'); }}>
            Done
          </button>
        </div>
      </div>
    </>
  );
}
