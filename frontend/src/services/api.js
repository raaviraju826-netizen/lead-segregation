import axios from "axios";

export const API_BASE = import.meta.env.VITE_API_URL || "/api";
const http = axios.create({ baseURL: API_BASE, timeout: 120000 });

http.interceptors.request.use((cfg) => {
  const k = localStorage.getItem("leadsense_key");
  if (k) cfg.headers["X-API-Key"] = k;
  return cfg;
});

export function errorMessage(err) {
  const d = err?.response?.data;
  if (d?.detail) return typeof d.detail === "string" ? d.detail : JSON.stringify(d.detail);
  if (err?.code === "ERR_NETWORK") return "Cannot reach the backend. Is it running on port 8000?";
  return err?.message || "Unexpected error";
}

const clean = (p = {}) => Object.fromEntries(Object.entries(p).filter(([, v]) => v !== "" && v != null && v !== false));

export const api = {
  health: () => http.get("/health").then((r) => r.data),
  stats: (source) => http.get("/stats", { params: { source } }).then((r) => r.data),
  industries: (source) => http.get("/industries", { params: { source } }).then((r) => r.data),
  updateIndustryConfig: (slug, body) => http.patch(`/industries/${slug}`, body).then((r) => r.data),
  leads: (params) => http.get("/leads", { params: clean(params) }).then((r) => r.data),
  industryLeads: (slug, params) => http.get(`/leads/industry/${slug}`, { params: clean(params) }).then((r) => r.data),
  reviewQueue: (params) => http.get("/review-queue", { params: clean(params) }).then((r) => r.data),
  lead: (id) => http.get(`/leads/${id}`).then((r) => r.data),
  review: (id, body) => http.patch(`/leads/${id}/review`, body).then((r) => r.data),
  patchIndustry: (id, body) => http.patch(`/leads/${id}/industry`, body).then((r) => r.data),
  gmailStatus: () => http.get("/gmail/status").then((r) => r.data),
  gmailSync: () => http.post("/gmail/sync").then((r) => r.data),
  gmailDisconnect: () => http.post("/gmail/disconnect").then((r) => r.data),
  simulateGmailInbox: () => http.post("/gmail/simulate-inbox").then((r) => r.data),
  connectAppPassword: (email, app_password) => http.post("/gmail/app-password", { email, app_password }).then((r) => r.data),
  saveOAuthCredentials: (client_id, client_secret) => http.post("/gmail/oauth-credentials", { client_id, client_secret }).then((r) => r.data),
  uploadClientSecret: (file) => {
    const fd = new FormData();
    fd.append("file", file);
    return http.post("/gmail/client-secret", fd, { headers: { "Content-Type": "multipart/form-data" } }).then((r) => r.data);
  },
  syncs: () => http.get("/gmail/syncs").then((r) => r.data),
  demoLoad: () => http.post("/demo/load").then((r) => r.data),
  demoClear: () => http.delete("/demo").then((r) => r.data),
  duplicates: (status = "open") => http.get("/duplicates", { params: { status } }).then((r) => r.data),
  duplicateLogs: () => http.get("/duplicates/logs").then((r) => r.data),
  resolveDuplicate: (id, action) => http.post(`/duplicates/${id}/resolve`, { action }).then((r) => r.data),
  batches: () => http.get("/batches").then((r) => r.data),
  batch: (id) => http.get(`/batches/${id}`).then((r) => r.data),
  ingestEmail: (body) => http.post("/emails/ingest", body).then((r) => r.data),
  uploadFile: (file, { columnMapping, source = "upload", onProgress } = {}) => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("source", source);
    if (columnMapping && Object.keys(columnMapping).length > 0) {
      fd.append("column_mapping", JSON.stringify(columnMapping));
    }
    return http
      .post("/uploads", fd, {
        headers: { "Content-Type": "multipart/form-data" },
        onUploadProgress: (evt) => {
          if (onProgress && evt.total) {
            onProgress(Math.round((evt.loaded * 100) / evt.total));
          }
        },
      })
      .then((r) => r.data);
  },
  async download(kind, { source, industry }) {
    const res = await http.get(`/exports/${kind}`, { params: clean({ source, industry }), responseType: "blob" });
    const cd = res.headers["content-disposition"] || "";
    const name = /filename="?([^";]+)"?/.exec(cd)?.[1] || `leadsense.${kind === "excel" ? "xlsx" : "csv"}`;
    const url = URL.createObjectURL(res.data);
    const a = Object.assign(document.createElement("a"), { href: url, download: name });
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  },
};
export const connectUrl = `${API_BASE}/gmail/connect`;
