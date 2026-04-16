import axios from "axios";

const BASE = "http://localhost:8000";
const api = axios.create({ baseURL: BASE });

export const analyzeLog    = (log_text, source_ip) => api.post("/api/analyze", { log_text, source_ip });

// Used by UploadPanel.jsx — was previously misnamed "uploadLogFile"
export const uploadFile    = (formData) =>
  api.post("/api/analyze/upload", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });

// Keep old name as alias so nothing else breaks if it was used elsewhere
export const uploadLogFile = uploadFile;

export const getAlerts     = (limit = 50, tier)   => api.get("/api/alerts", { params: { limit, tier } });
export const getAlert      = (id)                  => api.get(`/api/alerts/${id}`);
export const generateExplanation = (id)           => api.post(`/api/alerts/${id}/explain`);
export const getSimilar    = (id)                  => api.get(`/api/similar/${id}`);
export const getChains     = ()                    => api.get("/api/chains");
export const getStats      = ()                    => api.get("/api/stats");
export const sendChat      = (message, history)   => api.post("/api/chat", { message, history });
export const sendFeedback  = (alert_id, feedback) => api.post("/api/feedback", { alert_id, feedback });

// Demo stream
export const startStream   = ()                    => api.post("/api/stream/start");
export const stopStream    = ()                    => api.post("/api/stream/stop");
export const streamStatus  = ()                    => api.get("/api/stream/status");

// OS log watcher — used by WatcherStatus.jsx
export const getWatcherStatus = ()                 => api.get("/api/watcher/status");
export const startWatcher     = ()                 => api.post("/api/watcher/start");
export const stopWatcher      = ()                 => api.post("/api/watcher/stop");

// MITRE ATT&CK lookup
export const getMitreTechnique = (techniqueId)     => api.get(`/api/mitre/${encodeURIComponent(techniqueId)}`);
export const getMitreByLabel   = (label)           => api.get(`/api/mitre/by-label/${encodeURIComponent(label)}`);
