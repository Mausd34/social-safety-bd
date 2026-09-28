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
  hotels: (params = {}) => { const query = new URLSearchParams(params).toString(); return request(`/hotels/${query ? `?${query}` : ""}`); },
  hotelDetail: (id) => request(`/hotels/${id}/`),
  submitHotelReview: payload => request("/hotels/reviews/", {method:"POST", body:JSON.stringify(payload)}),
  adminHotelReviews: () => request("/admin/hotels/reviews/"),
  moderateHotelReview: (id, status) => request("/admin/hotels/reviews/", {method:"PATCH", body:JSON.stringify({id, status})}),

  // Citizen journal. The backend mounts these under /api/journal/ so the
  // existing /api routes stay exactly as they were.
  journalPosts: (params = {}) => { const query = new URLSearchParams(params).toString(); return request(`/journal/posts/${query ? `?${query}` : ""}`); },
  journalPost: id => request(`/journal/posts/${id}/`),
  createJournalPost: payload => request("/journal/posts/", {method:"POST", body:JSON.stringify(payload)}),
  updateJournalPost: (id, payload) => request(`/journal/posts/${id}/`, {method:"PATCH", body:JSON.stringify(payload)}),
  deleteJournalPost: id => request(`/journal/posts/${id}/`, {method:"DELETE"}),
  toggleJournalLike: (id, liked) => request(`/journal/posts/${id}/like/`, {method: liked ? "DELETE" : "POST"}),
  shareJournalPost: (id, channel = "LINK") => request(`/journal/posts/${id}/share/`, {method:"POST", body:JSON.stringify({channel})}),
  viewJournalPost: id => request(`/journal/posts/${id}/view/`, {method:"POST"}),
  trendingPosts: (params = {}) => { const query = new URLSearchParams(params).toString(); return request(`/journal/posts/trending/${query ? `?${query}` : ""}`); },
  journalFeed: (params = {}) => { const query = new URLSearchParams(params).toString(); return request(`/journal/feed/${query ? `?${query}` : ""}`); },
  postComments: id => request(`/journal/posts/${id}/comments/`),
  addComment: (postId, body, parent) => request("/journal/comments/", {method:"POST", body:JSON.stringify({post: postId, body, ...(parent ? {parent} : {})})}),
  toggleCommentLike: (id, liked) => request(`/journal/comments/${id}/like/`, {method: liked ? "DELETE" : "POST"}),
  journalSearch: q => request(`/journal/search/?q=${encodeURIComponent(q)}`),
  journalStats: (city = "") => request(`/journal/stats/${city ? `?city=${encodeURIComponent(city)}` : ""}`),
  myJournalPosts: () => request("/journal/me/posts/"),
  myJournalAnalytics: () => request("/journal/me/analytics/"),
  reportJournalPost: (id, reason) => request("/journal/flags/", {method:"POST", body:JSON.stringify({post: id, reason})}),
  applyJournalist: payload => request("/journal/journalist/apply/", {method:"POST", body:JSON.stringify(payload)}),
  adminJournalFlags: (status = "") => request(`/journal/admin/flags/${status ? `?status=${encodeURIComponent(status)}` : ""}`),
  resolveJournalFlag: (id, status, resolution) => request("/journal/admin/flags/", {method:"PATCH", body:JSON.stringify({id, status, ...(resolution ? {resolution} : {})})}),
  adminJournalists: (status = "") => request(`/journal/admin/journalists/${status ? `?status=${encodeURIComponent(status)}` : ""}`),
  reviewJournalist: (id, status, notes) => request("/journal/admin/journalists/", {method:"PATCH", body:JSON.stringify({id, status, ...(notes ? {notes} : {})})}),
};
export default api;
