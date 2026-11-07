from pathlib import Path
import re


REACTION_MARKER = "# VANTARMOR_MESSAGE_REACTIONS_V2"
REACTION_HELPERS = r'''# VANTARMOR_MESSAGE_REACTIONS_V2
KISS_GIFS = (
    "https://media.tenor.com/-I2QfQvG8fEAAAAC/anime-kiss.gif",
    "https://media.giphy.com/media/10UVJ0IXjUbPug/giphy.gif",
)
SLAP_GIFS = (
    "https://media.tenor.com/v1a5sM-9VnoAAAAC/anime-slap.gif",
    "https://media.giphy.com/media/3XlEk2RxPS1m8/giphy.gif",
)


class ReactionChoiceView(discord.ui.View):
    def __init__(self, initiator, recipient, action):
        super().__init__(timeout=300)
        self.initiator = initiator
        self.recipient = recipient
        self.action = action
        self.finished = False
        if action == "kiss":
            match = discord.ui.Button(label="💋 Coincidir", style=discord.ButtonStyle.success)
            reject = discord.ui.Button(label="🤦🏻 Rechazar", style=discord.ButtonStyle.secondary)
            match.callback = self.match
            reject.callback = self.reject
            self.add_item(match)
            self.add_item(reject)
        else:
            slap_back = discord.ui.Button(label="😡 Devolver", style=discord.ButtonStyle.danger)
            slap_back.callback = self.return_slap
            self.add_item(slap_back)

    async def interaction_check(self, interaction):
        if interaction.user.id != self.recipient.id:
            await interaction.response.send_message(
                "Este botón es para la persona del mensaje al que se respondió.", ephemeral=True
            )
            return False
        if self.finished:
            await interaction.response.send_message("Esta interacción ya terminó.", ephemeral=True)
            return False
        return True

    async def finish(self, interaction, outcome):
        self.finished = True
        for item in self.children:
            item.disabled = True
        if self.action == "kiss" and outcome == "match":
            text = f"💋 {self.recipient.mention} ha devuelto el beso a {self.initiator.mention}."
            image = random.choice(KISS_GIFS)
        elif self.action == "kiss":
            text = f"🤦🏻 {self.recipient.mention} ha rechazado el beso de {self.initiator.mention}."
            image = None
        else:
            text = f"😡 {self.recipient.mention} ha devuelto la bofetada a {self.initiator.mention}."
            image = random.choice(SLAP_GIFS)
        embed = discord.Embed(color=discord.Color.blurple())
        if image:
            embed.set_image(url=image)
        await interaction.response.edit_message(
            content=text,
            embed=embed,
            view=self,
            allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False),
        )

    async def match(self, interaction):
        await self.finish(interaction, "match")

    async def reject(self, interaction):
        await self.finish(interaction, "reject")

    async def return_slap(self, interaction):
        await self.finish(interaction, "return")


async def handle_reaction_command(message, content):
    command = content.split(maxsplit=1)[0].casefold() if content else ""
    if command not in ("?kiss", "?slap"):
        return False

    reference = message.reference
    if reference is None or reference.message_id is None:
        await message.reply(
            f"Responde al mensaje de una persona con `{command}` para usar este comando.",
            mention_author=False,
        )
        return True

    referenced = reference.resolved
    if referenced is None or not hasattr(referenced, "author"):
        try:
            channel = message.guild.get_channel(reference.channel_id)
            if channel is None:
                channel = await client.fetch_channel(reference.channel_id)
            referenced = await channel.fetch_message(reference.message_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            await message.reply("No pude encontrar el mensaje al que respondiste.", mention_author=False)
            return True

    target = referenced.author
    if target.bot:
        await message.reply("Elige el mensaje de una persona, no de un bot. 🙈", mention_author=False)
        return True
    if target.id == message.author.id:
        await message.reply("No puedes elegir tu propio mensaje para esta interacción. 😅", mention_author=False)
        return True

    if command == "?kiss":
        text = f"💋 {message.author.mention} ha besado a {target.mention}."
        image = random.choice(KISS_GIFS)
        view = ReactionChoiceView(message.author, target, "kiss")
    else:
        text = f"👋 {message.author.mention} ha abofeteado a {target.mention}."
        image = random.choice(SLAP_GIFS)
        view = ReactionChoiceView(message.author, target, "slap")

    embed = discord.Embed(color=discord.Color.blurple())
    embed.set_image(url=image)
    await message.reply(
        content=text,
        embed=embed,
        view=view,
        mention_author=False,
        allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False),
    )
    return True
'''

