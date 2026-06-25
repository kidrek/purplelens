import { useEffect, useRef } from "react";

/**
 * Drawer — panneau latéral glissant depuis la droite.
 *
 * Props :
 *   open      {bool}     — visible ou non
 *   onClose   {fn}       — callback fermeture
 *   title     {string}   — titre affiché dans l'en-tête
 *   width     {string}   — largeur CSS (défaut "52vw", min 560px)
 *   children  {ReactNode}
 */
export function Drawer({ open, onClose, title, width = "52vw", children }) {
  const drawerRef = useRef(null);

  // Ferme au clic sur l'overlay
  function onOverlayClick(e) {
    if (e.target === e.currentTarget) onClose();
  }

  // Ferme à Escape
  useEffect(() => {
    if (!open) return;
    function onKey(e) { if (e.key === "Escape") onClose(); }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  // Bloque le scroll body quand ouvert
  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    return () => { document.body.style.overflow = ""; };
  }, [open]);

  if (!open) return null;

  return (
    <div className="drawer-overlay" onClick={onOverlayClick}>
      <div
        ref={drawerRef}
        className="drawer-panel"
        style={{ width, minWidth: 560, maxWidth: "92vw" }}
        role="dialog"
        aria-modal="true"
      >
        <div className="drawer-panel-head">
          <span className="drawer-panel-title">{title}</span>
          <button
            className="drawer-panel-close"
            onClick={onClose}
            aria-label="Fermer"
          >
            <i className="ti ti-x" aria-hidden="true" />
          </button>
        </div>
        <div className="drawer-panel-body">
          {children}
        </div>
      </div>
    </div>
  );
}
