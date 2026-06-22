import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

const api = axios.create({ baseURL: API });

export const apiClient = {
  // categories
  getCategories: () => api.get("/categories").then(r => r.data),
  getLogicTree: (catId) => api.get(`/categories/${catId}/logic-tree`).then(r => r.data),
  // cases
  listCases: (params) => api.get("/cases", { params }).then(r => r.data),
  getCase: (id) => api.get(`/cases/${id}`).then(r => r.data),
  createCase: (payload) => api.post("/cases", payload).then(r => r.data),
  updateCase: (id, payload) => api.patch(`/cases/${id}`, payload).then(r => r.data),
  deleteCase: (id) => api.delete(`/cases/${id}`).then(r => r.data),
  // files
  uploadFiles: (caseId, files, layer) => {
    const fd = new FormData();
    files.forEach(f => fd.append("files", f));
    if (layer) fd.append("layer", layer);
    return api.post(`/cases/${caseId}/files`, fd, { headers: { "Content-Type": "multipart/form-data" } }).then(r => r.data);
  },
  deleteFile: (caseId, fileId) => api.delete(`/cases/${caseId}/files/${fileId}`).then(r => r.data),
  setFileLayer: (caseId, fileId, layer) => {
    const fd = new FormData();
    fd.append("layer", layer);
    return api.patch(`/cases/${caseId}/files/${fileId}`, fd).then(r => r.data);
  },
  previewFile: (caseId, fileId) => api.get(`/cases/${caseId}/files/${fileId}/preview`).then(r => r.data),
  extractZip: (caseId, fileId) => api.post(`/cases/${caseId}/files/${fileId}/extract`).then(r => r.data),
  // logic
  saveLogic: (caseId, answers) => api.post(`/cases/${caseId}/logic`, answers).then(r => r.data),
  // analyze (kicks off background job and returns immediately)
  analyze: (caseId, useA = true, useB = true) => api.post(`/cases/${caseId}/analyze`, { use_provider_a: useA, use_provider_b: useB }, { timeout: 30000 }).then(r => r.data),
  analyzeStatus: (caseId) => api.get(`/cases/${caseId}/analyze/status`).then(r => r.data),
  // orchestrator (deep investigation with map-reduce + self-critique)
  orchestrate: (caseId) => api.post(`/cases/${caseId}/orchestrate`, {}, { timeout: 30000 }).then(r => r.data),
  orchestrateStatus: (caseId) => api.get(`/cases/${caseId}/orchestrate/status`).then(r => r.data),
  listCasePatterns: (categoryId) => api.get(`/case-patterns`, { params: categoryId ? { category_id: categoryId } : {} }).then(r => r.data),
  // diagnostic quality (per-case composite score for the UI badge)
  diagnosticQuality: (caseId) => api.get(`/cases/${caseId}/diagnostic_quality`).then(r => r.data),
  // upload pre-flight (estimate chunks/coverage before sending bytes)
  uploadPreflight: (files) => api.post(`/upload/preflight`, { files }).then(r => r.data),
  // settings
  getSettings: () => api.get("/settings").then(r => r.data),
  saveSettings: (payload) => api.put("/settings", payload).then(r => r.data),
  // dashboard
  dashboardStats: () => api.get("/dashboard/stats").then(r => r.data),
  // export
  exportUrl: (caseId, format) => `${API}/cases/${caseId}/export?format=${format}`,
};
