/**
 * ProgressStepper — shows which step the user is on (1 of 9).
 *
 * Clickable: completed steps (and the current step) can be clicked
 * to navigate backward through the wizard. Uses WizardContext.
 */
import React from 'react';
import { useWizard } from '../auth/WizardContext';

const STEPS = [
  { num: 1, label: 'Submit' },
  { num: 2, label: 'Quality' },
  { num: 3, label: 'Analysis' },
  { num: 4, label: 'Review' },
  { num: 5, label: 'Search' },
  { num: 6, label: 'IDs' },
  { num: 7, label: 'Related' },
  { num: 8, label: 'Select' },
  { num: 9, label: 'Created' },
];

export default function ProgressStepper({ currentStep }) {
  const { maxStep, navigateToStep } = useWizard();

  return (
    <div className="stepper">
      {STEPS.map((s, i) => {
        const isActive = s.num === currentStep;
        const isCompleted = s.num < currentStep;
        const isClickable = s.num <= maxStep && s.num !== currentStep;

        let cls = 'step';
        if (isActive) cls += ' active';
        else if (isCompleted) cls += ' completed';
        if (isClickable) cls += ' clickable';

        const handleClick = () => {
          if (isClickable) navigateToStep(s.num);
        };

        return (
          <React.Fragment key={s.num}>
            {i > 0 && (
              <div className={`step-connector${isCompleted ? ' completed' : ''}`} />
            )}
            <div
              className={cls}
              onClick={handleClick}
              onKeyDown={(e) => { if (e.key === 'Enter' && isClickable) handleClick(); }}
              role={isClickable ? 'button' : undefined}
              tabIndex={isClickable ? 0 : undefined}
              title={isClickable ? `Go back to ${s.label}` : undefined}
            >
              <span className="step-number">
                {isCompleted ? '✓' : s.num}
              </span>
              <span className="step-label">{s.label}</span>
            </div>
          </React.Fragment>
        );
      })}
    </div>
  );
}