AFK_COOKIE_WARN_MARKER = "# VANTARMOR_AFK_COOKIE_WARN_V1"
AFK_COOKIE_WARN_HELPERS = r'''# VANTARMOR_AFK_COOKIE_WARN_V1
WARNINGS_FILE = Path("warnings.json")


def load_warnings():
    try:
        value = json.loads(WARNINGS_FILE.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_warnings():
    try:
        WARNINGS_FILE.write_text(json.dumps(warnings, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as error:
        print(f"No pude guardar las advertencias: {error}")


warnings = load_warnings()


def elapsed_label(seconds):
    seconds = max(0, int(seconds))
    if seconds >= 365 * 86400:
        return f"{seconds // (365 * 86400)} año(s)"
    if seconds >= 30 * 86400:
        return f"{seconds // (30 * 86400)} mes(es)"
    if seconds >= 86400:
        return f"{seconds // 86400} día(s)"
    if seconds >= 3600:
        return f"{seconds // 3600}h"
    if seconds >= 60:
        return f"{seconds // 60}m"
    return f"{seconds}s"


def afk_departure_text(user, state):
    duration = elapsed_label(time.time() - state.get("started", time.time()))
    reason = state.get("reason") or "Sin motivo"
    return f"👋 {user.mention} ha salido de su estado AFK.\n⏱️ Llevaba **{duration}** AFK.\n📝 Motivo: {reason}"


async def apply_warning_action(guild, moderator, target, action, duration_seconds_value, reason):
    bot_member = guild.me
    if bot_member is None:
        return "No pude verificar los permisos del bot."
    if target.bot or target.id == guild.owner_id:
        return "No se puede sancionar a un bot ni al propietario del servidor."
    if target.id == moderator.id or (isinstance(moderator, discord.Member) and target.top_role >= moderator.top_role and moderator.id != guild.owner_id):
        return "No puedes sancionar a alguien con un rol igual o superior al tuyo, ni a ti mismo."
    if target.top_role >= bot_member.top_role:
        return "No puedo sancionar: el rol del miembro está por encima o al mismo nivel que el del bot."
    try:
        if action == "ban":
            if not bot_member.guild_permissions.ban_members:
                return "Al bot le falta el permiso Banear miembros."
            await guild.ban(target, reason=reason, delete_message_seconds=0)
            return f"🔨 {target.mention} fue baneado al alcanzar el límite de advertencias."
        if action == "kick":
            if not bot_member.guild_permissions.kick_members:
                return "Al bot le falta el permiso Expulsar miembros."
            await guild.kick(target, reason=reason)
            return f"👢 {target.mention} fue expulsado al alcanzar el límite de advertencias."
        if action == "timeout":
            if not bot_member.guild_permissions.moderate_members:
                return "Al bot le falta el permiso Moderar miembros."
            seconds = max(60, min(int(duration_seconds_value or 3600), 28 * 86400))
            await target.timeout(datetime.now(timezone.utc) + timedelta(seconds=seconds), reason=reason)
            return f"🔇 {target.mention} fue silenciado durante **{duration_label(seconds)}** al alcanzar el límite de advertencias."
    except discord.Forbidden:
        return "Discord denegó la sanción. Revisa permisos y jerarquía de roles del bot."
    except discord.HTTPException:
        return "No se pudo aplicar la sanción por un error de Discord."
    return "Acción no válida."


class CookieGameView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.message = None
        self.winner_id = None
        self.winner_lock = asyncio.Lock()

    @discord.ui.button(label="🍪", style=discord.ButtonStyle.success)
    async def grab_cookie(self, interaction, button):
        async with self.winner_lock:
            if self.winner_id is not None:
                await interaction.response.send_message("La galleta ya tiene dueño. 🍪", ephemeral=True)
                return
            self.winner_id = interaction.user.id
            for child in self.children:
                child.disabled = True
            await interaction.response.edit_message(
                content=f"🍪 {interaction.user.mention} fue la primera persona en ganar la galleta. ¡Felicidades!",
                view=self,
                allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False),
            )
            self.stop()

    async def on_timeout(self):
        if self.winner_id is not None:
            return
        for child in self.children:
            child.disabled = True
        if self.message is not None:
            try:
                await self.message.edit(
                    content="🍪 Nadie alcanzó la galleta esta vez. ¡Inténtalo en la próxima partida!",
                    view=self,
                )
            except discord.HTTPException:
                pass
'''


