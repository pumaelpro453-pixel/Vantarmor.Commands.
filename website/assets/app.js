const $ = (selector) => document.querySelector(selector);
const toast = (message) => { const el = $("#toast"); if (!el) return; el.textContent = message; el.classList.add("show"); setTimeout(() => el.classList.remove("show"), 3000); };
async function api(path) { try { const response = await fetch(path, { credentials: "same-origin", cache: "no-store" }); return { response, data: await response.json() }; } catch { return { response: { ok: false }, data: {} }; } }
function setInvite(config) { const select = $("#guild-select"); const button = $("#invite-button"); if (!button) return; button.href = config.invite_url || `https://discord.com/oauth2/authorize?client_id=${encodeURIComponent(config.bot_client_id || "")}&scope=bot%20applications.commands&permissions=8`; button.target = "_blank"; button.rel = "noopener"; if (!select) return; select.addEventListener("change", () => { const url = new URL(button.href); if (select.value) { url.searchParams.set("guild_id", select.value); url.searchParams.set("disable_guild_select", "true"); } else { url.searchParams.delete("guild_id"); url.searchParams.delete("disable_guild_select"); } button.href = url.toString(); }); }
async function boot() {
  const menu = $("#menu-toggle"); if (menu) menu.addEventListener("click", () => { const nav = $("#nav"); nav.classList.toggle("open"); menu.setAttribute("aria-expanded", String(nav.classList.contains("open"))); });
  const configResult = await api("/config.json"); const config = configResult.data || {}; setInvite(config);
  const statsResult = await api("/api/stats"); if (statsResult.response.ok) { $("#server-count").textContent = Number(statsResult.data.servers || 0).toLocaleString("es"); $("#web-count").textContent = Number(statsResult.data.website_users || 0).toLocaleString("es"); }
  const me = await api("/api/me");
  if (me.response.ok && me.data.authenticated) {
    const user = me.data.user || {}; $("#profile-name").textContent = user.name || user.username || "Cuenta de Discord"; $("#profile-status").textContent = `${user.username ? `@${user.username} · ` : ""}${me.data.premium ? "Premium activo" : "Plan Free"}`;
    const avatar = $(".avatar"); if (avatar && user.avatar) { const image = document.createElement("img"); image.src = user.avatar; image.alt = "Avatar de Discord"; image.className = "avatar"; avatar.replaceWith(image); }
    $("#profile-login").hidden = true; $("#account-actions").innerHTML = '<a class="secondary button button-small" href="/auth/logout">Cerrar sesión</a>'; if (me.data.is_admin) $("#admin-link").hidden = false;
    const guildResult = await api("/api/guilds"); const select = $("#guild-select"); if (select && guildResult.response.ok) { select.replaceChildren(new Option("Elige un servidor (opcional)", ""), ...guildResult.data.guilds.map((guild) => new Option(guild.name, guild.id))); }
  }
}
boot();
