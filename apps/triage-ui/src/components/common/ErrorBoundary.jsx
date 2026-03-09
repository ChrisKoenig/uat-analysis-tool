/**
 * ErrorBoundary — React Error Boundary
 * ======================================
 *
 * Catches unhandled render errors in child components and displays
 * a recoverable fallback UI instead of a white screen.
 *
 * Usage:
 *   <ErrorBoundary>
 *     <ComponentThatMightCrash />
 *   </ErrorBoundary>
 *
 *   <ErrorBoundary fallback={<p>Custom fallback</p>}>
 *     ...
 *   </ErrorBoundary>
 */

import React from 'react';

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('[ErrorBoundary] Caught render error:', error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div style={{
          padding: '2rem',
          margin: '1rem',
          border: '1px solid var(--border-color, #e0e0e0)',
          borderRadius: '8px',
          background: 'var(--surface, #fff)',
          textAlign: 'center',
        }}>
          <h3 style={{ color: 'var(--error, #d32f2f)', marginBottom: '0.5rem' }}>
            Something went wrong
          </h3>
          <p style={{ color: 'var(--text-light, #666)', marginBottom: '1rem' }}>
            {this.state.error?.message || 'An unexpected error occurred while rendering.'}
          </p>
          <button
            onClick={this.handleReset}
            className="btn btn-primary btn-sm"
          >
            Try Again
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
