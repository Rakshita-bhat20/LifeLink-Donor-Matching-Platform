/* LifeLink single-page client. Plain JavaScript, no build step. */
"use strict";

const CITIES = {
  "Bengaluru": [12.9716, 77.5946], "Whitefield": [12.9698, 77.75], "Jayanagar": [12.925, 77.5938],
  "Yelahanka": [13.1007, 77.5963], "Hosur": [12.7409, 77.8253], "Tumakuru": [13.3379, 77.1173],
  "Mysuru": [12.2958, 76.6394], "Mangaluru": [12.9141, 74.856], "Chennai": [13.0827, 80.2707],
  "Hyderabad": [17.385, 78.4867],
};
const GROUPS = ["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"];
const ORGANS = ["kidney", "liver", "heart", "lung", "pancreas"];
const WINDOWS = { heart: 4, lung: 6, liver: 12, pancreas: 12, kidney: 36 };

const state = { token: null, user: null, stats: null, requests: [], selected: null, matches: [],
                rejected: null, open: new Set(), authTab: "login", donor: null, offers: [],
                audit: [], verify: null };

const $app = document.getElementById("app");

function store(key, value) {
  try { value === null ? sessionStorage.removeItem(key) : sessionStorage.setItem(key, value); } catch (e) { /* storage blocked */ }
}
function load(key) {
  try { return sessionStorage.getItem(key); } catch (e) { return null; }
}

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function toast(message, bad = false) {
  const el = document.getElementById("toast");
  el.textContent = message;
  el.className = "show" + (bad ? " bad" : "");
  setTimeout(() => { el.className = ""; }, 3200);
}

async function api(path, method = "GET", body) {
  const headers = { "Content-Type": "application/json" };
  if (state.token) headers.Authorization = "Bearer " + state.token;
  const res = await fetch("/api" + path, { method, headers, body: body ? JSON.stringify(body) : undefined });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = data.errors ? Object.entries(data.errors).map(([k, v]) => `${k} ${v}`).join("; ") : "";
    const err = new Error(detail || data.error || "Request failed");
    err.status = res.status;
    throw err;
  }
  return data;
}

const opts = (items, current) => items.map((i) => `<option ${i === current ? "selected" : ""}>${esc(i)}</option>`).join("");
const dots = (n) => "●".repeat(n) + "○".repeat(5 - n);
const chip = (text, cls = "") => `<span class="chip ${esc(cls || text)}">${esc(text)}</span>`;

/* ---------- auth screen ---------- */
function renderAuth(error = "") {
  const reg = state.authTab === "register";
  $app.innerHTML = `
  <div class="topbar"><div class="brand"><span class="drop"></span>LifeLink</div></div>
  <div class="auth card">
    <h1>${reg ? "Create your account" : "Welcome back"}</h1>
    <p class="muted">A donor-recipient matching network for blood and organs.</p>
    <div class="tabs"><button data-tab="login" class="${reg ? "" : "on"}">Log in</button><button data-tab="register" class="${reg ? "on" : ""}">Register</button></div>
    <form id="authForm" novalidate>
      ${reg ? `<label for="name">Full name / hospital name</label><input id="name" required>` : ""}
      <label for="email">Email</label><input id="email" type="email" required>
      <label for="password">Password</label><input id="password" type="password" required>
      ${reg ? `<label for="role">I am a</label><select id="role"><option value="donor">Donor</option><option value="hospital">Hospital</option></select>` : ""}
      <div class="err" id="authErr">${esc(error)}</div>
      <button class="btn block" type="submit">${reg ? "Create account" : "Log in"}</button>
    </form>
    ${reg ? "" : `<div class="demo"><span class="muted">Demo:</span>
      <button class="btn ghost small" data-demo="hospital@lifelink.test|Hospital@123">Hospital</button>
      <button class="btn ghost small" data-demo="donor@lifelink.test|Donor@1234">Donor</button>
      <button class="btn ghost small" data-demo="admin@lifelink.test|Admin@1234">Admin</button></div>`}
    <div class="note">Academic prototype. Not a clinical system. Do not enter real patient data.</div>
  </div>`;
}

