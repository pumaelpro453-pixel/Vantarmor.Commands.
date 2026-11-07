import runpy
from pathlib import Path

from message_reactions_patch import patch_app as patch_message_features
from premium_backup_patch import patch_app_file as patch_premium_features

ROOT = Path(__file__).resolve().parent
APP_FILE = ROOT / "app.py"


def main():
    if not APP_FILE.is_file():
        raise FileNotFoundError(f"No encontré el archivo del bot: {APP_FILE}")

    # Both patchers are idempotent and must run before app.py is imported/executed.
    patch_message_features(APP_FILE)
    patch_premium_features(APP_FILE)

    print("Iniciando app.py con funciones Premium de copia de seguridad...")
    runpy.run_path(str(APP_FILE), run_name="__main__")


if __name__ == "__main__":
    main()
