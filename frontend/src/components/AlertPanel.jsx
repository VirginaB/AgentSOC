import { useEffect, useState } from "react";
import { getSimilar, sendFeedback } from "../api/client";
import SeverityBadge from "./SeverityBadge";
import { X, Shield, AlertTriangle, Link, ThumbsUp, ThumbsDown } from "lucide-react";

export default function AlertPanel({ alert, onClose }) {
  const [similar, setSimilar]   = useState([]);
  const [feedback, setFeedback] = useState(alert?.feedback || null);

  useEffect(() => {
    if (!alert) return;
    setFeedback(alert.feedback || null);
    setSimilar([]);
    getSimilar(alert.id)
      .then(r => setSimilar(r.data.similar || []))
      .catch(() => {});
  }, [alert?.id]);

  const handleFeedback = async (type) => {
    try {
      await sendFeedback(alert.id, type);
      setFeedback(type);
    } catch (_) {}
  };

  if (!alert) return null;

  const scoreColor =
    alert.risk_score >= 81 ? "#dc2626"
    : alert.risk_score >= 61 ? "#ea580c"
    : alert.risk_score >= 31 ? "#ca8a04"
    : "#16a34a";

  return (
    <div style={{
      width: 420, flexShrink: 0, background: "var(--card)",
      border: "0.5px solid var(--border)", borderRadius: 12,
      display: "flex", flexDirection: "column", overflow: "hidden",
      maxHeight: "100%",
    }}>
      {/* Header */}
      <div style={{ padding: "14px 18px", borderBottom: "0.5px solid var(--border)",
        display: "flex", alignItems: "center", gap: 10 }}>
        <Shield size={16} color="var(--accent)" />
        <span style={{ flex: 1, fontWeight: 500, fontSize: 14, color: "var(--text)" }}>
          Alert #{alert.id}
        </span>
        <SeverityBadge tier={alert.risk_tier} size="lg" />
        <button onClick={onClose} style={{ background: "none", border: "none",
          cursor: "pointer", padding: 4, borderRadius: 6, color: "var(--muted)",
          display: "flex", alignItems: "center" }}>
          <X size={16} />
        </button>
      </div>

      <div style={{ flex: 1, overflowY: "auto", padding: "16px 18px",
        display: "flex", flexDirection: "column", gap: 18 }}>

        {/* Risk score gauge */}
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: 48, fontWeight: 700, color: scoreColor,
            lineHeight: 1 }}>
            {alert.risk_score?.toFixed(0)}
          </div>
          <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 2 }}>
            risk score / 100
          </div>
          <div style={{ margin: "10px 0 0", height: 6, background: "var(--border)",
            borderRadius: 99, overflow: "hidden" }}>
            <div style={{ height: "100%", width: `${alert.risk_score}%`,
              background: scoreColor, borderRadius: 99,
              transition: "width 0.6s ease" }} />
          </div>
        </div>

        {/* Raw log */}
        <Section title="Raw log">
          <code style={{ fontSize: 12, lineHeight: 1.6, display: "block",
            background: "var(--surface)", padding: "10px 12px", borderRadius: 8,
            color: "var(--text)", wordBreak: "break-all",
            border: "0.5px solid var(--border)" }}>
            {alert.log_text}
          </code>
        </Section>

        {/* Category */}
        <Section title="Classification">
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <code style={{ fontSize: 13, color: "var(--accent)", fontWeight: 500 }}>
              {alert.label}
            </code>
            <span style={{ fontSize: 12, color: "var(--muted)" }}>
              ({(alert.confidence * 100).toFixed(0)}% confidence)
            </span>
          </div>
          {alert.source_ip && (
            <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 4 }}>
              Source IP: <code style={{ color: "var(--text)" }}>{alert.source_ip}</code>
            </div>
          )}
        </Section>

        {/* LLM Explanation */}
        <Section title="AI Analysis" icon={<AlertTriangle size={13} />}>
          <p style={{ fontSize: 13, lineHeight: 1.7, color: "var(--text)", margin: 0,
            whiteSpace: "pre-wrap" }}>
            {alert.explanation || "No explanation available."}
          </p>
        </Section>

        {/* MITRE */}
        {alert.mitre_technique && (
          <Section title="MITRE ATT&CK" icon={<Link size={13} />}>
            <span style={{ fontSize: 12, fontWeight: 500, padding: "3px 10px",
              background: "#ede9fe", color: "#5b21b6", borderRadius: 99 }}>
              {alert.mitre_technique}
            </span>
          </Section>
        )}

        {/* Similar logs */}
        {similar.length > 0 && (
          <Section title={`Similar logs (${similar.length})`}>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {similar.map((s, i) => (
                <div key={i} style={{ fontSize: 12, padding: "8px 10px",
                  background: "var(--surface)", borderRadius: 8,
                  border: "0.5px solid var(--border)" }}>
                  <div style={{ display: "flex", justifyContent: "space-between",
                    marginBottom: 4 }}>
                    <code style={{ color: "var(--accent)", fontSize: 11 }}>{s.label}</code>
                    <span style={{ color: "var(--muted)", fontSize: 11 }}>
                      {(s.similarity * 100).toFixed(0)}% match
                    </span>
                  </div>
                  <div style={{ color: "var(--muted)", overflow: "hidden",
                    textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {s.log_text}
                  </div>
                </div>
              ))}
            </div>
          </Section>
        )}

        {/* Feedback */}
        <Section title="Analyst feedback">
          <div style={{ display: "flex", gap: 8 }}>
            <FeedbackBtn
              active={feedback === "correct"}
              color="#16a34a" bgActive="#dcfce7"
              onClick={() => handleFeedback("correct")}
              icon={<ThumbsUp size={14} />}
              label="Correct" />
            <FeedbackBtn
              active={feedback === "false_positive"}
              color="#dc2626" bgActive="#fee2e2"
              onClick={() => handleFeedback("false_positive")}
              icon={<ThumbsDown size={14} />}
              label="False positive" />
          </div>
          {feedback && (
            <p style={{ fontSize: 12, color: "var(--muted)", margin: "8px 0 0" }}>
              Feedback recorded: <strong>{feedback.replace("_", " ")}</strong>
            </p>
          )}
        </Section>

      </div>
    </div>
  );
}

function Section({ title, icon, children }) {
  return (
    <div>
      <div style={{ fontSize: 11, fontWeight: 500, color: "var(--muted)",
        textTransform: "uppercase", letterSpacing: "0.06em",
        marginBottom: 8, display: "flex", alignItems: "center", gap: 5 }}>
        {icon}{title}
      </div>
      {children}
    </div>
  );
}

function FeedbackBtn({ active, color, bgActive, onClick, icon, label }) {
  return (
    <button onClick={onClick} style={{
      display: "flex", alignItems: "center", gap: 6,
      padding: "6px 14px", borderRadius: 8, cursor: "pointer",
      border: `0.5px solid ${active ? color : "var(--border)"}`,
      background: active ? bgActive : "transparent",
      color: active ? color : "var(--muted)",
      fontSize: 13, fontWeight: 500, transition: "all 0.15s",
    }}>
      {icon} {label}
    </button>
  );
}