async function submitAuth(form) {
  const reg = state.authTab === "register";
  const body = { email: form.email.value.trim(), password: form.password.value };
  if (reg) { body.name = form.name.value.trim(); body.role = form.role.value; }
  try {
    const data = await api(reg ? "/auth/register" : "/auth/login", "POST", body);
    state.token = data.token; state.user = data.user;
    store("ll_token", data.token);
    await enter();
  } catch (e) { renderAuth(e.message); }
}

function logout() {
  Object.assign(state, { token: null, user: null, selected: null, matches: [], rejected: null });
  store("ll_token", null);
  renderAuth();
}

/* ---------- shell ---------- */
function shell(inner) {
  const u = state.user;
  $app.innerHTML = `
  <div class="topbar"><div class="brand"><span class="drop"></span>LifeLink</div>
    <div class="who"><span>${esc(u.name)}</span><span class="role">${esc(u.role)}</span><button class="btn ghost small" style="color:#fff;border-color:#ffffff55" data-action="logout">Log out</button></div></div>
  <div class="wrap">${statsHtml()}${inner}</div>`;
}

function statsHtml() {
  const s = state.stats;
  if (!s) return "";
  const cell = (n, label) => `<div class="stat"><b>${n}</b><span>${label}</span></div>`;
  return `<div class="stats">${cell(s.available_donors, "Available donors")}${cell(s.open_requests, "Open requests")}${cell(s.fulfilled_requests, "Fulfilled requests")}${cell(s.lives_touched, "Successful donations")}</div>`;
}

async function enter() {
  const role = state.user.role;
  state.stats = (await api("/stats")).stats;
  if (role === "hospital") { await loadRequests(); renderHospital(); }
  else if (role === "donor") { await loadDonor(); renderDonor(); }
  else { await loadAdmin(); renderAdmin(); }
}

/* ---------- hospital ---------- */
async function loadRequests() { state.requests = (await api("/requests")).requests; }

function requestForm() {
  return `<div class="card"><h2>New request</h2>
  <form id="reqForm" novalidate>
    <label for="patient_ref">Patient reference (no names)</label><input id="patient_ref" placeholder="PT-10300">
    <div class="row2"><div><label for="kind">Type</label><select id="kind"><option value="blood">Blood</option><option value="organ">Organ</option></select></div>
    <div><label for="blood_group">Blood group</label><select id="blood_group">${opts(GROUPS, "A+")}</select></div></div>
    <div id="bloodFields"><label for="units_needed">Units needed</label><input id="units_needed" type="number" min="1" max="10" value="1"></div>
    <div id="organFields" hidden>
      <div class="row2"><div><label for="organ">Organ</label><select id="organ">${opts(ORGANS)}</select></div>
      <div><label for="patient_age">Patient age</label><input id="patient_age" type="number" min="0" max="100"></div></div>
      <label for="hla">HLA antigens (comma separated)</label><input id="hla" placeholder="A2,A24,B7,B8,DR3,DR4"></div>
    <label for="urgency">Urgency: <span id="urgVal">3</span> / 5</label><input id="urgency" type="range" min="1" max="5" value="3">
    <label for="city">Hospital city</label><select id="city">${opts(Object.keys(CITIES))}</select>
    <div class="err" id="reqErr"></div>
    <button class="btn block" type="submit">Create request</button>
  </form></div>`;
}

function requestList() {
  if (!state.requests.length) return `<div class="empty">No requests yet.</div>`;
  return state.requests.map((r) => `
    <div class="req ${state.selected === r.id ? "sel" : ""}" data-select="${r.id}">
      <div><b>${esc(r.patient_ref)}</b> ${chip(r.blood_group, "group")} ${chip(r.kind === "organ" ? r.organ : r.units_needed + " unit(s) blood", "")}<br>
      <small>${esc(r.city)} · <span class="dots" title="Urgency ${r.urgency}/5">${dots(r.urgency)}</span> · priority ${r.priority}</small></div>
      <div style="text-align:right">${chip(r.status)}<br><button class="btn small" style="margin-top:.35rem" data-match="${r.id}" ${["fulfilled", "cancelled"].includes(r.status) ? "disabled" : ""}>Find matches</button></div>
    </div>`).join("");
}