def _remove_generated_block(source: str, marker: str, next_marker: str) -> str:
    if marker not in source:
        return source
    start = source.index(marker)
    end = source.index(next_marker, start)
    return source[:start] + source[end:]


def patch_app(app_file: Path) -> None:
    source = app_file.read_text(encoding="utf-8")
    event_marker = "@client.event\nasync def on_message(message):\n"
    if event_marker not in source:
        raise RuntimeError("No encontré on_message en app.py para aplicar las correcciones.")

    source = _remove_generated_block(source, REACTION_MARKER, event_marker)
    source = _remove_generated_block(source, "# VANTARMOR_MESSAGE_REACTIONS\n", event_marker)
    source = _remove_generated_block(source, AFK_COOKIE_WARN_MARKER, '@tree.command(name="cookie"')
    source = _remove_generated_block(source, "# VANTARMOR_AFK_COOKIE_FIX\n", '@tree.command(name="cookie"')

    content_line = '    content = message.content.strip()\n'
    command_line = '    command = parts[0].lower() if parts else ""\n'
    if content_line not in source or command_line not in source:
        raise RuntimeError("No encontré el contenido o el parser de comandos de on_message.")

    source = source.replace(event_marker, REACTION_HELPERS + "\n\n" + event_marker, 1)
    reaction_dispatch = "    if await handle_reaction_command(message, content):\n        return\n"
    if reaction_dispatch not in source:
        source = source.replace(content_line, content_line + reaction_dispatch, 1)

    cookie_decorator = '@tree.command(name="cookie", description="Juego de tocar la galleta", guild=GUILD)'
    if cookie_decorator not in source:
        raise RuntimeError("No encontré el comando /cookie en app.py.")
    source = source.replace(cookie_decorator, AFK_COOKIE_WARN_HELPERS + "\n\n" + cookie_decorator, 1)

    cookie_block = re.compile(
        r'@tree\.command\(name="cookie", description="Juego de tocar la galleta", guild=GUILD\)\n'
        r'async def cookie\(interaction\):\n'
        r'    await interaction\.response\.send_message\([^\n]*\)'
    )
    cookie_replacement = '''@tree.command(name="cookie", description="Juego de tocar la galleta", guild=GUILD)
async def cookie(interaction):
    await interaction.response.send_message("🍪 La galleta aparece en **5 segundos**…")
    await asyncio.sleep(5)
    view = CookieGameView()
    await interaction.edit_original_response(
        content="🍪 ¡Ya apareció! Sé la primera persona en tocar el botón verde.",
        view=view,
    )
    view.message = await interaction.original_response()'''
    source, cookie_count = cookie_block.subn(cookie_replacement, source, count=1)
    if cookie_count != 1:
        raise RuntimeError("No pude actualizar el comando /cookie con la cuenta regresiva y el botón.")

    # Replace the warning command definitions from the previous generated version.
    warn_start = source.find('@tree.command(name="warn",')
    if warn_start != -1:
        warn_end = source.find('@tree.command(name="avatar",', warn_start)
        if warn_end == -1:
            raise RuntimeError("No encontré el fin del bloque de advertencias.")
        source = source[:warn_start] + source[warn_end:]

    warning_commands = r'''
@tree.command(name="warn", description="Advierte a un miembro y aplica una sanción al llegar al límite", guild=GUILD)
@app_commands.default_permissions(moderate_members=True)
@app_commands.choices(accion=[
    app_commands.Choice(name="Banear", value="ban"),
    app_commands.Choice(name="Expulsar", value="kick"),
    app_commands.Choice(name="Silenciar", value="timeout"),
])
@app_commands.choices(unidad=[
    app_commands.Choice(name="Minutos", value="minutes"),
    app_commands.Choice(name="Horas", value="hours"),
])
@app_commands.describe(
    usuario="Miembro que recibirá la advertencia",
    limite="Advertencias permitidas antes de aplicar la sanción (1 a 10)",
    accion="Sanción al alcanzar el límite",
    duracion="Duración del silencio; requerida si eliges Silenciar",
    unidad="Unidad de duración del silencio",
    motivo="Motivo opcional de la advertencia",
)
async def warn_command(
    interaction: discord.Interaction,
    usuario: discord.Member,
    limite: app_commands.Range[int, 1, 10],
    accion: app_commands.Choice[str],
    duracion: Optional[app_commands.Range[int, 1, 40320]] = None,
    unidad: Optional[app_commands.Choice[str]] = None,
    motivo: Optional[str] = None,
):
    guild = interaction.guild
    moderator = interaction.user
    if guild is None or not isinstance(moderator, discord.Member):
        await interaction.response.send_message("Este comando solo funciona dentro de un servidor.", ephemeral=True)
        return
    if not (moderator.guild_permissions.moderate_members or moderator.guild_permissions.administrator or moderator.id == guild.owner_id):
        await interaction.response.send_message("Necesitas Moderar miembros o Administrador para usar este comando.", ephemeral=True)
        return
    if usuario.bot or usuario.id == guild.owner_id or usuario.id == moderator.id:
        await interaction.response.send_message("No puedes advertir a bots, al propietario ni a ti mismo.", ephemeral=True)
        return
    bot_member = guild.me
    if bot_member is None or usuario.top_role >= bot_member.top_role:
        await interaction.response.send_message("No puedo gestionar a ese miembro: su rol está por encima o al nivel del bot.", ephemeral=True)
        return
    if moderator.id != guild.owner_id and usuario.top_role >= moderator.top_role:
        await interaction.response.send_message("No puedes advertir a alguien con un rol igual o superior al tuyo.", ephemeral=True)
        return
    if accion.value == "timeout" and (duracion is None or unidad is None):
        await interaction.response.send_message("Para Silenciar, indica una duración y una unidad (minutos u horas).", ephemeral=True)
        return

    guild_key = str(guild.id)
    user_key = str(usuario.id)
    server_warnings = warnings.setdefault(guild_key, {})
    history = server_warnings.setdefault(user_key, [])
    if not isinstance(history, list):
        history = []
        server_warnings[user_key] = history
    reason = (motivo or "Sin motivo").strip()[:500] or "Sin motivo"
    history.append({"moderator_id": moderator.id, "reason": reason, "created_at": int(time.time())})
    save_warnings()
    count = len(history)

    if count >= int(limite):
        duration_seconds_value = None
        if accion.value == "timeout":
            duration_seconds_value = int(duracion) * (60 if unidad.value == "minutes" else 3600)
            duration_seconds_value = min(duration_seconds_value, 28 * 86400)
        sanction_reason = f"Límite de {limite} advertencia(s). Último motivo: {reason}"
        result = await apply_warning_action(guild, moderator, usuario, accion.value, duration_seconds_value, sanction_reason)
        # Clear the count only when the selected action was carried out successfully.
        action_succeeded = any(phrase in result for phrase in ("fue baneado", "fue expulsado", "fue silenciado"))
        if action_succeeded:
            server_warnings.pop(user_key, None)
            save_warnings()
        await interaction.response.send_message(
            f"⚠️ Advertencia **({count}/{limite})** para {usuario.mention}. Motivo: {reason}\n{result}",
            allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False),
        )
        return

    await interaction.response.send_message(
        f"⚠️ {usuario.mention} recibió una advertencia (**{count}/{limite}**).\nMotivo: {reason}",
        allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False),
    )


@tree.command(name="unwarn", description="Quita todas las advertencias de un miembro", guild=GUILD)
@app_commands.default_permissions(moderate_members=True)
@app_commands.describe(usuario="Miembro al que se le quitarán las advertencias", motivo="Motivo opcional")
async def unwarn_command(interaction: discord.Interaction, usuario: discord.Member, motivo: Optional[str] = None):
    guild = interaction.guild
    moderator = interaction.user
    if guild is None or not isinstance(moderator, discord.Member):
        await interaction.response.send_message("Este comando solo funciona dentro de un servidor.", ephemeral=True)
        return
    if not (moderator.guild_permissions.moderate_members or moderator.guild_permissions.administrator or moderator.id == guild.owner_id):
        await interaction.response.send_message("Necesitas Moderar miembros o Administrador para usar este comando.", ephemeral=True)
        return
    guild_key = str(guild.id)
    user_key = str(usuario.id)
    history = warnings.get(guild_key, {}).pop(user_key, [])
    save_warnings()
    if history:
        detail = f" Se quitaron **{len(history)}** advertencia(s)."
    else:
        detail = " El usuario no tenía advertencias registradas."
    note = f" Motivo: {motivo.strip()[:500]}" if motivo and motivo.strip() else ""
    await interaction.response.send_message(
        f"✅ Se reiniciaron las advertencias de {usuario.mention}.{detail}{note}",
        allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False),
    )
'''
    marker = '@tree.command(name="avatar", description="Muestra avatar y banner de un miembro", guild=GUILD)'
    if marker not in source:
        raise RuntimeError("No encontré el lugar para registrar /warn y /unwarn.")
    source = source.replace(marker, warning_commands + "\n\n" + marker, 1)

    old_afk = (
        '    state = afk_users.pop((message.guild.id, message.author.id), None)\n'
        '    if state:\n'
        '        await message.channel.send(f"{message.author.mention} salió de AFK tras {elapsed_label(time.time() - state[\'started\'])}.", allowed_mentions=discord.AllowedMentions.none())\n'
    )
    afk_dispatch = '''    state = afk_users.pop((message.guild.id, message.author.id), None)
    if state:
        await message.channel.send(
            afk_departure_text(message.author, state),
            allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False),
        )
'''
    if old_afk in source:
        source = source.replace(old_afk, "", 1)
    if afk_dispatch not in source:
        source = source.replace(command_line, command_line + afk_dispatch, 1)

    interaction_marker = "        data = interaction.data or {}\n"
    slash_afk = '''        afk_state = afk_users.pop((interaction.guild.id, interaction.user.id), None)
        if afk_state and interaction.channel is not None:
            await interaction.channel.send(
                afk_departure_text(interaction.user, afk_state),
                allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False),
            )
'''
    if interaction_marker not in source:
        raise RuntimeError("No encontré el manejador de interacciones para corregir /afk.")
    if slash_afk not in source:
        source = source.replace(interaction_marker, interaction_marker + slash_afk, 1)

    app_file.write_text(source, encoding="utf-8")
