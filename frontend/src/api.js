// Relative by default: the Vite dev server proxies /api to Django, and in
// production the app is served from the same origin as the API. Set
// VITE_API_URL to an absolute URL only when the API lives on another host.
const API_BASE = import.meta.env.VITE_API_URL || "/api";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    ...options,
    headers: { ...(options.body instanceof FormData ? {} : { "Content-Type": "application/json" }), ...(options.headers || {}) },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.message || `Request failed: ${response.status}`);
  return data;
}

export const api = {
  health: () => request("/health/"),
  cities: () => request("/cities/"),
  areas: (city = "") => request(`/areas/${city ? `?city=${encodeURIComponent(city)}` : ""}`),
  cases: (params = {}) => { const query = new URLSearchParams(params).toString(); return request(`/cases/${query ? `?${query}` : ""}`); },
  statistics: () => request("/statistics/"),
  caseDetail: id => request(`/cases/${encodeURIComponent(id)}/`),
  login: (email, password) => request("/login/", {method:"POST", body:JSON.stringify({email,password})}),
  register: (name,email,password) => request("/register/", {method:"POST", body:JSON.stringify({name,email,password})}),
  me: () => request("/me/"),
  logout: () => request("/logout/", {method:"POST"}),
  submitReport: formData => request("/reports/", {method:"POST", body:formData}),
  adminReports: () => request("/admin/reports/"),
  updateReport: (id,status) => request("/admin/reports/", {method:"PATCH", body:JSON.stringify({id,status})}),
  upazilas: (params = {}) => { const query = new URLSearchParams(params).toString(); return request(`/upazilas/${query ? `?${query}` : ""}`); },
  startThread: (upazila, message) => request("/chat/threads/", {method:"POST", body:JSON.stringify({upazila, message})}),
  thread: (id) => request(`/chat/threads/${id}/`),
  postMessage: (id, message) => request(`/chat/threads/${id}/`, {method:"POST", body:JSON.stringify({message})}),
  adminThreads: () => request("/admin/chat/"),
  staffReply: (id, message, status) => request("/admin/chat/", {method:"POST", body:JSON.stringify({id, message, status})}),
};
export default api;
