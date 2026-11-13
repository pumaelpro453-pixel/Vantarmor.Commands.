const byId = (id) => document.getElementById(id);
let csrf = "";
let people = [];

async function api(url, options = {}) {
  const response = await fetch(url, { credentials: "same-origin", ...options, headers: { "Content-Type": "application/json", ...(options.headers || {}) } });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || data.message || `Error HTTP ${response.status}`);
  return data;
}

function showStatus(text, error = false) {
  const el = byId("status");
  el.textContent = text;
  el.style.color = error ? "#ff8585" : "#a6f3c2";
}

function renderUsers() {
  const tbody = byId("users");
  tbody.replaceChildren();
  const select = byId("user-select");
  select.replaceChildren();
  for (const user of people) {
    const option = document.createElement("option");
    option.value = user.id;
    option.textContent = `${user.id}${user.premium ? " · Premium activo" : ""}`;
    select.append(option);
    const row = document.createElement("tr");
    const idCell = document.createElement("td"); idCell.textContent = user.id;
    const premiumCell = document.createElement("td"); premiumCell.textContent = user.premium ? "Activo" : "No activo";
    const expiryCell = document.createElement("td"); expiryCell.textContent = user.expires_at == null ? (user.premium ? "Permanente" : "—") : new Date(user.expires_at * 1000).toLocaleString();
    const actionCell = document.createElement("td");
    if (user.premium) {
      const button = document.createElement("button"); button.type = "button"; button.className = "danger"; button.textContent = "Revocar";
      button.addEventListener("click", () => changePremium("/api/admin/revoke", { user_id: user.id }));
      actionCell.append(button);
    } else actionCell.textContent = "—";
    row.append(idCell, premiumCell, expiryCell, actionCell); tbody.append(row);
  }
  if (!people.length) {
    const row = document.createElement("tr"); const cell = document.createElement("td"); cell.colSpan = 4; cell.textContent = "Aún no hay usuarios registrados."; row.append(cell); tbody.append(row);
  }
}

async function loadUsers() {
  const result = await api("/api/admin/users");
  people = result.users;
  renderUsers();
}

async function changePremium(endpoint, payload) {
  try {
    const result = await api(endpoint, { method: "POST", headers: { "X-CSRF-Token": csrf }, body: JSON.stringify(payload) });
    showStatus(result.message);
    await loadUsers();
  } catch (error) { showStatus(error.message, true); }
}

async function init() {
  try {
    const me = await api("/api/me");
    csrf = me.csrf;
    if (!me.is_admin) { byId("denied").hidden = false; return; }
    byId("dashboard").hidden = false;
    await loadUsers();
  } catch (_) {
    byId("login").hidden = false;
  }
}

byId("grant-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const permanent = byId("permanent").checked;
  await changePremium("/api/admin/grant", { user_id: byId("user-select").value, permanent, days: Number(byId("days").value) });
});
byId("permanent").addEventListener("change", (event) => { byId("days").disabled = event.target.checked; });
byId("refresh").addEventListener("click", () => loadUsers().catch((error) => showStatus(error.message, true)));
init();
