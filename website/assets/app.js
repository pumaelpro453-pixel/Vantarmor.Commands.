const $ = (selector) => document.querySelector(selector);
const tabSections = [...document.querySelectorAll("main > section[id]")];
const nav = $("#nav");
const menuToggle = $("#menu-toggle");

function activateTab(id, { updateHash = true } = {}) {
  const active = tabSections.find((section) => section.id === id) || tabSections[0];
  for (const section of tabSections) {
    const selected = section === active;
    section.hidden = !selected;
    section.classList.toggle("active-tab", selected);
    section.setAttribute("role", "tabpanel");
    section.setAttribute("aria-hidden", String(!selected));
  }
  if (nav) {
    for (const link of nav.querySelectorAll("a[href^='#']")) {
      const selected = link.hash === `#${active.id}`;
      link.classList.toggle("active", selected);
      link.setAttribute("aria-current", selected ? "page" : "false");
    }
    nav.classList.remove("open");
  }
  menuToggle?.setAttribute("aria-expanded", "false");
  if (updateHash && location.hash !== `#${active.id}`) history.replaceState(null, "", `#${active.id}`);
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function toast(message) {
  const el = $("#toast");
  if (!el) return;
  el.textContent = message;
  el.classList.add("show");
  setTimeout(() => el.classList.remove("show"), 3000);
}

async function api(path) {
  try {
    const response = await fetch(path, { credentials: "same-origin", cache: "no-store" });
    return { response, data: await response.json() };
  } catch {
    return { response: { ok: false }, data: {} };
  }
}

function configureInvite(config) {
  const select = $("#guild-select");
  const button = $("#invite-button");
  if (!button) return;
  button.href = config.invite_url || `https://discord.com/oauth2/authorize?client_id=${encodeURIComponent(config.bot_client_id || "")}&scope=bot%20applications.commands&permissions=8`;
  button.target = "_blank";
  button.rel = "noopener";
  select?.addEventListener("change", () => {
    const url = new URL(button.href);
    if (select.value) {
      url.searchParams.set("guild_id", select.value);
      url.searchParams.set("disable_guild_select", "true");
    } else {
      url.searchParams.delete("guild_id");
      url.searchParams.delete("disable_guild_select");
    }
    button.href = url.toString();
  });
}

async function boot() {
  const initialId = location.hash.slice(1);
  activateTab(initialId, { updateHash: false });
  nav?.addEventListener("click", (event) => {
    const link = event.target.closest("a[href^='#']");
    if (!link) return;
    event.preventDefault();
    activateTab(link.hash.slice(1));
  });
  document.querySelectorAll("a[href^='#']").forEach((link) => {
    if (nav?.contains(link)) return;
    link.addEventListener("click", (event) => {
      event.preventDefault();
      activateTab(link.hash.slice(1));
    });
  });
  menuToggle?.addEventListener("click", () => {
    const open = nav.classList.toggle("open");
    menuToggle.setAttribute("aria-expanded", String(open));
  });

  const config = (await api("/config.json")).data || {};
  configureInvite(config);
  const stats = await api("/api/stats");
  if (stats.response.ok) {
    $("#server-count").textContent = Number(stats.data.servers || 0).toLocaleString("es");
    $("#web-count").textContent = Number(stats.data.website_users || 0).toLocaleString("es");
  }
  const me = await api("/api/me");
  if (!me.response.ok || !me.data.authenticated) return;

  const user = me.data.user || {};
  $("#profile-name").textContent = user.name || user.username || "Cuenta de Discord";
  $("#profile-status").textContent = `${user.username ? `@${user.username} · ` : ""}${me.data.premium ? "Premium activo" : "Plan Free"}`;
  const avatar = $(".avatar");
  if (avatar && user.avatar) {
    const image = document.createElement("img");
    image.src = user.avatar;
    image.alt = "Avatar de Discord";
    image.className = "avatar";
    avatar.replaceWith(image);
  }
  $("#profile-login").hidden = true;
  $("#account-actions").innerHTML = '<a class="button secondary button-small" href="/auth/logout">Cerrar sesión</a>';
  if (me.data.is_admin) $("#admin-link").hidden = false;

  const guilds = await api("/api/guilds");
  const select = $("#guild-select");
  if (select && guilds.response.ok) {
    select.replaceChildren(new Option("Elige un servidor (opcional)", ""), ...guilds.data.guilds.map((guild) => new Option(guild.name, guild.id)));
  }
}

boot();
