/**
 * ConfirmDialog — Modal Confirmation
 * ====================================
 *
 * Simple modal dialog for confirming destructive actions
 * like delete operations.
 *
 * Props:
 *   open       : boolean — whether the dialog is visible
 *   title      : string — dialog title
 *   message    : string — confirmation question
 *   confirmLabel : string — text for the confirm button (default: "Delete")
 *   danger     : boolean — style confirm button as danger (red)
 *   onConfirm  : () => void — called when user confirms
 *   onCancel   : () => void — called when user cancels
 */

import React, { useEffect, useRef } from 'react';
import './ConfirmDialog.css';


export default function ConfirmDialog({
  open,
  title = 'Confirm',
  message,
  confirmLabel = 'Delete',
  danger = true,
  onConfirm,
  onCancel,
}) {
  const dialogRef = useRef(null);

  // Focus trap: auto-focus the cancel button when opening
  useEffect(() => {
    if (open && dialogRef.current) {
      dialogRef.current.focus();
    }
  }, [open]);

  // Close on Escape key
  useEffect(() => {
    if (!open) return;
    const handler = (e) => {
      if (e.key === 'Escape') onCancel?.();
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [open, onCancel]);

  if (!open) return null;

  return (
    <div className="confirm-overlay" onClick={onCancel}>
      <div
        className="confirm-dialog"
        ref={dialogRef}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-title"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 id="confirm-title" className="confirm-title">{title}</h3>
        <p className="confirm-message">{message}</p>
        <div className="confirm-actions">
          <button
            className="btn btn-secondary"
            onClick={onCancel}
          >
            Cancel
          </button>
          <button
            className={`btn ${danger ? 'btn-danger' : 'btn-primary'}`}
            onClick={onConfirm}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
