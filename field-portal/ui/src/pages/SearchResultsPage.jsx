/**
 * Step 5: Search Results
 *
 * Displays three categories of results from POST /api/field/search/{sid}:
 *
 *   1. Microsoft Learn Resources — curated documentation links generated
 *      from detected Azure services and the submission title.
 *   2. Related TFT Features — work items from the production ADO org
 *      (unifiedactiontracker) matched by semantic similarity. Each shows
 *      a similarity bar, state badge, and clickable ADO link. Users can
 *      select features to link (checkboxes). The list is collapsible.
 *   3. Category Guidance — category-specific advice (retirement notices,
 *      capacity guidance) when applicable.
 *
 * Navigates → /uat-input (Step 6) on "Continue".
 */
import React, { useEffect, useState, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import ProgressStepper from '../components/ProgressStepper';
import { toggleFeature } from '../api/fieldApi';
import { useWizard } from '../auth/WizardContext';

export default function SearchResultsPage() {
  const navigate = useNavigate();
  const { state } = useLocation();
  const sessionId = state?.sessionId;
  const data = state?.searchData;
  const { cacheStep } = useWizard();

  const [selectedFeatures, setSelectedFeatures] = useState([]);
  const [showAllDocs, setShowAllDocs] = useState(false);
  const [showAllFeatures, setShowAllFeatures] = useState(false);
  const [toggleError, setToggleError] = useState('');
  const [toggling, setToggling] = useState(null); // feature ID currently being toggled
  const togglingRef = useRef(false);
  const [sessionExpired, setSessionExpired] = useState(false);

  // Cache for backward navigation
  useEffect(() => {
    if (data && sessionId) cacheStep(5, { searchData: data, sessionId });
  }, [data, sessionId, cacheStep]);

  if (!data || !sessionId) { navigate('/'); return null; }

  const {
    learn_docs = [], tft_features = [],
    retirement_info, capacity_guidance,
    category_guidance, flow_path = 'create_uat',
  } = data;

  const handleToggleFeature = async (featureId) => {
    if (togglingRef.current) return; // synchronous guard prevents double-fires
    togglingRef.current = true;
    setToggling(featureId);
    setToggleError('');
    try {
      const result = await toggleFeature(sessionId, featureId);
      setSelectedFeatures(result.selected_features || []);
    } catch (err) {
      console.error('Toggle feature error:', err);
      if (err.message && err.message.includes('404')) {
        setSessionExpired(true);
      } else {
        setToggleError(`Failed to toggle feature #${featureId}: ${err.message}`);
      }
    } finally {
      togglingRef.current = false;
      setToggling(null);
    }
  };

  const handleContinue = () => {
    if (flow_path === 'deflect') {
      navigate('/done', { state: { sessionId, searchData: data } });
    } else {
      navigate('/uat-input', { state: { sessionId } });
    }
  };

  // Learn docs: show top 3 unless expanded
  const visibleDocs = showAllDocs ? learn_docs : learn_docs.slice(0, 3);

  return (
    <>
      <ProgressStepper currentStep={5} />

      {/* Retirement info */}
      {retirement_info && (
        <div className="alert alert-warning">
          <h3>Retirement Notice</h3>
          <p>{typeof retirement_info === 'string' ? retirement_info : JSON.stringify(retirement_info)}</p>
        </div>
      )}

      {/* Capacity guidance */}
      {capacity_guidance && (
        <div className="alert alert-info">
          <h3>Capacity Guidance</h3>
          <p>{typeof capacity_guidance === 'string' ? capacity_guidance : JSON.stringify(capacity_guidance)}</p>
        </div>
      )}

      {/* Microsoft Learn Docs */}
      {learn_docs.length > 0 ? (
        <div className="card">
          <div className="card-header">Microsoft Learn Resources</div>
          {visibleDocs.map((doc, i) => (
            <div key={i} style={{
              padding: '10px 0',
              borderBottom: i < visibleDocs.length - 1 ? '1px solid #edebe9' : 'none'
            }}>
              <a
                href={doc.url}
                target="_blank"
                rel="noopener noreferrer"
                style={{ fontWeight: 600, fontSize: 14 }}
              >
                {doc.title || doc.url}
              </a>
              {doc.description && (
                <p style={{ margin: '4px 0 0', fontSize: 13, color: '#605e5c' }}>
                  {doc.description}
                </p>
              )}
            </div>
          ))}
          {learn_docs.length > 3 && !showAllDocs && (
            <button
              onClick={() => setShowAllDocs(true)}
              style={{
                background: 'none', border: 'none', color: '#0078d4',
                cursor: 'pointer', fontSize: 13, fontWeight: 600,
                padding: '10px 0 0', textDecoration: 'none'
              }}
            >
              Show {learn_docs.length - 3} more resources →
            </button>
          )}
          {showAllDocs && learn_docs.length > 3 && (
            <button
              onClick={() => setShowAllDocs(false)}
              style={{
                background: 'none', border: 'none', color: '#0078d4',
                cursor: 'pointer', fontSize: 13, fontWeight: 600,
                padding: '10px 0 0', textDecoration: 'none'
              }}
            >
              Show less
            </button>
          )}
        </div>
      ) : (
        <div className="card" style={{ color: '#605e5c' }}>
          <div className="card-header">Microsoft Learn Resources</div>
          <p style={{ fontSize: 13, fontStyle: 'italic' }}>
            No Learn articles matched this submission. Relevant documentation will appear here when available.
          </p>
        </div>
      )}

      {/* TFT Features — collapsible frame */}
      {tft_features.length > 0 ? (
        <div className="card" style={{ overflow: 'hidden' }}>
          <div
            className="card-header"
            onClick={() => setShowAllFeatures(!showAllFeatures)}
            style={{ cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center', userSelect: 'none' }}
          >
            <span>Related TFT Features ({Math.min(tft_features.length, 10)})</span>
            <span style={{ fontSize: 18, lineHeight: 1, transition: 'transform 0.2s', transform: showAllFeatures ? 'rotate(180deg)' : 'rotate(0deg)' }}>
              ▾
            </span>
          </div>

          {showAllFeatures && (
            <div style={{ padding: '0 16px 16px' }}>
              <p style={{ fontSize: 13, color: '#605e5c', marginBottom: 16 }}>
                Select features to link to your UAT (optional). Sorted by relevance — highest first.
              </p>

              {sessionExpired && (
                <div style={{
                  padding: '12px 16px', marginBottom: 12, borderRadius: 4,
                  background: '#fff4ce', color: '#854d0e', fontSize: 13, border: '1px solid #fbbf24',
                }}>
                  <strong>Session expired.</strong> The server was restarted and your session was lost.
                  Please go back and re-run the search.
                  <div style={{ marginTop: 8 }}>
                    <button onClick={() => navigate('/')} style={{
                      background: '#0078d4', color: '#fff', border: 'none', borderRadius: 4,
                      padding: '6px 16px', cursor: 'pointer', fontSize: 13, fontWeight: 600,
                    }}>Start Over</button>
                  </div>
                </div>
              )}

              {toggleError && !sessionExpired && (
                <div style={{
                  padding: '8px 12px', marginBottom: 12, borderRadius: 4,
                  background: '#fde7e9', color: '#d13438', fontSize: 13,
                }}>
                  {toggleError}
                </div>
              )}

              {tft_features.slice(0, 10).map((feat) => {
                const pct = Math.round((feat.similarity || 0) * 100);
                const barColor = pct >= 80 ? '#107c10' : pct >= 50 ? '#ffaa44' : '#d13438';
                const stateColors = {
                  Active: '#0078d4', 'In Progress': '#0078d4', New: '#0078d4',
                  'In Review': '#0078d4', 'PG Investigating': '#8764b8',
                  'Not Committed': '#ffaa44', Proposed: '#ffaa44',
                  Resolved: '#107c10', Closed: '#8a8886', Done: '#107c10',
                };
                const stateBg = stateColors[feat.state] || '#605e5c';

                return (
                  <div
                    key={feat.id}
                    className={`selectable-item${selectedFeatures.includes(feat.id) ? ' selected' : ''}`}
                    onClick={() => handleToggleFeature(feat.id)}
                    style={{ alignItems: 'flex-start' }}
                  >
                    <input
                      type="checkbox"
                      checked={selectedFeatures.includes(feat.id)}
                      readOnly
                      style={{ marginTop: 4, cursor: 'pointer', pointerEvents: 'none' }}
                    />
                    <div style={{ flex: 1 }}>
                      {/* Title row with similarity badge */}
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
                        <div style={{ fontWeight: 600 }}>
                          {feat.url ? (
                            <a
                              href={feat.url}
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
                              #{feat.id}
                            </a>
                          ) : (
                            <span style={{
                              display: 'inline-block', background: '#e1dfdd', borderRadius: 4,
                              padding: '1px 6px', fontSize: 12, fontWeight: 700, marginRight: 8, color: '#323130'
                            }}>
                              #{feat.id}
                            </span>
                          )}
                          {feat.title}
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
                      {feat.description && (
                        <p style={{ fontSize: 12, color: '#605e5c', margin: '4px 0 8px', lineHeight: 1.4 }}>
                          {feat.description.length > 250
                            ? feat.description.slice(0, 250) + '…'
                            : feat.description}
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
                          {feat.state || 'Unknown'}
                        </span>
                        {feat.created_date && (
                          <span>
                            📅 {new Date(feat.created_date).toLocaleDateString()}
                          </span>
                        )}
                        {feat.url && (
                          <a
                            href={feat.url}
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
            </div>
          )}
        </div>
      ) : (
        <div className="card" style={{ color: '#605e5c' }}>
          <div className="card-header">Related TFT Features</div>
          <p style={{ fontSize: 13, fontStyle: 'italic' }}>
            {data.search_metadata?.tft_error
              ? `Search failed: ${data.search_metadata.tft_error.slice(0, 120)}`
              : 'No matching TFT Features found.'}
          </p>
        </div>
      )}

      {/* TFT Search Diagnostics — always show when metadata available */}
      {data.search_metadata?.tft_diagnostics && (
        <details style={{ margin: '0 0 16px', fontSize: 12, color: '#605e5c' }}>
          <summary style={{ cursor: 'pointer', fontWeight: 600, padding: '4px 0' }}>
            TFT Search Diagnostics
            {data.search_metadata.tft_diagnostics.error && (
              <span style={{ color: '#d13438', marginLeft: 8, fontWeight: 400 }}>
                — Error: {data.search_metadata.tft_diagnostics.error.slice(0, 100)}
              </span>
            )}
          </summary>
          <div style={{
            background: '#f3f2f1', borderRadius: 4, padding: '10px 14px',
            marginTop: 6, fontFamily: 'Consolas, monospace', lineHeight: 1.7,
          }}>
            <div><strong>Category:</strong> {data.search_metadata.tft_diagnostics.category || '?'}</div>
            <div><strong>Searched:</strong> {data.search_metadata.tft_diagnostics.searched ? 'Yes' : 'No (skipped)'}</div>
            <div><strong>Title used:</strong> {data.search_metadata.tft_diagnostics.title_used || '—'}</div>
            <div><strong>Services detected:</strong> {(data.search_metadata.tft_diagnostics.azure_services || []).join(', ') || 'none'}</div>
            <div><strong>Similarity threshold:</strong> {data.search_metadata.tft_diagnostics.threshold ?? '—'}</div>
            {data.search_metadata.tft_diagnostics.raw_count != null && (
              <div><strong>WIQL matches:</strong> {data.search_metadata.tft_diagnostics.raw_count}</div>
            )}
            {data.search_metadata.tft_diagnostics.returned_count != null && (
              <div><strong>Above threshold:</strong> {data.search_metadata.tft_diagnostics.returned_count}</div>
            )}
            {data.search_metadata.tft_diagnostics.elapsed_ms != null && (
              <div><strong>Elapsed:</strong> {data.search_metadata.tft_diagnostics.elapsed_ms}ms</div>
            )}
            {data.search_metadata.tft_diagnostics.error && (
              <div style={{ color: '#d13438', marginTop: 4 }}><strong>Error:</strong> {data.search_metadata.tft_diagnostics.error}</div>
            )}
          </div>
        </details>
      )}

      <div className="btn-group">
        <button className="btn btn-primary" onClick={handleContinue}>
          {flow_path === 'deflect' ? 'Review Guidance →' : 'Continue →'}
        </button>
      </div>
    </>
  );
}
