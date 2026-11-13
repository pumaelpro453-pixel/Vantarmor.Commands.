# VANTARMOR_MESSAGE_REACTIONS_V2
KISS_GIFS = (
    "https://media.tenor.com/-I2QfQvG8fEAAAAC/anime-kiss.gif",
    "https://media.giphy.com/media/10UVJ0IXjUbPug/giphy.gif",
)
SLAP_GIFS = (
    "https://media.tenor.com/v1a5sM-9VnoAAAAC/anime-slap.gif",
    "https://media.giphy.com/media/3XlEk2RxPS1m8/giphy.gif",
)


async def random_anime_gif(action):
    """Fetch a random kiss/slap anime GIF; use curated GIFs if the API is down."""
    import json
    import urllib.request

    endpoint = "kiss" if action == "kiss" else "slap"
    fallback = KISS_GIFS if endpoint == "kiss" else SLAP_GIFS

    def fetch():
        request = urllib.request.Request(
            f"https://nekos.best/api/v2/{endpoint}",
            headers={"User-Agent": "Vantarmor-Commands/1.0", "Accept": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            payload = json.loads(response.read(256 * 1024).decode("utf-8"))
        results = payload.get("results", [])
        url = results[0].get("url") if results else None
        if isinstance(url, str) and url.startswith("https://"):
            return url
        return None

    try:
        return await asyncio.to_thread(fetch) or random.choice(fallback)
    except (OSError, ValueError, KeyError, TypeError):
        return random.choice(fallback)


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
            image = await random_anime_gif("kiss")
        elif self.action == "kiss":
            text = f"🤦🏻 {self.recipient.mention} ha rechazado el beso de {self.initiator.mention}."
            image = None
        else:
            text = f"😡 {self.recipient.mention} ha devuelto la bofetada a {self.initiator.mention}."
            image = await random_anime_gif("slap")
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
        image = await random_anime_gif("kiss")
        view = ReactionChoiceView(message.author, target, "kiss")
    else:
        text = f"👋 {message.author.mention} ha abofeteado a {target.mention}."
        image = await random_anime_gif("slap")
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
