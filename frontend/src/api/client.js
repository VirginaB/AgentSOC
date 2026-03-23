import axios from "axios";

const BASE = "http://localhost:8000";
const api = axios.create({ baseURL: BASE });

export const analyzeLog   = (log_text, source_ip) => api.post("/api/analyze", { log_text, source_ip });
export const getAlerts    = (limit = 50, tier)    => api.get("/api/alerts", { params: { limit, tier } });
export const getAlert     = (id)                  => api.get(`/api/alerts/${id}`);
export const getSimilar   = (id)                  => api.get(`/api/similar/${id}`);
export const getChains    = ()                     => api.get("/api/chains");
export const getStats     = ()                     => api.get("/api/stats");
export const sendChat     = (message, history)    => api.post("/api/chat", { message, history });
export const sendFeedback = (alert_id, feedback)  => api.post("/api/feedback", { alert_id, feedback });
export const startStream  = ()                     => api.post("/api/stream/start");
export const stopStream   = ()                     => api.post("/api/stream/stop");
export const streamStatus = ()                     => api.get("/api/stream/status");