function matchPanel() {
  const req = state.requests.find((r) => r.id === state.selected);
  if (!req) return `<div class="card"><h2>Matches</h2><div class="empty">Select a request, then press “Find matches”.</div></div>`;
  const win = req.kind === "organ" ? ` · viability window ${WINDOWS[req.organ]} h` : "";
  const rej = state.rejected && Object.keys(state.rejected).length
    ? `<h3>Why other donors were excluded</h3><div class="rejected">${Object.entries(state.rejected).map(([k, v]) => `<span class="chip">${esc(k)} × ${v}</span>`).join("")}</div>` : "";
  const rows = state.matches.map((m, i) => `
    <tr data-toggle="${m.id}" style="cursor:pointer">
      <td>${i + 1}</td><td><b>${esc(m.name || m.code)}</b>${m.name ? `<br><small class="muted">${esc(m.code)}</small>` : ""}</td>
      <td>${chip(m.blood_group, "group")}</td><td>${esc(m.city)}</td><td>${m.distance_km} km</td>
      <td>${m.transport_h != null ? m.transport_h + " h" : "-"}</td>
      <td><div class="scorebar"><i style="width:${Math.min(100, m.score)}%"></i><b>${m.score}</b></div></td>
      <td>${chip(m.status)}</td>
      <td>${m.status === "accepted" ? `<button class="btn good small" data-fulfil="${m.id}">Mark fulfilled</button>` : ""}</td></tr>
    ${state.open.has(m.id) ? `<tr class="break"><td colspan="9">${m.breakdown.map((b) => `<div class="seg"><span>${esc(b.label)}</span><span class="bar"><i style="width:${(b.points / b.max) * 100}%"></i></span><span>${b.points} / ${b.max}</span></div>`).join("")}</td></tr>` : ""}`).join("");
  return `<div class="card"><h2>Ranked matches for ${esc(req.patient_ref)}</h2>
    <p class="muted" style="margin-top:0">${esc(req.kind === "organ" ? req.organ : "blood")} · group ${esc(req.blood_group)}${win}. Click a row to see how its score was built.</p>${rej}
    ${state.matches.length ? `<table><thead><tr><th>#</th><th>Donor</th><th>Group</th><th>City</th><th>Distance</th><th>Transit</th><th>Score</th><th>Status</th><th></th></tr></thead><tbody>${rows}</tbody></table>
    <div class="note">Donor names stay hidden until the donor accepts the offer.</div>` : `<div class="empty">No eligible donors yet. Press “Find matches” to run the engine.</div>`}</div>`;
}

function renderHospital() {
  shell(`<div class="grid cols"><div>${requestForm()}</div><div class="grid"><div class="card"><h2>Requests (by priority)</h2>${requestList()}</div>${matchPanel()}</div></div>`);
  bindRequestForm();
}

function bindRequestForm() {
  const form = document.getElementById("reqForm");
  const sync = () => {
    const organ = form.kind.value === "organ";
    document.getElementById("organFields").hidden = !organ;
    document.getElementById("bloodFields").hidden = organ;
  };
  form.kind.addEventListener("change", sync);
  form.urgency.addEventListener("input", () => { document.getElementById("urgVal").textContent = form.urgency.value; });
  sync();
}

async function createRequest(form) {
  const [lat, lng] = CITIES[form.city.value];
  const body = { patient_ref: form.patient_ref.value, kind: form.kind.value, blood_group: form.blood_group.value,
                 urgency: Number(form.urgency.value), city: form.city.value, lat, lng };
  if (body.kind === "blood") body.units_needed = Number(form.units_needed.value);
  else { body.organ = form.organ.value; body.hla = form.hla.value; if (form.patient_age.value) body.patient_age = Number(form.patient_age.value); }
  try {
    const { request } = await api("/requests", "POST", body);
    toast("Request created");
    await refreshHospital(request.id);
  } catch (e) { document.getElementById("reqErr").textContent = e.message; }
}

