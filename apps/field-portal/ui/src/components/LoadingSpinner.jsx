/**
 * LoadingSpinner — full page or inline loading state.
 */
import React from 'react';

export default function LoadingSpinner({ message = 'Processing...' }) {
  return (
    <div className="loading-overlay">
      <div className="spinner" />
      <p>{message}</p>
    </div>
  );
}
