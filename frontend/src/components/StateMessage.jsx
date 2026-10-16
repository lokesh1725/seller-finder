export function Spinner({ label = "Loading..." }) {
  return (
    <div className="state state-loading" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}

export function StateMessage({ variant = "info", title, message, action }) {
  return (
    <div className={`state state-${variant}`} role={variant === "error" ? "alert" : "status"}>
      {title ? <strong className="state-title">{title}</strong> : null}
      {message ? <p className="state-message">{message}</p> : null}
      {action || null}
    </div>
  );
}
