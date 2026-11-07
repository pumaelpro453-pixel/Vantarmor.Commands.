import asyncio
import json
import time
from pathlib import Path

import discord

PREMIUM_USERS_FILE = Path("premium_users.json")
BACKUP_FILE = Path("premium_backups.json")


def _load_json(path: Path, default):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default
    return data if isinstance(data, type(default)) else default


def _save_json(path: Path, data):
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def get_premium_users():
    return _load_json(PREMIUM_USERS_FILE, {})


def is_premium_user(user_id) -> bool:
    user_id = str(user_id)
    return bool(get_premium_users().get(user_id, False))


def set_premium_user(user_id, enabled: bool = True):
    users = get_premium_users()
    key = str(user_id)
    if enabled:
        users[key] = True
    else:
        users.pop(key, None)
    _save_json(PREMIUM_USERS_FILE, users)


def load_backups():
    return _load_json(BACKUP_FILE, {})


def _channel_key(channel) -> tuple:
    parent_name = channel.category.name if getattr(channel, "category", None) else ""
    return (parent_name, getattr(channel, "name", ""), str(getattr(channel, "type", "")))


async def save_server_snapshot(guild: discord.Guild):
    snapshot = {
        "guild_id": guild.id,
        "guild_name": guild.name,
        "created_at": int(time.time()),
        "categories": [],
        "channels": [],
    }

    for category in guild.categories:
        category_data = {
            "name": category.name,
            "position": category.position,
            "channels": [],
        }
        for channel in category.channels:
            channel_data = {
                "name": channel.name,
                "type": str(channel.type),
                "position": channel.position,
                "topic": getattr(channel, "topic", None),
                "nsfw": getattr(channel, "nsfw", False),
                "slowmode_delay": getattr(channel, "slowmode_delay", 0),
                "category": category.name,
            }
            category_data["channels"].append(channel_data)
        snapshot["categories"].append(category_data)

    for channel in guild.channels:
        if channel.category is not None:
            continue
        snapshot["channels"].append({
            "name": channel.name,
            "type": str(channel.type),
            "position": channel.position,
            "topic": getattr(channel, "topic", None),
            "nsfw": getattr(channel, "nsfw", False),
            "slowmode_delay": getattr(channel, "slowmode_delay", 0),
            "category": None,
        })

    backups = load_backups()
    backups[str(guild.id)] = snapshot
    _save_json(BACKUP_FILE, backups)
    return snapshot


async def restore_server_snapshot(guild: discord.Guild, snapshot=None):
    if snapshot is None:
        backup = load_backups().get(str(guild.id))
        if not backup:
            return False
        snapshot = backup

    snapshot_by_key = set()
    for category_data in snapshot.get("categories", []):
        for channel_data in category_data.get("channels", []):
            snapshot_by_key.add((category_data["name"], channel_data["name"], channel_data["type"]))
    for channel_data in snapshot.get("channels", []):
        snapshot_by_key.add(("", channel_data["name"], channel_data["type"]))

    for channel in list(guild.channels):
        if (channel.category.name if channel.category else "", channel.name, str(channel.type)) not in snapshot_by_key:
            try:
                await channel.delete(reason="Restauración premium de seguridad")
            except (discord.Forbidden, discord.HTTPException):
                pass

    existing_categories = {category.name: category for category in guild.categories}
    for category_data in snapshot.get("categories", []):
        category_name = category_data["name"]
        if category_name not in existing_categories:
            try:
                created = await guild.create_category(category_name, reason="Restauración premium")
                existing_categories[category_name] = created
            except (discord.Forbidden, discord.HTTPException):
                continue

    for category_data in snapshot.get("categories", []):
        category_name = category_data["name"]
        category_obj = existing_categories.get(category_name)
        if category_obj is None:
            continue
        existing_channels = {(channel.category.name if channel.category else "", channel.name, str(channel.type)) for channel in category_obj.channels}
        for channel_data in category_data.get("channels", []):
            key = (category_name, channel_data["name"], channel_data["type"])
            if key in existing_channels:
                continue
            try:
                if "text" in channel_data["type"].lower():
                    await guild.create_text_channel(
                        channel_data["name"],
                        category=category_obj,
                        topic=channel_data.get("topic"),
                        nsfw=channel_data.get("nsfw", False),
                        slowmode_delay=channel_data.get("slowmode_delay", 0),
                        reason="Restauración premium",
                    )
                elif "voice" in channel_data["type"].lower():
                    await guild.create_voice_channel(
                        channel_data["name"],
                        category=category_obj,
                        reason="Restauración premium",
                    )
            except (discord.Forbidden, discord.HTTPException):
                pass

    existing_top_channels = {("", channel.name, str(channel.type)) for channel in guild.channels if channel.category is None}
    for channel_data in snapshot.get("channels", []):
        key = ("", channel_data["name"], channel_data["type"])
        if key in existing_top_channels:
            continue
        try:
            if "text" in channel_data["type"].lower():
                await guild.create_text_channel(
                    channel_data["name"],
                    topic=channel_data.get("topic"),
                    nsfw=channel_data.get("nsfw", False),
                    slowmode_delay=channel_data.get("slowmode_delay", 0),
                    reason="Restauración premium",
                )
            elif "voice" in channel_data["type"].lower():
                await guild.create_voice_channel(channel_data["name"], reason="Restauración premium")
        except (discord.Forbidden, discord.HTTPException):
            pass

    return True


