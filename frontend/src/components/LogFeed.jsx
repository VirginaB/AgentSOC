import { useEffect, useState } from "react";
import { getAlerts, sendFeedback } from "../api/client";
import SeverityBadge from "./SeverityBadge";
import { ThumbsUp, ThumbsDown, ChevronRight } from "lucide-react";

/**
 * LogFeed accepts either:
 *   - alerts prop (pre-fetched by useAlerts hook) — no extra HTTP call, live via WS
 *   - refreshTick alone (fallback: fetches its own alerts via HTTP)
 */
export default function LogFeed({ alerts: alertsProp, refreshTick, onSelectAlert }) {
  const [localAlerts, setLocalAlerts] = useState([]);
  const [filter, setFilter]           = useState("ALL");

  // Only fetch independently if parent didn't pass alerts down
  const load = async () => {
    if (alertsProp !== undefined) return;
    try {
      const tier = filter === "ALL" ? undefined : filter;
      const { data } = await getAlerts(100, tier);
      setLocalAlerts(data);
    } catch (_) {}
  };

  useEffect(() => { load(); }, [refreshTick, filter, alertsProp]);

  const handleFeedback = async (e, id, type) => {
    e.stopPropagation();
    try {
      await sendFeedback(id, type);
      // Update whichever list we're working from
      const update = (prev) => prev.map((a) => a.id === id ? { ...a, feedback: type } : a);
      if (alertsProp !== undefined) {
        // alertsProp is managed by the parent (useAlerts hook) — we can't mutate it,
        // but feedback is optimistic UI only; the server has already saved it.
        // A full refresh will pick it up. For now just show nothing broken.
      } else {
        setLocalAlerts(update);
      }
    } catch (_) {}
  };

  // Use prop alerts if available, fall back to local fetch
  const allAlerts = alertsProp ?? localAlerts;

  // Client-side filter when using prop alerts (server filters for local fetch)
  const alerts = filter === "ALL"
    ? allAlerts
    : allAlerts.filter((a) => a.risk_tier === filter);

  const tiers = ["ALL", "CRITICAL", "HIGH", "MEDIUM", "LOW"];

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>

      {/* Filter tabs */}
      <div style={{ display: "flex", gap: 6, marginBottom: 12, flexWrap: "wrap" }}>
        {tiers.map((t) => (
          <button key={t} onClick={() => setFilter(t)} style={{
            padding: "4px 14px", borderRadius: 99, fontSize: 12, fontWeight: 500,
            cursor: "pointer", border: "0.5px solid var(--border)",
            background: filter === t ? "var(--accent)" : "var(--card)",
            color: filter === t ? "#fff" : "var(--muted)",
            transition: "all 0.15s",
          }}>{t}</button>
        ))}
        <span style={{ marginLeft: "auto", fontSize: 12, color: "var(--muted)", alignSelf: "center" }}>
          {alerts.length} alerts
        </span>
      </div>

      {/* Table */}
      <div style={{ flex: 1, overflowY: "auto", borderRadius: 10, border: "0.5px solid var(--border)" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr style={{ background: "var(--surface)", position: "sticky", top: 0 }}>
              {["Time", "Log (truncated)", "Category", "Score", "Tier", "Feedback", ""].map((h) => (
                <th key={h} style={{
                  padding: "10px 14px", textAlign: "left",
                  fontWeight: 500, fontSize: 11, color: "var(--muted)",
                  textTransform: "uppercase", letterSpacing: "0.05em",
                  borderBottom: "0.5px solid var(--border)",
                }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {alerts.length === 0 && (
              <tr>
                <td colSpan={7} style={{ padding: 32, textAlign: "center", color: "var(--muted)", fontSize: 13 }}>
                  No alerts yet. Start the stream or submit a log.
                </td>
              </tr>
            )}
            {alerts.map((a, i) => (
              <tr
                key={a.id}
                onClick={() => onSelectAlert(a)}
                style={{
                  cursor: "pointer",
                  background: i % 2 === 0 ? "var(--card)" : "var(--surface)",
                  borderBottom: "0.5px solid var(--border)",
                  transition: "background 0.1s",
                }}
                onMouseEnter={(e) => e.currentTarget.style.background = "var(--hover)"}
                onMouseLeave={(e) => e.currentTarget.style.background =
                  i % 2 === 0 ? "var(--card)" : "var(--surface)"}
              >
                <td style={{ padding: "9px 14px", color: "var(--muted)", whiteSpace: "nowrap" }}>
                  {new Date(a.timestamp).toLocaleTimeString()}
                </td>
                <td style={{ padding: "9px 14px", maxWidth: 320 }}>
                  <span style={{
                    display: "block", overflow: "hidden",
                    textOverflow: "ellipsis", whiteSpace: "nowrap", color: "var(--text)",
                  }}>{a.log_text}</span>
                </td>
                <td style={{ padding: "9px 14px", color: "var(--muted)", whiteSpace: "nowrap",
                  fontFamily: "monospace", fontSize: 12 }}>
                  {a.label}
                </td>
                <td style={{
                  padding: "9px 14px", fontWeight: 600,
                  color: a.risk_score >= 81 ? "#dc2626"
                       : a.risk_score >= 61 ? "#ea580c"
                       : a.risk_score >= 31 ? "#ca8a04" : "#16a34a",
                }}>
                  {a.risk_score?.toFixed(1)}
                </td>
                <td style={{ padding: "9px 14px" }}>
                  <SeverityBadge tier={a.risk_tier} />
                </td>
                <td style={{ padding: "9px 14px" }}>
                  <div style={{ display: "flex", gap: 4 }}>
                    <button
                      title="Correct"
                      onClick={(e) => handleFeedback(e, a.id, "correct")}
                      style={{
                        padding: "3px 6px", borderRadius: 6, border: "0.5px solid var(--border)",
                        background: a.feedback === "correct" ? "#dcfce7" : "transparent",
                        cursor: "pointer", display: "flex", alignItems: "center",
                      }}
                    >
                      <ThumbsUp size={13} color={a.feedback === "correct" ? "#16a34a" : "var(--muted)"} />
                    </button>
                    <button
                      title="False positive"
                      onClick={(e) => handleFeedback(e, a.id, "false_positive")}
                      style={{
                        padding: "3px 6px", borderRadius: 6, border: "0.5px solid var(--border)",
                        background: a.feedback === "false_positive" ? "#fee2e2" : "transparent",
                        cursor: "pointer", display: "flex", alignItems: "center",
                      }}
                    >
                      <ThumbsDown size={13} color={a.feedback === "false_positive" ? "#dc2626" : "var(--muted)"} />
                    </button>
                  </div>
                </td>
                <td style={{ padding: "9px 10px" }}>
                  <ChevronRight size={14} color="var(--muted)" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}