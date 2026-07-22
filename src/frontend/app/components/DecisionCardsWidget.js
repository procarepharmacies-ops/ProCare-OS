import { useEffect, useState } from "react";
import { api } from "../api";
import { t } from "../i18n";
import Icon from "./icons";

export default function DecisionCardsWidget({ lang }) {
  const L = (k) => t(lang, k);
  const [cards, setCards] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actioningCardId, setActioningCardId] = useState(null);

  // Fetch decision cards on mount
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        setLoading(true);
        const data = await api.decisions();
        if (alive) {
          setCards(data?.cards ?? []);
          setError(null);
        }
      } catch (err) {
        if (alive) {
          setError(err.message);
          setCards([]);
        }
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => { alive = false; };
  }, []);

  async function handleDismiss(cardId) {
    try {
      await api.dismissDecision(cardId);
      setCards((prev) => prev.filter((c) => c.card_id !== cardId));
    } catch (err) {
      alert(`Error dismissing card: ${err.message}`);
    }
  }

  async function handleAction(cardId) {
    try {
      setActioningCardId(cardId);
      await api.actionDecision(cardId);
      setCards((prev) => prev.filter((c) => c.card_id !== cardId));
    } catch (err) {
      alert(`Error actioning card: ${err.message}`);
    } finally {
      setActioningCardId(null);
    }
  }

  const severityStyles = {
    critical: { bg: "var(--danger)", fg: "#fff" },
    warning: { bg: "#f59e0b", fg: "#000" },
    info: { bg: "#3b82f6", fg: "#fff" },
  };

  const severityLabels = {
    critical: L("decision_severity_critical"),
    warning: L("decision_severity_warning"),
    info: L("decision_severity_info"),
  };

  if (loading) {
    return (
      <div className="card" style={{ marginTop: 16 }}>
        <h3 className="section-title">{L("daily_decisions")}</h3>
        <p style={{ color: "var(--fg-muted)", fontSize: 12 }}>{L("loading")}</p>
      </div>
    );
  }

  if (error || !cards) {
    return null; // Fail-soft: don't show card if there's an error
  }

  if (cards.length === 0) {
    return null; // Hide widget if no open decisions
  }

  return (
    <div className="card" style={{ marginTop: 16 }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 12 }}>
        <h3 className="section-title" style={{ margin: 0, flex: 1 }}>
          {L("daily_decisions")}
        </h3>
        <span
          style={{
            background: "var(--fg-muted)",
            color: "var(--bg)",
            padding: "2px 8px",
            borderRadius: 12,
            fontSize: 12,
            fontWeight: 600,
          }}
        >
          {cards.length}
        </span>
      </div>
      <p style={{ color: "var(--fg-muted)", fontSize: 12, marginBottom: 12 }}>
        {L("daily_decisions_subtitle")}
      </p>

      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {cards.map((card) => {
          const severity = card.severity || "info";
          const style = severityStyles[severity] || severityStyles.info;
          const isActioning = actioningCardId === card.card_id;

          return (
            <div
              key={card.card_id}
              style={{
                border: `1px solid ${style.bg}`,
                borderRadius: 8,
                padding: 12,
                background: `${style.bg}11`,
                color: style.fg,
              }}
            >
              <div style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
                <div style={{ flex: 1 }}>
                  <div
                    style={{
                      display: "flex",
                      gap: 8,
                      alignItems: "center",
                      marginBottom: 4,
                    }}
                  >
                    <span
                      style={{
                        background: style.bg,
                        color: style.fg,
                        padding: "2px 8px",
                        borderRadius: 4,
                        fontSize: 11,
                        fontWeight: 600,
                      }}
                    >
                      {severityLabels[severity]}
                    </span>
                    <span
                      style={{
                        fontSize: 11,
                        color: "var(--fg-muted)",
                      }}
                    >
                      {card.card_type}
                    </span>
                  </div>
                  <div style={{ fontWeight: 600, marginBottom: 4, fontSize: 13 }}>
                    {lang === "ar" ? card.title_ar : card.title_en || card.title_ar}
                  </div>
                  <div
                    style={{
                      fontSize: 12,
                      color: "var(--fg-muted)",
                      lineHeight: 1.4,
                    }}
                  >
                    {lang === "ar" ? card.body_ar : card.body_en || card.body_ar}
                  </div>
                </div>
                <div
                  style={{
                    display: "flex",
                    gap: 4,
                    flexShrink: 0,
                  }}
                >
                  <button
                    className="btn"
                    style={{
                      padding: "6px 10px",
                      fontSize: 12,
                      minWidth: 0,
                      background: style.bg,
                      color: style.fg,
                      border: "none",
                      fontWeight: 600,
                    }}
                    onClick={() => handleAction(card.card_id)}
                    disabled={isActioning}
                    title={L("decision_approve")}
                  >
                    {isActioning ? "…" : "✓"}
                  </button>
                  <button
                    className="btn"
                    style={{
                      padding: "6px 10px",
                      fontSize: 12,
                      minWidth: 0,
                      background: "var(--fg-muted)",
                      color: "var(--bg)",
                      border: "none",
                      fontWeight: 600,
                    }}
                    onClick={() => handleDismiss(card.card_id)}
                    title={L("decision_dismiss")}
                  >
                    ✕
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
