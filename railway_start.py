import re
import runpy
from pathlib import Path

from message_reactions_patch import patch_app
import premium_antibots

ROOT = Path(__file__).resolve().parent
APP_FILE = ROOT / "app.py"

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
runpy.run_path(str(APP_FILE), run_name="__main__", init_globals={"premium_system": __import__("premium_system")})
