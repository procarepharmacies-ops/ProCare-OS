"use client";

// A lightweight, theme-aware modal for dashboard "second-click" detail views.
// Click the backdrop or the ✕ to close. Content is passed as children.
export default function DetailModal({ title, onClose, children }) {
  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.45)",
        display: "grid",
        placeItems: "center",
        zIndex: 1000,
        padding: 16,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="card"
        style={{ maxWidth: 640, width: "100%", maxHeight: "85vh", overflowY: "auto" }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <h3 className="section-title" style={{ margin: 0 }}>{title}</h3>
          <button className="btn icon" onClick={onClose}>✕</button>
        </div>
        {children}
      </div>
    </div>
  );
}
