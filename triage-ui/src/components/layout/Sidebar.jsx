/**
 * Sidebar — Left Navigation Panel
 * =================================
 *
 * Azure portal-style dark sidebar with navigation links.
 * Highlights the active route and collapses on small screens.
 *
 * Features:
 *   - Navigation items with icons
 *   - Active route highlighting
 *   - Divider support for grouping sections
 *   - System health indicator at the bottom
 */

import React, { useEffect, useState } from 'react';
import { NavLink } from 'react-router-dom';
import { NAV_ITEMS } from '../../utils/constants';
import { getHealth } from '../../api/triageApi';
import './Sidebar.css';


export default function Sidebar() {
  const [health, setHealth] = useState(null);

  // Poll health every 30 seconds
  useEffect(() => {
    const check = () => getHealth().then(setHealth).catch(() => null);
    check();
    const interval = setInterval(check, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <aside className="sidebar">
      {/* Brand / title area */}
      <div className="sidebar-brand">
        <span className="sidebar-brand-icon">⚙️</span>
        <div className="sidebar-brand-text">
          <span className="sidebar-brand-title">Triage Admin</span>
          <span className="sidebar-brand-subtitle">Management System</span>
        </div>
      </div>

      {/* Navigation links */}
      <nav className="sidebar-nav" aria-label="Main navigation">
        {NAV_ITEMS.map((item, i) => {
          // Render divider
          if (item.divider) {
            return <hr key={`div-${i}`} className="sidebar-divider" />;
          }

          return (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === '/'}
              className={({ isActive }) =>
                `sidebar-link ${isActive ? 'sidebar-link-active' : ''}`
              }
            >
              <span className="sidebar-link-icon">{item.icon}</span>
              <span className="sidebar-link-label">{item.label}</span>
            </NavLink>
          );
        })}
      </nav>

      {/* Health indicator at bottom */}
      <div className="sidebar-footer">
        <div className={`sidebar-health ${
          health?.status === 'healthy' ? 'healthy' :
          health?.status === 'degraded' ? 'degraded' : 'unhealthy'
        }`}>
          <span className="sidebar-health-dot" />
          <span className="sidebar-health-text">
            {health?.status === 'healthy'
              ? 'API Connected'
              : health?.status === 'degraded'
                ? 'API Degraded'
                : 'API Offline'}
          </span>
        </div>
      </div>
    </aside>
  );
}
