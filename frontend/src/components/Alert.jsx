import React from 'react';
import PropTypes from 'prop-types';

/**
 * Modular alert/banner for errors and important messages
 * @param {string} message - The main message
 * @param {string} [details] - Optional details
 * @param {string} [type] - 'error', 'success', 'info', 'warning'
 */
function Alert({ message, details, type = 'error' }) {
  const colors = {
    error: { bg: '#fef2f2', border: '#ef4444', text: '#b91c1c' },
    success: { bg: '#ecfdf5', border: '#10b981', text: '#065f46' },
    info: { bg: '#eff6ff', border: '#3b82f6', text: '#1e40af' },
    warning: { bg: '#fef9c3', border: '#f59e0b', text: '#92400e' }
  };
  const style = colors[type] || colors.error;
  return (
    <div style={{
      background: style.bg,
      borderLeft: `4px solid ${style.border}`,
      color: style.text,
      padding: '1rem',
      borderRadius: '0.5rem',
      marginBottom: '1rem',
      boxShadow: '0 1px 3px rgba(0,0,0,0.03)'
    }}>
      <div style={{ fontWeight: 600 }}>{message}</div>
      {details && <div style={{ fontSize: '0.95em', marginTop: '0.25em' }}>{details}</div>}
    </div>
  );
}

Alert.propTypes = {
  message: PropTypes.string.isRequired,
  details: PropTypes.string,
  type: PropTypes.oneOf(['error', 'success', 'info', 'warning'])
};

export default Alert;
