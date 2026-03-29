/**
 * WatcherStatus.jsx
 *
 * Shows real-time log watcher status in the header.
 * Watcher does NOT auto-start — analyst must click "Start OS Watcher" explicitly.
 * Uses the shared axios api client (no raw fetch / hardcoded URLs).
 */

import { useState, useEffect } from "react";
import { getWatcherStatus, startWatcher, stopWatcher } from "../api/client";
import { Activity, Wifi, WifiOff, Radio } from "lucide-react";

export default function WatcherStatus({ wsStatus }) {
  const [watcher, setWatcher]   = useState(null);
  const [toggling, setToggling] = useState(false);

  const fetchStatus = async () => {
    try {
      const { data } = await getWatcherStatus();
      setWatcher(data);
    } catch (_) {}
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 10_000);
    return () => clearInterval(interval);
  }, []);

  const toggle = async () => {
    if (!watcher || toggling) return;
    setToggling(true);
    try {
      if (watcher.running) {
        await stopWatcher();
      } else {
        await startWatcher();
      }
      await fetchStatus();
    } catch (_) {}
    setToggling(false);
  };

  const wsColor = wsStatus === "open"
    ? "#16a34a"
    : wsStatus === "connecting"
    ? "#ca8a04"
    : "#dc2626";

  const wsLabel = wsStatus === "open"
    ? "Live"
    : wsStatus === "connecting"
    ? "Connecting"
    : "Offline";

  const WsIcon = wsStatus === "open" ? Wifi : WifiOff;

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>

      {/* WebSocket connection badge */}
      <div style={{
        display: "flex", alignItems: "center", gap: 5,
        padding: "4px 10px", borderRadius: 99,
        border: `0.5px solid ${wsColor}44`,
        background: `${wsColor}11`,
      }}>
        <span style={{
          width: 6, height: 6, borderRadius: "50%", background: wsColor,
          ...(wsStatus === "open" ? { animation: "pulse-dot 2s ease-in-out infinite" } : {}),
        }} />
        <WsIcon size={12} color={wsColor} />
        <span style={{ fontSize: 12, fontWeight: 500, color: wsColor }}>
          {wsLabel}
        </span>
      </div>

      {/* OS log watcher toggle — off by default, user starts it manually */}
      {watcher !== null && (
        <button
          onClick={toggle}
          disabled={toggling}
          title={watcher.running
            ? "Stop real-time OS log collection"
            : "Start real-time OS log collection"}
          style={{
            display: "flex", alignItems: "center", gap: 5,
            padding: "4px 12px", borderRadius: 99, cursor: "pointer",
            border: `0.5px solid ${watcher.running ? "#7c3aed44" : "var(--border)"}`,
            background: watcher.running ? "#7c3aed11" : "transparent",
            color: watcher.running ? "#7c3aed" : "var(--muted)",
            fontSize: 12, fontWeight: 500,
            opacity: toggling ? 0.5 : 1,
            transition: "all 0.2s",
          }}
        >
          {watcher.running
            ? <Radio size={12} style={{ animation: "pulse-scale 1.5s ease-in-out infinite" }} />
            : <Activity size={12} />
          }
          {toggling
            ? (watcher.running ? "Stopping…" : "Starting…")
            : (watcher.running ? "Watching OS logs" : "Start OS watcher")}
          {watcher.running && watcher.queue_size > 0 && (
            <span style={{
              padding: "1px 6px", borderRadius: 99,
              background: "#7c3aed", color: "#fff", fontSize: 10,
            }}>
              {watcher.queue_size}
            </span>
          )}
        </button>
      )}

      <style>{`
        @keyframes pulse-dot {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
        @keyframes pulse-scale {
          0%, 100% { transform: scale(1); }
          50% { transform: scale(1.2); }
        }
      `}</style>
    </div>
  );
}