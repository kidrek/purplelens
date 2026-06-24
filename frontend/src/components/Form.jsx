import { useEffect } from "react";

export function Modal({ title, onClose, children, footer, error }) {
  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <span className="modal-title">{title}</span>
          <button className="modal-close" onClick={onClose} aria-label="Fermer">
            ×
          </button>
        </div>
        {error && <div className="modal-err">{error}</div>}
        {children}
        {footer && <div className="modal-foot">{footer}</div>}
      </div>
    </div>
  );
}

export function Field({ label, hint, children }) {
  return (
    <div className="field">
      {label && <label className="lbl">{label}</label>}
      {children}
      {hint && <div className="hint">{hint}</div>}
    </div>
  );
}

export function Input({ value, onChange, mono, ...rest }) {
  return (
    <input
      className={`input ${mono ? "mono" : ""}`}
      value={value ?? ""}
      onChange={(e) => onChange(e.target.value)}
      {...rest}
    />
  );
}

export function NumberInput({ value, onChange, ...rest }) {
  return (
    <input
      type="number"
      className="input mono"
      value={value ?? ""}
      onChange={(e) =>
        onChange(e.target.value === "" ? null : Number(e.target.value))
      }
      {...rest}
    />
  );
}

export function Select({ value, onChange, options }) {
  return (
    <select
      className="select"
      value={value}
      onChange={(e) => onChange(e.target.value)}
    >
      {options.map((o) => (
        <option key={o} value={o}>
          {o}
        </option>
      ))}
    </select>
  );
}

export function Textarea({ value, onChange, ...rest }) {
  return (
    <textarea
      className="textarea"
      value={value ?? ""}
      onChange={(e) => onChange(e.target.value)}
      {...rest}
    />
  );
}

export function ChipPicker({ items, selected, onToggle, label }) {
  return (
    <div className="chip-pick">
      {items.map((it) => (
        <span
          key={it.value}
          className={`chip ${selected.includes(it.value) ? "sel" : ""}`}
          onClick={() => onToggle(it.value)}
          title={it.title || ""}
        >
          {it.label}
        </span>
      ))}
    </div>
  );
}

export function ConfirmDialog({ message, onConfirm, onCancel }) {
  return (
    <Modal
      title="Confirmer la suppression"
      onClose={onCancel}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onCancel}>
            Annuler
          </button>
          <button className="btn btn-danger" onClick={onConfirm}>
            Supprimer
          </button>
        </>
      }
    >
      <p className="muted" style={{ fontSize: 14, lineHeight: 1.5 }}>
        {message}
      </p>
    </Modal>
  );
}

export function SegmentedControl({ value, onChange, options }) {
  return (
    <div className="segmented">
      {options.map((o) => (
        <button
          key={o}
          type="button"
          className={`seg ${value === o ? "seg-on" : ""}`}
          onClick={() => onChange(o)}
        >
          {o}
        </button>
      ))}
    </div>
  );
}

export function EmptyState({ title, hint }) {
  return (
    <div className="empty-state">
      <div className="big">{title}</div>
      <div style={{ fontSize: 13 }}>{hint}</div>
    </div>
  );
}
