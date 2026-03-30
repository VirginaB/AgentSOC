/**
 * ModelVotes.jsx — Shows per-model majority vote breakdown.
 * Used inside AlertPanel when alert.model_votes is present.
 */

const MODEL_COLORS = {
  svm:       "#0284c7",
  lstm:      "#7c3aed",
  bert:      "#059669",
  sbert:     "#d97706",
  logformer: "#dc2626",
};

export default function ModelVotes({ votes, finalLabel }) {
  if (!votes) return null;

  const entries = Object.entries(votes).filter(([, v]) => v !== null);
  if (entries.length === 0) return null;

  const agreeCount = entries.filter(([, v]) => v === finalLabel).length;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div style={{ display: "flex", gap: 6, alignItems: "center", marginBottom: 2 }}>
        <span style={{
          fontSize: 11, padding: "2px 8px", borderRadius: 99, fontWeight: 500,
          background: agreeCount === entries.length ? "#dcfce7" : "#fef9c3",
          color: agreeCount === entries.length ? "#166534" : "#854d0e",
        }}>
          {agreeCount}/{entries.length} agree
        </span>
        <span style={{ fontSize: 11, color: "var(--muted)" }}>majority vote</span>
      </div>

      {entries.map(([name, label]) => {
        const agrees = label === finalLabel;
        const color  = MODEL_COLORS[name] || "var(--accent)";
        return (
          <div key={name} style={{
            display: "flex", alignItems: "center", gap: 8,
            padding: "6px 10px", borderRadius: 8,
            background: agrees ? "var(--surface)" : "transparent",
            border: `0.5px solid ${agrees ? color + "44" : "var(--border)"}`,
          }}>
            <span style={{
              width: 7, height: 7, borderRadius: "50%",
              background: color, opacity: agrees ? 1 : 0.3, flexShrink: 0,
            }}/>
            <span style={{
              fontSize: 12, fontWeight: 500, minWidth: 72,
              color: agrees ? "var(--text)" : "var(--muted)",
            }}>
              {name.toUpperCase()}
            </span>
            <code style={{ fontSize: 11, color: agrees ? color : "var(--muted)" }}>
              {label}
            </code>
            {!agrees && (
              <span style={{
                marginLeft: "auto", fontSize: 10, padding: "1px 6px",
                borderRadius: 99, background: "#fee2e2", color: "#991b1b",
              }}>
                disagrees
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}