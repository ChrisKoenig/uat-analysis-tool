/**
 * ProductionConfirmDialog — Two-Step Production Write Confirmation
 * =================================================================
 *
 * B0011: Double-confirmation gate before any production ADO writes.
 * Step 1: "You are about to change production data. Are you sure?"
 * Step 2: "You have selected to update Production data. Are you really really sure?"
 *
 * Will be removed once the team is comfortable with production writes.
 *
 * Props:
 *   open       : boolean — whether the dialog is visible
 *   action     : string — description of action (e.g., "set 3 items to Awaiting Approval")
 *   onConfirm  : () => void — called after BOTH confirmations pass
 *   onCancel   : () => void — called when user bails at either step
 */

import React, { useState, useEffect, useRef } from 'react';
import './ProductionConfirmDialog.css';


export default function ProductionConfirmDialog({ open, action, onConfirm, onCancel }) {
  const [step, setStep] = useState(1);
  const dialogRef = useRef(null);

  // Reset to step 1 whenever dialog opens
  useEffect(() => {
    if (open) {
      setStep(1);
    }
  }, [open]);

  // Auto-focus for a11y
  useEffect(() => {
    if (open && dialogRef.current) {
      dialogRef.current.focus();
    }
  }, [open, step]);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const handler = (e) => {
      if (e.key === 'Escape') onCancel?.();
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [open, onCancel]);

  if (!open) return null;

  const handleYes = () => {
    if (step === 1) {
      setStep(2);
    } else {
      onConfirm?.();
    }
  };

  return (
    <div className="prod-confirm-overlay" onClick={onCancel}>
      <div
        className="prod-confirm-dialog"
        ref={dialogRef}
        tabIndex={-1}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="prod-confirm-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="prod-confirm-icon">⚠️</div>

        {step === 1 ? (
          <>
            <h3 id="prod-confirm-title" className="prod-confirm-title">
              Production Write
            </h3>
            <p className="prod-confirm-message">
              You are about to change production data. Are you sure?
            </p>
            {action && (
              <p className="prod-confirm-action">
                Action: <strong>{action}</strong>
              </p>
            )}
          </>
        ) : (
          <>
            <h3 id="prod-confirm-title" className="prod-confirm-title prod-confirm-title--danger">
              Final Confirmation
            </h3>
            <p className="prod-confirm-message">
              You have selected to update Production data. Are you really really sure?
            </p>
          </>
        )}

        <div className="prod-confirm-step">
          Step {step} of 2
        </div>

        <div className="prod-confirm-actions">
          <button
            className="btn btn-secondary"
            onClick={onCancel}
          >
            No
          </button>
          <button
            className={`btn ${step === 2 ? 'btn-danger' : 'btn-warning'}`}
            onClick={handleYes}
          >
            Yes
          </button>
        </div>
      </div>
    </div>
  );
}
