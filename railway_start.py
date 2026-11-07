import re
import runpy
from pathlib import Path

from message_reactions_patch import patch_app
from premium_backup_patch import patch_app_file

ROOT = Path(__file__).resolve().parent
APP_FILE = ROOT / "app.py"

# app.py usa este valor para guardar el canal del panel de tickets.
source = APP_FILE.read_text(encoding="utf-8")
start = source.find("CONFIG_DEFAULTS = {")
if start < 0:
    raise RuntimeError("No encontré CONFIG_DEFAULTS en app.py.")
end = source.find("\n}", start)
if end < 0:
    raise RuntimeError("CONFIG_DEFAULTS en app.py no parece estar cerrado correctamente.")
defaults = source[start:end]
if '"ticket_panel"' not in defaults and "'ticket_panel'" not in defaults:
    updated, count = re.subn(r'("antilink"\s*:\s*\{\}\s*,?)', r'\1 "ticket_panel": {},', defaults, count=1)
    if count == 1:
        source = source[:start] + updated + source[end:]
        APP_FILE.write_text(source, encoding="utf-8")

patch_app(APP_FILE)
patch_app_file(APP_FILE)
runpy.run_path(str(APP_FILE), run_name="__main__", init_globals={"premium_system": __import__("premium_system")})
