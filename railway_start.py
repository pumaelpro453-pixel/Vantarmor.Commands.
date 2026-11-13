import runpy
import threading
from pathlib import Path

from message_reactions_patch import patch_app as patch_message_features
from premium_backup_patch import patch_app_file as patch_premium_features
from premium_key_commands_patch import patch_app_file as remove_premium_key_commands
from web_server import start_website

ROOT = Path(__file__).resolve().parent
APP_FILE = ROOT / "app.py"


def main():
    if not APP_FILE.is_file():
        raise FileNotFoundError(f"No encontré el archivo del bot: {APP_FILE}")
    patch_message_features(APP_FILE)
    patch_premium_features(APP_FILE)
    remove_premium_key_commands(APP_FILE)
    start_website()
    print("Iniciando Vantarmor Commands...")
    runpy.run_path(str(APP_FILE), run_name="__main__")


if __name__ == "__main__":
    main()