class BackupRestoreView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id

    @discord.ui.button(label="Restaurar copia", style=discord.ButtonStyle.danger)
    async def restore_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild is not None:
            guild = interaction.guild
        else:
            guild = interaction.client.get_guild(self.guild_id)

        if guild is None:
            await interaction.response.send_message("No pude localizar ese servidor.", ephemeral=True)
            return

        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("Este botón solo se usa dentro de un servidor.", ephemeral=True)
            return

        if not (interaction.user.id == guild.owner_id or interaction.user.guild_permissions.administrator):
            await interaction.response.send_message("Necesitas ser propietario o administrador del servidor.", ephemeral=True)
            return

        if not is_premium_user(interaction.user.id):
            await interaction.response.send_message("Este comando es premium. Activa tu plan para restaurar la copia.", ephemeral=True)
            return

        snapshot = load_backups().get(str(guild.id))
        if not snapshot:
            await interaction.response.send_message("Aún no hay una copia de seguridad guardada para este servidor.", ephemeral=True)
            return

        await interaction.response.send_message("🔄 Restaurando la estructura del servidor…", ephemeral=True)
        await restore_server_snapshot(guild, snapshot)
        await interaction.followup.send("✅ La estructura del servidor ha sido restaurada con la copia guardada.", ephemeral=True)


async def send_backup_dm_to_admins(guild: discord.Guild):
    if guild is None:
        return
    await save_server_snapshot(guild)
    for member in guild.members:
        if member.bot:
            continue
        if not is_premium_user(member.id):
            continue
        if not (member.id == guild.owner_id or member.guild_permissions.administrator):
            continue
        try:
            await member.send(
                f"**{guild.name}**\nCopia de seguridad guardada. Cuando quieras, pulsa el botón para restaurar el servidor a su estado anterior.",
                view=BackupRestoreView(guild.id),
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except (discord.Forbidden, discord.HTTPException):
            pass


async def premium_backup_scheduler(client: discord.Client):
    while not client.is_closed():
        for guild in client.guilds:
            try:
                await save_server_snapshot(guild)
                await send_backup_dm_to_admins(guild)
            except (discord.Forbidden, discord.HTTPException):
                pass
        await asyncio.sleep(5 * 60 * 60)


async def ensure_premium_role_for_user(user: discord.Member, guild: discord.Guild):
    if user.bot:
        return
    if not is_premium_user(user.id):
        return
    role = discord.utils.get(guild.roles, name="Premium")
    if role is None:
        try:
            role = await guild.create_role(name="Premium", reason="Suscripción premium")
        except (discord.Forbidden, discord.HTTPException):
            return
    if role not in user.roles:
        try:
            await user.add_roles(role, reason="Usuario premium activo")
        except (discord.Forbidden, discord.HTTPException):
            pass


async def ensure_premium_user_access(guild: discord.Guild):
    for member in guild.members:
        if member.bot:
            continue
        if is_premium_user(member.id):
            await ensure_premium_role_for_user(member, guild)
