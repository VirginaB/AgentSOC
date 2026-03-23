const TIER_STYLES = {
  CRITICAL: { bg: "#fee2e2", text: "#991b1b", dot: "#dc2626" },
  HIGH:     { bg: "#ffedd5", text: "#9a3412", dot: "#ea580c" },
  MEDIUM:   { bg: "#fef9c3", text: "#854d0e", dot: "#ca8a04" },
  LOW:      { bg: "#dcfce7", text: "#166534", dot: "#16a34a" },
};

export default function SeverityBadge({ tier, size = "sm" }) {
  const style = TIER_STYLES[tier] || TIER_STYLES["LOW"];
  const pad = size === "lg" ? "4px 14px" : "2px 8px";
  const fontSize = size === "lg" ? "13px" : "11px";

  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 5,
      background: style.bg, color: style.text,
      padding: pad, borderRadius: 99,
      fontSize, fontWeight: 500, whiteSpace: "nowrap",
    }}>
      <span style={{
        width: size === "lg" ? 8 : 6, height: size === "lg" ? 8 : 6,
        borderRadius: "50%", background: style.dot, flexShrink: 0,
      }} />
      {tier}
    </span>
  );
}