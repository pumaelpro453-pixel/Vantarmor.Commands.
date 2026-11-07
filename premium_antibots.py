from pathlib import Path


def patch_app_file(app_file: Path):
    source = app_file.read_text(encoding="utf-8")

    if "premium_backup_system" not in source:
        source = source.replace(
            "from discord import app_commands\n",
            "from discord import app_commands\nfrom premium_backup_system import (\n    BackupRestoreView,\n    is_premium_user,\n    premium_backup_scheduler,\n    save_server_snapshot,\n)\n",
            1,
        )

    marker = '@tree.command(name="ping", description="Comprueba si el bot responde", guild=GUILD)\n'
    if 'name="seguridad-copia"' not in source:
        source = source.replace(
            marker,
            '''@tree.command(name="seguridad-copia", description="Guarda una copia segura del servidor para usuarios premium", guild=GUILD)
@app_commands.default_permissions(administrator=True)
async def seguridad_copia(interaction: discord.Interaction):
    if interaction.guild is None or not isinstance(interaction.user, discord.Member):
        await interaction.response.send_message("Úsalo dentro de un servidor.", ephemeral=True)
        return
    if not is_premium_user(interaction.user.id):
        await interaction.response.send_message("Este comando es premium. Activa tu plan premium para usarlo.", ephemeral=True)
        return
    if not (interaction.user.id == interaction.guild.owner_id or interaction.user.guild_permissions.administrator):
        await interaction.response.send_message("Necesitas ser propietario o administrador del servidor.", ephemeral=True)
        return
    snapshot = await save_server_snapshot(interaction.guild)
    await interaction.response.send_message(
        f"✅ Copia de seguridad creada para **{interaction.guild.name}**.\nCuando quieras, puedes restaurarla con el botón de abajo.",
        view=BackupRestoreView(interaction.guild.id),
    )

'''+marker,
            1,
        )

    if 'asyncio.create_task(premium_backup_scheduler(client))' not in source:
        source = source.replace(
            '    try:\n        commands = await tree.sync(guild=GUILD)\n        print(f"Comandos sincronizados: {len(commands)}")\n    except Exception as error:\n        print(f"Error al sincronizar comandos: {error}")\n',
            '    try:\n        asyncio.create_task(premium_backup_scheduler(client))\n        commands = await tree.sync(guild=GUILD)\n        print(f"Comandos sincronizados: {len(commands)}")\n    except Exception as error:\n        print(f"Error al sincronizar comandos: {error}")\n',
            1,
        )

    app_file.write_text(source, encoding="utf-8")


__all__ = ["patch_app_file"]