async function refreshHospital(selectId) {
  await loadRequests();
  state.stats = (await api("/stats")).stats;
  if (selectId) state.selected = selectId;
  if (state.selected) state.matches = (await api(`/requests/${state.selected}/matches`)).matches;
  renderHospital();
}

async function runMatch(id) {
  try {
    const data = await api(`/requests/${id}/match`, "POST");
    state.selected = id; state.rejected = data.rejected; state.open.clear();
    await loadRequests(); state.matches = data.matches;
    toast(`${data.candidates} eligible donor(s) found`);
    renderHospital();
  } catch (e) { toast(e.message, true); }
}

/* ---------- donor ---------- */
async function loadDonor() {
  try { state.donor = (await api("/donors/me")).donor; } catch (e) { state.donor = null; }
  state.offers = (await api("/donors/me/offers")).offers;
}

function donorForm() {
  const d = state.donor || { blood_group: "O+", age: 25, weight_kg: 60, donor_type: "blood", organs_pledged: [], hla: "", city: "Bengaluru", last_donation_date: "", available: true };
  return `<div class="card"><h2>${state.donor ? "My donor profile" : "Create your donor profile"}</h2>
  <form id="donorForm" novalidate>
    <div class="row2"><div><label for="blood_group">Blood group</label><select id="blood_group">${opts(GROUPS, d.blood_group)}</select></div>
    <div><label for="donor_type">I want to donate</label><select id="donor_type">${["blood", "organ", "both"].map((t) => `<option value="${t}" ${t === d.donor_type ? "selected" : ""}>${t}</option>`).join("")}</select></div></div>
    <div class="row2"><div><label for="age">Age</label><input id="age" type="number" value="${esc(d.age)}"></div>
    <div><label for="weight_kg">Weight (kg)</label><input id="weight_kg" type="number" value="${esc(d.weight_kg)}"></div></div>
    <label>Organs I pledge</label><div class="checks">${ORGANS.map((o) => `<label><input type="checkbox" name="organ" value="${o}" ${d.organs_pledged.includes(o) ? "checked" : ""}>${o}</label>`).join("")}</div>
    <label for="hla">HLA antigens (optional)</label><input id="hla" value="${esc(d.hla)}" placeholder="A2,A24,B7,B8,DR3,DR4">
    <div class="row2"><div><label for="city">City</label><select id="city">${opts(Object.keys(CITIES), d.city)}</select></div>
    <div><label for="last_donation_date">Last blood donation</label><input id="last_donation_date" type="date" value="${esc(d.last_donation_date || "")}"></div></div>
    <div class="checks"><label><input id="available" type="checkbox" ${d.available ? "checked" : ""}>Available for matching</label></div>
    <div class="err" id="donorErr"></div>
    <button class="btn block" type="submit">Save profile</button>
  </form></div>`;
}

function offersHtml() {
  if (!state.offers.length) return `<div class="empty">No offers yet. Hospitals will send you a request when your profile is a good fit.</div>`;
  return state.offers.map((o) => `
    <div class="req" style="cursor:default"><div><b>${esc(o.hospital)}</b> ${chip(o.blood_group, "group")} ${chip(o.kind === "organ" ? o.organ : o.units_needed + " unit(s) blood", "")}<br>
      <small>${esc(o.city)} · ${o.distance_km} km away · urgency <span class="dots">${dots(o.urgency)}</span> · match score ${o.score}</small></div>
      <div style="text-align:right">${o.status === "proposed"
        ? `<button class="btn good small" data-respond="${o.id}|accept">Accept</button> <button class="btn ghost small" data-respond="${o.id}|decline">Decline</button>` : chip(o.status)}</div></div>`).join("");
}

function renderDonor() {
  shell(`<div class="grid cols"><div>${donorForm()}</div><div class="card"><h2>My offers</h2>${offersHtml()}
    <div class="note">Your name is shared with a hospital only after you accept an offer. After a blood donation is recorded you rest for 90 days before new offers arrive.</div></div></div>`);
}

