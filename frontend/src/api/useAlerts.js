/**
 * useAlerts.js
 *
 * Replaces the polling pattern across the app.
 * Opens a single WebSocket to /ws/alerts and dispatches incoming events
 * to registered callbacks. Components call useAlerts() and get a live
 * stream of alerts + a refreshTick that increments on each event.
 *
 * Usage:
 *   const { alerts, stats, refreshTick, wsStatus } = useAlerts();
 */

import { useState, useEffect, useRef, useCallback } from "react";
import { getAlerts, getStats } from "./client";

const WS_URL = "ws://localhost:8000/ws/alerts";
const RECONNECT_DELAY_MS = 3000;
const MAX_ALERTS = 200; // keep last N in memory

function sortAlertsByTimestamp(alerts) {
  return [...alerts].sort((a, b) => {
    const aTime = a?.timestamp ? new Date(a.timestamp).getTime() : 0;
    const bTime = b?.timestamp ? new Date(b.timestamp).getTime() : 0;
    return bTime - aTime;
  });
}

export function useAlerts() {
  const [alerts, setAlerts]       = useState([]);
  const [stats, setStats]         = useState(null);
  const [refreshTick, setRefreshTick] = useState(0);
  const [wsStatus, setWsStatus]   = useState("connecting"); // connecting | open | closed
  const wsRef = useRef(null);
  const reconnectTimer = useRef(null);
  const mountedRef = useRef(true);

  // Initial HTTP fetch to populate the table before WS connects
  const fetchInitial = useCallback(async () => {
    try {
      const [alertsRes, statsRes] = await Promise.all([getAlerts(100), getStats()]);
      if (mountedRef.current) {
        setAlerts(sortAlertsByTimestamp(alertsRes.data || []));
        setStats(statsRes.data || null);
      }
    } catch (_) {}
  }, []);

  const connect = useCallback(() => {
    if (!mountedRef.current) return;
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;
    setWsStatus("connecting");

    ws.onopen = () => {
      if (!mountedRef.current) return;
      setWsStatus("open");
    };

    ws.onmessage = (event) => {
      if (!mountedRef.current) return;
      try {
        const { type, data } = JSON.parse(event.data);

        if (type === "new_alert") {
          setAlerts((prev) => {
            const next = [data, ...prev.filter((alert) => alert.id !== data.id)];
            return sortAlertsByTimestamp(next).slice(0, MAX_ALERTS);
          });
          setRefreshTick((t) => t + 1);
        }

        if (type === "stats_refresh") {
          // Server tells us stats changed; re-fetch
          getStats().then((r) => {
            if (mountedRef.current) setStats(r.data);
          }).catch(() => {});
          setRefreshTick((t) => t + 1);
        }
      } catch (_) {}
    };

    ws.onclose = () => {
      if (!mountedRef.current) return;
      setWsStatus("closed");
      // Reconnect after delay
      reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY_MS);
    };

    ws.onerror = () => {
      ws.close();
    };
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    fetchInitial();
    connect();

    return () => {
      mountedRef.current = false;
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect, fetchInitial]);

  return { alerts, stats, refreshTick, wsStatus };
}
