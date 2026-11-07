from pathlib import Path


IMPORTS = '''from premium_backup_system import (
    BackupRestoreView,
    is_premium_user,
    premium_backup_scheduler,
    save_server_snapshot,
)
'''

COMMAND = '''@tree.command(name="seguridad-copia", description="Guarda una copia de la estructura del servidor", guild=GUILD)
@app_commands.default_permissions(administrator=True)
async def seguridad_copia(interaction: discord.Interaction):
    guild = interaction.guild
    member = interaction.user
    if guild is None or not isinstance(member, discord.Member):
        await interaction.response.send_message("Este comando solo funciona en un servidor.", ephemeral=True)
        return
    if not is_premium_user(member.id):
        await interaction.response.send_message("Tu cuenta no tiene Premium activo.", ephemeral=True)
        return
    if not (member.id == guild.owner_id or member.guild_permissions.administrator):
        await interaction.response.send_message("Necesitas ser propietario o administrador del servidor.", ephemeral=True)
        return
    await save_server_snapshot(guild)
    await interaction.response.send_message(
        f"✅ Copia de seguridad guardada para **{guild.name}**.\nLa restauración solo recrea categorías y canales que falten; no elimina canales existentes.",
        view=BackupRestoreView(guild.id),
        ephemeral=True,
    )


'''


def patch_app_file(app_file: Path):
    source = app_file.read_text(encoding="utf-8")

    if "from premium_backup_system import (" not in source:
        anchor = "from discord import app_commands\n"
        if anchor not in source:
            raise RuntimeError("No encontré el punto de importación en app.py.")
        source = source.replace(anchor, anchor + IMPORTS, 1)

    if 'name="seguridad-copia"' not in source:
        anchor = '@tree.command(name="ping", description="Comprueba si el bot responde", guild=GUILD)\n'
        if anchor not in source:
            raise RuntimeError("No encontré el comando ping para insertar /seguridad-copia.")
        source = source.replace(anchor, COMMAND + anchor, 1)

    on_ready_anchor = '    print(f"Conectado como {client.user}")\n'
    on_ready_setup = '''    if not getattr(client, "premium_backup_views_registered", False):
        for server in client.guilds:
            client.add_view(BackupRestoreView(server.id))
        client.premium_backup_views_registered = True
    backup_task = getattr(client, "premium_backup_task", None)
    if backup_task is None or backup_task.done():
        client.premium_backup_task = asyncio.create_task(premium_backup_scheduler(client))
'''
    if "premium_backup_views_registered" not in source:
        if on_ready_anchor not in source:
            raise RuntimeError("No encontré el inicio de on_ready en app.py.")
        source = source.replace(on_ready_anchor, on_ready_anchor + on_ready_setup, 1)

    app_file.write_text(source, encoding="utf-8")


__all__ = ["patch_app_file"]
