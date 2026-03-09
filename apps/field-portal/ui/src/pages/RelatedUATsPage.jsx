/**
 * Steps 7-8: Related UATs — Select Up to 5 to Link
 *
 * Displays UATs found by the similarity search, sorted by match percentage.
 * Each item shows:
 *   - Clickable #id badge (links to ADO), title, similarity bar
 *   - Description preview, state badge, created date, assigned to
 *   - Checkbox for selection (click anywhere on the row)
 *
 * The user can select up to UAT_MAX_SELECTED (5) items to link.
 * On "Create UAT", navigates → /create-uat (Step 9).
 */
import React, { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import ProgressStepper from '../components/ProgressStepper';
import { toggleUAT } from '../api/fieldApi';
import { useWizard } from '../auth/WizardContext';

export default function RelatedUATsPage() {
  const navigate = useNavigate();
  const { state } = useLocation();
  const sessionId = state?.sessionId;
  const data = state?.uatData;
  const { cacheStep } = useWizard();

  const [selectedUATs, setSelectedUATs] = useState([]);

  // Cache for backward navigation (steps 7 & 8 share this route)
  useEffect(() => {
    if (data && sessionId) {
      const cached = { uatData: data, sessionId };
      cacheStep(7, cached);
      cacheStep(8, cached);
    }
  }, [data, sessionId, cacheStep]);

  if (!data || !sessionId) { navigate('/'); return null; }

  const { related_uats = [], total_found } = data;

  const handleToggle = async (uatId) => {
    try {
      const result = await toggleUAT(sessionId, uatId);
      setSelectedUATs(result.selected_uats || []);
    } catch (err) {
      console.error(err);
    }
  };

  const handleContinue = () => {
    navigate('/create-uat', { state: { sessionId } });
  };

  return (
    <>
      <ProgressStepper currentStep={8} />
      <div className="card">
        <div className="card-header">
          Similar UATs Found ({total_found})
        </div>
        <p style={{ fontSize: 13, color: '#605e5c', marginBottom: 16 }}>
          Select related UATs to link (max 5). Sorted by similarity — highest first.
        </p>

        {related_uats.map((uat) => {
          const pct = Math.round((uat.similarity || 0) * 100);
          const barColor = pct >= 80 ? '#107c10' : pct >= 50 ? '#ffaa44' : '#d13438';
          const stateColors = {
            Active: '#0078d4', 'In Progress': '#0078d4', New: '#0078d4',
            Resolved: '#107c10', Closed: '#8a8886', Done: '#107c10',
          };
          const stateBg = stateColors[uat.state] || '#605e5c';

          return (
            <div
              key={uat.id}
              className={`selectable-item${selectedUATs.includes(uat.id) ? ' selected' : ''}`}
              onClick={() => handleToggle(uat.id)}
              style={{ alignItems: 'flex-start' }}
            >
              <input
                type="checkbox"
                checked={selectedUATs.includes(uat.id)}
                readOnly
                style={{ marginTop: 4, cursor: 'pointer', pointerEvents: 'none' }}
              />
              <div style={{ flex: 1 }}>
                {/* Title row with similarity badge */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
                  <div style={{ fontWeight: 600 }}>
                    {uat.url ? (
                      <a
                        href={uat.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={(e) => e.stopPropagation()}
                        style={{
                          display: 'inline-block', background: '#0078d4', borderRadius: 4,
                          padding: '1px 6px', fontSize: 12, fontWeight: 700, marginRight: 8,
                          color: '#fff', textDecoration: 'none'
                        }}
                        title="Open in Azure DevOps"
                      >
                        #{uat.id}
                      </a>
                    ) : (
                      <span style={{
                        display: 'inline-block', background: '#e1dfdd', borderRadius: 4,
                        padding: '1px 6px', fontSize: 12, fontWeight: 700, marginRight: 8, color: '#323130'
                      }}>
                        #{uat.id}
                      </span>
                    )}
                    {uat.title}
                  </div>
                  <span style={{
                    background: barColor, color: '#fff', borderRadius: 4,
                    padding: '2px 10px', fontSize: 12, fontWeight: 700, whiteSpace: 'nowrap'
                  }}>
                    {pct}% match
                  </span>
                </div>

                {/* Similarity bar */}
                <div style={{
                  height: 6, background: '#edebe9', borderRadius: 3,
                  marginTop: 8, marginBottom: 8, overflow: 'hidden'
                }}>
                  <div style={{
                    width: `${pct}%`, height: '100%', background: barColor,
                    borderRadius: 3, transition: 'width 0.4s ease'
                  }} />
                </div>

                {/* Description preview */}
                {uat.description && (
                  <p style={{ fontSize: 12, color: '#605e5c', margin: '4px 0 8px', lineHeight: 1.4 }}>
                    {uat.description.length > 250
                      ? uat.description.slice(0, 250) + '…'
                      : uat.description}
                  </p>
                )}

                {/* Metadata row */}
                <div style={{
                  display: 'flex', flexWrap: 'wrap', alignItems: 'center',
                  gap: 12, fontSize: 12, color: '#605e5c', marginTop: 4
                }}>
                  <span style={{
                    background: stateBg, color: '#fff', borderRadius: 4,
                    padding: '1px 8px', fontWeight: 600, fontSize: 11
                  }}>
                    {uat.state || 'Unknown'}
                  </span>
                  <span>
                    📅 {uat.created_date ? new Date(uat.created_date).toLocaleDateString() : '—'}
                  </span>
                  <span>
                    👤 {uat.assigned_to || 'Unassigned'}
                  </span>
                  {uat.url && (
                    <a
                      href={uat.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{
                        fontSize: 12, color: '#0078d4', fontWeight: 600,
                        textDecoration: 'none', padding: '2px 8px',
                        border: '1px solid #0078d4', borderRadius: 4
                      }}
                      onClick={(e) => e.stopPropagation()}
                    >
                      View in ADO ↗
                    </a>
                  )}
                </div>
              </div>
            </div>
          );
        })}

        <div className="btn-group">
          <button className="btn btn-primary" onClick={handleContinue}>
            {selectedUATs.length > 0
              ? `Create UAT with ${selectedUATs.length} linked →`
              : 'Create UAT →'}
          </button>
        </div>
      </div>
    </>
  );
}
