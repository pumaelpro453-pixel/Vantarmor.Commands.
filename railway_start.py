import json
import os
import re
import runpy
import secrets
import threading
import time
from http.cookies import SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

from message_reactions_patch import patch_app
import premium_antibots

ROOT = Path(__file__).resolve().parent
APP_FILE = ROOT / "app.py"
WEB_DIR = ROOT / "website"
DISCORD_API = "https://discord.com/api/v10"
DEFAULT_CLIENT_ID = "1567331667826311288"
PUBLIC_DOMAIN = "vantarmors-production.up.railway.app"
DEFAULT_REDIRECT_URI = f"https://{PUBLIC_DOMAIN}/auth/callback"
SESSIONS = {}
SESSIONS_LOCK = threading.RLock()


def oauth_settings():
    return {
        "client_id": os.getenv("DISCORD_CLIENT_ID", DEFAULT_CLIENT_ID).strip(),
        "client_secret": os.getenv("DISCORD_CLIENT_SECRET", "").strip(),
        "redirect_uri": os.getenv("DISCORD_REDIRECT_URI", DEFAULT_REDIRECT_URI).strip(),
    }


def get_cookie(handler, name):
    cookie = SimpleCookie()
    try:
        cookie.load(handler.headers.get("Cookie", ""))
        morsel = cookie.get(name)
        return morsel.value if morsel else None
    except (TypeError, ValueError):
        return None


def discord_request(path, access_token):
    request = Request(f"{DISCORD_API}{path}", headers={
        "Authorization": f"Bearer {access_token}", "Accept": "application/json",
        "User-Agent": f"Vantarmor (https://{PUBLIC_DOMAIN}, 1.0)",
    })
    with urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def exchange_code(code, settings):
    import base64
    body = urlencode({"grant_type": "authorization_code", "code": code, "redirect_uri": settings["redirect_uri"]}).encode("utf-8")
    credentials = base64.b64encode(f"{settings['client_id']}:{settings['client_secret']}".encode("utf-8")).decode("ascii")
    request = Request(f"{DISCORD_API}/oauth2/token", data=body, headers={
        "Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json",
        "User-Agent": f"Vantarmor (https://{PUBLIC_DOMAIN}, 1.0)", "Authorization": f"Basic {credentials}",
    }, method="POST")
    with urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def discord_error_details(error):
    try:
        payload = json.loads(error.read(4096).decode("utf-8", errors="replace"))
    except (OSError, ValueError):
        payload = {}
    code = str(payload.get("error") or payload.get("code") or "unknown")[:80]
    description = " ".join(str(payload.get("error_description") or payload.get("message") or "").split())[:240] or "Sin cuerpo JSON"
    headers = getattr(error, "headers", {})
    metadata = {key: str(headers.get(key, ""))[:120] for key in ("Content-Type", "Server", "CF-Ray", "Retry-After") if headers.get(key)}
    return code, description, metadata


def oauth_failure_message(stage, status, code):
    if code == "invalid_client":
        return "Discord rechazó las credenciales de la aplicación (invalid_client). Comprueba que el Client ID y Client Secret sean de la misma aplicación."
    if code == "invalid_grant":
        return "Discord rechazó el código de autorización. Reintenta y comprueba la URL de retorno configurada en Railway y Discord."
    if stage == "profile":
        return f"El inicio de sesión fue aceptado, pero Discord rechazó la consulta del perfil (HTTP {status}). Vuelve a iniciar sesión."
    return f"Discord rechazó el intercambio OAuth (HTTP {status}, {code}). Comprueba los logs de Railway."


def session_for(handler):
    session_id = get_cookie(handler, "vantarmor_session")
    if not session_id:
        return None
    with SESSIONS_LOCK:
        session = SESSIONS.get(session_id)
        if session and session["expires_at"] > time.time():
            return session
        SESSIONS.pop(session_id, None)
    return None


class WebsiteHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def send_json(self, data, status=200):
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(payload)

    def send_text(self, text, status=400):
        payload = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(payload)

    @staticmethod
    def cookie_header(name, value, max_age):
        return f"{name}={value}; Path=/; Max-Age={max_age}; HttpOnly; Secure; SameSite=Lax"

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/config.json":
            settings = oauth_settings()
            self.send_json({"auth_enabled": bool(all(settings.values())), "support_url": os.getenv("SUPPORT_URL", "")})
            return
        if path == "/auth/discord":
            settings = oauth_settings()
            if not all(settings.values()):
                self.send_text("Falta configurar Discord OAuth en Railway.", 503)
                return
            state = secrets.token_urlsafe(32)
            query = urlencode({"client_id": settings["client_id"], "response_type": "code", "redirect_uri": settings["redirect_uri"], "scope": "identify guilds", "state": state})
            self.send_response(302)
            self.send_header("Location", f"https://discord.com/oauth2/authorize?{query}")
            self.send_header("Set-Cookie", self.cookie_header("vantarmor_oauth_state", state, 600))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return
        if path == "/auth/callback":
            query = parse_qs(urlparse(self.path).query)
            state = query.get("state", [""])[0]
            expected = get_cookie(self, "vantarmor_oauth_state")
            code = query.get("code", [""])[0]
            if not expected or not state or not secrets.compare_digest(state, expected):
                self.send_text("La verificación de seguridad falló. Vuelve a iniciar sesión desde la web.", 400)
                return
            if query.get("error") or not code:
                self.send_text("No se autorizó el acceso a Discord. Vuelve a intentarlo desde la web.", 400)
                return
            settings = oauth_settings()
            if not all(settings.values()):
                self.send_text("Falta configurar Discord OAuth en Railway.", 503)
                return
            stage = "token_exchange"
            try:
                token_data = exchange_code(code, settings)
                access_token = token_data["access_token"]
                stage = "profile"
                user = discord_request("/users/@me", access_token)
                expires_in = max(60, int(token_data.get("expires_in", 3600)))
            except HTTPError as error:
                error_code, description, metadata = discord_error_details(error)
                print(f"Discord OAuth rechazado; etapa={stage}, HTTP={error.code}, error={error_code}, detalle={description}, respuesta={json.dumps(metadata, ensure_ascii=False)}")
                self.send_text(oauth_failure_message(stage, error.code, error_code), 502)
                return
            except (URLError, TimeoutError) as error:
                print(f"Discord OAuth no disponible; etapa={stage}, tipo={type(error).__name__}")
                self.send_text("No pudimos conectar con Discord. Espera un momento y vuelve a intentarlo.", 502)
                return
            except (KeyError, ValueError, TypeError) as error:
                print(f"Respuesta OAuth de Discord no válida; etapa={stage}, tipo={type(error).__name__}")
                self.send_text("Discord devolvió una respuesta inesperada. Vuelve a iniciar sesión.", 502)
                return
            session_id = secrets.token_urlsafe(32)
            with SESSIONS_LOCK:
                SESSIONS[session_id] = {"access_token": access_token, "user": {"id": str(user.get("id", "")), "username": user.get("global_name") or user.get("username", "Discord")}, "expires_at": time.time() + expires_in}
            self.send_response(302)
            self.send_header("Location", "/?connected=1")
            self.send_header("Set-Cookie", self.cookie_header("vantarmor_session", session_id, expires_in))
            self.send_header("Set-Cookie", self.cookie_header("vantarmor_oauth_state", "", 0))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return
        if path == "/api/me":
            session = session_for(self)
            if not session:
                self.send_json({"error": "unauthenticated"}, 401)
                return
            self.send_json({"user": session["user"]})
            return
        if path == "/api/guilds":
            session = session_for(self)
            if not session:
                self.send_json({"error": "unauthenticated"}, 401)
                return
            try:
                guilds = discord_request("/users/@me/guilds", session["access_token"])
            except HTTPError as error:
                code, description, metadata = discord_error_details(error)
                print(f"Consulta de servidores rechazada; HTTP={error.code}, error={code}, detalle={description}, respuesta={json.dumps(metadata, ensure_ascii=False)}")
                self.send_json({"error": "guild_lookup_failed"}, 502)
                return
            except (URLError, TimeoutError, ValueError) as error:
                print(f"Error al consultar servidores; tipo={type(error).__name__}")
                self.send_json({"error": "guild_lookup_failed"}, 502)
                return
            manageable = []
            for guild in guilds:
                try:
                    permissions = int(guild.get("permissions", "0"))
                except (TypeError, ValueError):
                    permissions = 0
                if guild.get("owner") or permissions & (0x8 | 0x20):
                    manageable.append({"id": str(guild.get("id", "")), "name": str(guild.get("name", "Servidor")), "icon": guild.get("icon"), "owner": bool(guild.get("owner"))})
            self.send_json({"guilds": manageable})
            return
        if path == "/auth/logout":
            session_id = get_cookie(self, "vantarmor_session")
            with SESSIONS_LOCK:
                SESSIONS.pop(session_id, None)
            self.send_response(302)
            self.send_header("Location", "/")
            self.send_header("Set-Cookie", self.cookie_header("vantarmor_session", "", 0))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return
        if path == "/" or path == "/index.html":
            html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
            script_tag = '<script src="/assets/navigation.js" defer></script>'
            if script_tag not in html:
                html = html.replace("</body>", f"  {script_tag}\n</body>", 1)
            payload = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(payload)
            return
        if path.startswith("/assets/"):
            return super().do_GET()
        if not session_for(self):
            self.send_json({"error": "authentication_required"}, 401)
            return
        super().do_GET()

    def log_message(self, format, *args):
        return


def start_website():
    if not (WEB_DIR / "index.html").is_file():
        print("No encontré website/index.html; no iniciaré la web.")
        return
    port = int(os.getenv("PORT", "7070"))
    server = ThreadingHTTPServer(("0.0.0.0", port), WebsiteHandler)
    threading.Thread(target=server.serve_forever, name="website", daemon=True).start()
    print(f"Web iniciada en el puerto {port}")


source = APP_FILE.read_text(encoding="utf-8")
start = source.find("CONFIG_DEFAULTS = {")
if start < 0:
    raise RuntimeError("No encontré CONFIG_DEFAULTS en app.py.")
end = source.find("\n}", start)
if end < 0:
    raise RuntimeError("CONFIG_DEFAULTS en app.py no parece estar cerrado correctamente.")
defaults = source[start:end]
for key in ("ticket_panel", "anti_bots"):
    if f'"{key}"' not in defaults and f"'{key}'" not in defaults:
        updated, count = re.subn(r'("antilink"\s*:\s*\{\}\s*,?)', rf'\1 "{key}": {{}},', defaults, count=1)
        if count == 1:
            source = source[:start] + updated + source[end:]
            APP_FILE.write_text(source, encoding="utf-8")
            start = source.find("CONFIG_DEFAULTS = {")
            end = source.find("\n}", start)
            defaults = source[start:end]
patch_app(APP_FILE)
premium_antibots.patch_app_file(APP_FILE)
start_website()
runpy.run_path(str(APP_FILE), run_name="__main__", init_globals={"premium_system": __import__("premium_system")})
