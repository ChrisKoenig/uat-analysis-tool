/**
 * Done Page — Deflection exit for categories handled outside UAT flow.
 *
 * Shown when flow_path === "deflect". Displays the category-specific
 * guidance (links, instructions) and gives the user an override button
 * to continue to UAT creation if they still need it.
 */
import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import ProgressStepper from '../components/ProgressStepper';
import { markGuidedOverride } from '../api/fieldApi';
import { useWizard } from '../auth/WizardContext';

const VARIANT_STYLES = {
  danger:  { background: '#fde7e9', border: '1px solid #d13438', color: '#a4262c' },
  warning: { background: '#fff4ce', border: '1px solid #f7c948', color: '#854d0e' },
  info:    { background: '#e8f4fd', border: '1px solid #0078d4', color: '#004578' },
};

export default function DonePage() {
  const navigate = useNavigate();
  const { state } = useLocation();
  const { setFlowPath, cacheStep, resetWizard } = useWizard();
  const sessionId = state?.sessionId;
  const data = state?.searchData;

  if (!data || !sessionId) { navigate('/'); return null; }

  const [overriding, setOverriding] = useState(false);

  const handleOverride = async () => {
    setOverriding(true);
    try {
      await markGuidedOverride(sessionId);
    } catch (err) {
      console.error('Failed to mark guided override:', err);
    }
    setFlowPath('create_uat');
    // Bump maxStep so stepper shows progress into the 9-step flow
    cacheStep(6, { sessionId });
    // Override flag skips "search related UATs" — deflect categories
    // (capacity, support, etc.) won't have meaningful matches.
    navigate('/uat-input', { state: { sessionId, override: true } });
  };

  const { category_guidance, learn_docs = [] } = data;
  const style = VARIANT_STYLES[category_guidance?.variant] || VARIANT_STYLES.info;

  return (
    <>
      <ProgressStepper currentStep={5} />

      {/* Category guidance banner */}
      {category_guidance && (
        <div className="card" style={{ ...style, borderRadius: 8, padding: 20, marginBottom: 20 }}>
          <h2 style={{ margin: '0 0 12px', fontSize: 18 }}>{category_guidance.title}</h2>
          <ul style={{ margin: '0 0 16px', paddingLeft: 20, lineHeight: 1.8 }}>
            {(category_guidance.items || []).map((item, i) => (
              <li key={i}>{item}</li>
            ))}
          </ul>
          {category_guidance.links && Object.keys(category_guidance.links).length > 0 && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
              {Object.entries(category_guidance.links).map(([label, url]) => (
                <a
                  key={label}
                  href={url}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                    display: 'inline-block', background: '#0078d4', color: '#fff',
                    borderRadius: 4, padding: '8px 16px', fontSize: 14,
                    fontWeight: 600, textDecoration: 'none',
                  }}
                >
                  {label} ↗
                </a>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Learn docs if available */}
      {learn_docs.length > 0 && (
        <div className="card">
          <div className="card-header">Helpful Resources</div>
          {learn_docs.slice(0, 5).map((doc, i) => (
            <div key={i} style={{
              padding: '10px 0',
              borderBottom: i < Math.min(learn_docs.length, 5) - 1 ? '1px solid #edebe9' : 'none',
            }}>
              <a href={doc.url} target="_blank" rel="noopener noreferrer"
                 style={{ fontWeight: 600, fontSize: 14 }}>
                {doc.title || doc.url}
              </a>
              {doc.description && (
                <p style={{ margin: '4px 0 0', fontSize: 13, color: '#605e5c' }}>
                  {doc.description}
                </p>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Actions */}
      <div className="btn-group" style={{ marginTop: 24 }}>
        <button
          className="btn btn-primary"
          onClick={() => { resetWizard(); navigate('/'); }}
        >
          Done — Return Home
        </button>
        <button
          className="btn"
          style={{
            background: 'transparent', border: '1px solid #8a8886',
            color: '#323130', cursor: 'pointer',
          }}
          onClick={handleOverride}
          disabled={overriding}
        >
          {overriding ? 'Loading...' : 'I still need to create a UAT →'}
        </button>
      </div>
    </>
  );
}