async function saveDonor(form) {
  const [lat, lng] = CITIES[form.city.value];
  const body = { blood_group: form.blood_group.value, donor_type: form.donor_type.value, age: Number(form.age.value),
    weight_kg: Number(form.weight_kg.value), organs_pledged: [...form.querySelectorAll("input[name=organ]:checked")].map((c) => c.value),
    hla: form.hla.value, city: form.city.value, lat, lng, last_donation_date: form.last_donation_date.value || null,
    available: form.available.checked };
  try { state.donor = (await api("/donors/me", "PUT", body)).donor; toast("Profile saved"); state.stats = (await api("/stats")).stats; renderDonor(); }
  catch (e) { document.getElementById("donorErr").textContent = e.message; }
}

/* ---------- admin ---------- */
async function loadAdmin() {
  state.audit = (await api("/audit")).entries;
  state.requests = (await api("/requests")).requests;
}

function renderAdmin() {
  const groups = state.stats.donors_by_group, max = Math.max(1, ...Object.values(groups));
  const v = state.verify;
  shell(`<div class="grid cols"><div class="card"><h2>Available donors by blood group</h2><div class="bars">${GROUPS.map((g) => `<div><span>${g}</span><i style="width:${((groups[g] || 0) / max) * 100}%;min-width:3px"></i>${groups[g] || 0}</div>`).join("")}</div></div>
  <div class="card"><h2>Tamper-evident audit trail</h2>
    <p class="muted" style="margin-top:0">Every action is chained to the previous one with SHA-256, so editing history is detectable.</p>
    <button class="btn small" data-action="verify">Verify chain</button>
    ${v ? ` ${chip(v.valid ? "Chain intact · " + v.entries + " entries" : "Tampering at entry " + v.first_bad_entry, v.valid ? "fulfilled" : "cancelled")}` : ""}
    <table style="margin-top:.8rem"><thead><tr><th>#</th><th>Time (UTC)</th><th>Actor</th><th>Action</th><th>Hash</th></tr></thead><tbody>
    ${state.audit.slice(0, 12).map((a) => `<tr><td>${a.id}</td><td>${esc(a.ts.replace("T", " "))}</td><td>${esc(a.actor)}</td><td>${esc(a.action)}</td><td class="hash">${esc(a.hash.slice(0, 14))}…</td></tr>`).join("")}</tbody></table></div></div>`);
}

/* ---------- events ---------- */
document.addEventListener("click", async (ev) => {
  const t = ev.target.closest("[data-tab],[data-demo],[data-action],[data-select],[data-match],[data-toggle],[data-fulfil],[data-respond]");
  if (!t) return;
  const d = t.dataset;
  try {
    if (d.tab) { state.authTab = d.tab; renderAuth(); }
    else if (d.demo) { const [e, p] = d.demo.split("|"); document.getElementById("email").value = e; document.getElementById("password").value = p; }
    else if (d.action === "logout") logout();
    else if (d.action === "verify") { state.verify = await api("/audit/verify"); renderAdmin(); }
    else if (d.match) { ev.stopPropagation(); await runMatch(Number(d.match)); }
    else if (d.select) { state.selected = Number(d.select); state.rejected = null; state.open.clear(); state.matches = (await api(`/requests/${state.selected}/matches`)).matches; renderHospital(); }
    else if (d.toggle) { const id = Number(d.toggle); state.open.has(id) ? state.open.delete(id) : state.open.add(id); renderHospital(); }
    else if (d.fulfil) { await api(`/matches/${d.fulfil}/fulfil`, "POST"); toast("Donation recorded"); await refreshHospital(); }
    else if (d.respond) { const [id, decision] = d.respond.split("|"); await api(`/matches/${id}/respond`, "POST", { decision }); toast(decision === "accept" ? "Thank you. The hospital has been notified." : "Offer declined"); await loadDonor(); renderDonor(); }
  } catch (e) { toast(e.message, true); }
});

document.addEventListener("submit", (ev) => {
  ev.preventDefault();
  const f = ev.target;
  if (f.id === "authForm") submitAuth(f);
  else if (f.id === "reqForm") createRequest(f);
  else if (f.id === "donorForm") saveDonor(f);
});

(async function boot() {
  const saved = load("ll_token");
  if (!saved) return renderAuth();
  state.token = saved;
  try { state.user = (await api("/auth/me")).user; await enter(); } catch (e) { logout(); }
})();
