import { useEffect, useState } from "react";
import { getStats } from "../api/client";

const StatCard = ({ label, value, color }) => (
  <div style={{
    background: "var(--card)", border: "0.5px solid var(--border)",
    borderRadius: 10, padding: "14px 20px", minWidth: 130, flex: 1,
  }}>
    <div style={{
      fontSize: 11, color: "var(--muted)", fontWeight: 500,
      textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 6,
    }}>
      {label}
    </div>
    <div style={{ fontSize: 26, fontWeight: 600, color: color || "var(--text)" }}>
      {value ?? "—"}
    </div>
  </div>
);

/**
 * StatsBar accepts either:
 *   - stats prop (pre-fetched by useAlerts hook) — no extra HTTP call
 *   - refreshTick prop (fallback: triggers its own fetch if stats not provided)
 */
export default function StatsBar({ stats: statsProp, refreshTick }) {
  const [localStats, setLocalStats] = useState(null);

  // Only fetch independently if the parent didn't pass stats down
  useEffect(() => {
    if (statsProp !== undefined) return;
    getStats()
      .then((r) => setLocalStats(r.data))
      .catch(() => {});
  }, [refreshTick, statsProp]);

  const stats = statsProp ?? localStats;

  return (
    <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
      <StatCard label="Total logs"        value={stats?.total_logs}      />
      <StatCard label="Critical"          value={stats?.critical_count}  color="#dc2626" />
      <StatCard label="High"              value={stats?.high_count}      color="#ea580c" />
      <StatCard label="Attack chains"     value={stats?.attack_chains}   color="#7c3aed" />
      <StatCard label="Correct feedback"  value={stats?.correct_feedback} color="#16a34a" />
      <StatCard label="False positives"   value={stats?.false_positives} color="#ca8a04" />
      {stats?.accuracy_estimate != null && (
        <StatCard
          label="Est. accuracy"
          value={`${(stats.accuracy_estimate * 100).toFixed(0)}%`}
          color="#0284c7"
        />
      )}
    </div>
  );
}