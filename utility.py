import discord
from discord.ext import commands, tasks
import json
import datetime
import asyncio
import random
import pytz
import os
from collections import deque

CONFIG_FILE = 'config.json'

def load_config():
    with open(CONFIG_FILE) as f:
        return json.load(f)

def save_config(cfg):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(cfg, f, indent=2)

config = load_config()

TOKEN = config['Utility_bot_token']
ALLOWED_USER = int(config['Utility_bot_token'])
PREMIUM_ROLE_ID = int(config.get('Premium_Role_Id', 0))
REVIEW_CHANNEL_ID = int(config.get('Review_channel_id', 0))
DROP_CHANNEL_ID = int(config.get('Drop_Channel_Id', 0))
GUILD_ID = 1450598554371362952

STATS_FILE = 'stats.json'

def load_stats():
    try:
        with open(STATS_FILE) as f:
            return json.load(f)
    except FileNotFoundError:
        return {'total': 0, 'sum': 0, 'last_five': []}

def save_stats(stats):
    with open(STATS_FILE, 'w') as f:
        json.dump(stats, f, indent=2)

stats = load_stats()

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.members = True
bot = commands.Bot(command_prefix='$', intents=intents, help_command=None)

purge_active = False
purge_channel_id = None
purge_message_id = None

def human_delta(dt: datetime.datetime) -> str:
    now = datetime.datetime.utcnow()
    delta = now - dt
    days = delta.days
    if days >= 365:
        return f"{days // 365} year{'s' if days // 365 != 1 else ''} ago"
    if days >= 30:
        return f"{days // 30} month{'s' if days // 30 != 1 else ''} ago"
    if days >= 7:
        return f"{days // 7} week{'s' if days // 7 != 1 else ''} ago"
    return f"{days} day{'s' if days != 1 else ''} ago"

@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.CustomActivity(name='Flow Cloud Utility Bot'))
    await bot.tree.sync()
    check_growth.start()
    print('Bot online')

@tasks.loop(minutes=5)
async def check_growth():
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        return
    member_count = guild.member_count
    if member_count in (1000, 1500):
        await start_purge_wave(guild)

async def start_purge_wave(guild):
    global purge_active, purge_channel_id, purge_message_id
    if purge_active:
        return
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=False),
        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
    }
    channel = await guild.create_text_channel('purge-wave', overwrites=overwrites)
    purge_channel_id = channel.id
    embed = discord.Embed(
        title='🧹 Purge Wave Incoming',
        description='Hey @everyone its time for a member purgewave!\nTo keep the community active this Purge Wave is to remove inactive members\n\nWhat you need to do is react with ✅ within 48 hours to confirm you\'re still active\n\nIf you don\'t react within 48 hours you\'ll be kicked by the bot automatically once the 48 hour timer ends\n\nLet\'s keep Flow Cloud active',
        color=discord.Color.cyan()
    )
    embed.set_footer(text='Flow Cloud Purge Wave')
    msg = await channel.send(embed=embed)
    await msg.add_reaction('✅')
    purge_message_id = msg.id
    purge_active = True
    await asyncio.sleep(48 * 3600)
    if not purge_active:
        return
    await perform_purge(guild, channel)

async def perform_purge(guild, channel):
    global purge_active
    msg = await channel.fetch_message(purge_message_id)
    reacted = set()
    for reaction in msg.reactions:
        if str(reaction.emoji) == '✅':
            async for user in reaction.users():
                reacted.add(user.id)
    to_kick = []
    for member in guild.members:
        if member.bot:
            continue
        if member.guild_permissions.administrator or member.guild_permissions.manage_guild:
            continue
        if member.id not in reacted:
            to_kick.append(member)
    for member in to_kick:
        try:
            await member.kick(reason='Purge Wave - inactive')
        except:
            pass
    await channel.send(f'🧹 Purge complete. {len(to_kick)} members removed.')
    purge_active = False

@bot.tree.command(name='setpremiumrole')
async def setpremiumrole(interaction: discord.Interaction, role: discord.Role):
    if interaction.user.id != ALLOWED_USER:
        return await interaction.response.send_message('❌ Unauthorized', ephemeral=True)
    global config
    config['Premium_Role_Id'] = str(role.id)
    save_config(config)
    await interaction.response.send_message(f'✅ Premium role set to {role.mention}', ephemeral=True)

@bot.tree.command(name='setreview')
async def setreview(interaction: discord.Interaction, channel: discord.TextChannel):
    if interaction.user.id != ALLOWED_USER:
        return await interaction.response.send_message('❌ Unauthorized', ephemeral=True)
    global config
    config['Review_channel_id'] = str(channel.id)
    save_config(config)
    await interaction.response.send_message(f'✅ Review channel set to {channel.mention}', ephemeral=True)

@bot.tree.command(name='setdrop')
async def setdrop(interaction: discord.Interaction, channel: discord.TextChannel):
    if interaction.user.id != ALLOWED_USER:
        return await interaction.response.send_message('❌ Unauthorized', ephemeral=True)
    global config
    config['Drop_Channel_Id'] = str(channel.id)
    save_config(config)
    await interaction.response.send_message(f'✅ Drop channel set to {channel.mention}', ephemeral=True)

@bot.tree.command(name='purgewave')
async def purgewave(interaction: discord.Interaction):
    if interaction.guild_id != GUILD_ID:
        return await interaction.response.send_message('This command only works in Flow Cloud.', ephemeral=True)
    if interaction.user.id != ALLOWED_USER:
        return await interaction.response.send_message('❌ Unauthorized', ephemeral=True)
    guild = interaction.guild
    await interaction.response.send_message('✅ Purge wave started', ephemeral=True)
    await start_purge_wave(guild)

@bot.tree.command(name='purgecancel')
async def purgecancel(interaction: discord.Interaction):
    if interaction.guild_id != GUILD_ID:
        return await interaction.response.send_message('This command only works in Flow Cloud.', ephemeral=True)
    if interaction.user.id != ALLOWED_USER:
        return await interaction.response.send_message('❌ Unauthorized', ephemeral=True)
    global purge_active, purge_channel_id
    if not purge_active:
        return await interaction.response.send_message('No active purge wave', ephemeral=True)
    channel = bot.get_channel(purge_channel_id)
    if channel:
        try:
            await channel.delete()
        except:
            pass
    purge_active = False
    await interaction.response.send_message('✅ Purge wave cancelled', ephemeral=True)

@bot.tree.command(name='drop')
async def drop(interaction: discord.Interaction, file: discord.Attachment):
    if interaction.user.id != ALLOWED_USER:
        return await interaction.response.send_message('❌ Unauthorized', ephemeral=True)
    channel = bot.get_channel(DROP_CHANNEL_ID)
    if not channel:
        return await interaction.response.send_message('Drop channel not found', ephemeral=True)
    if not file.filename.endswith('.txt'):
        return await interaction.response.send_message('❌ Only .txt files are allowed', ephemeral=True)
    await interaction.response.send_message('✅ Drop sent', ephemeral=True)

    est = pytz.timezone('US/Eastern')
    now = datetime.datetime.now(est).strftime('%B %d, %Y %I:%M %p')

    embed = discord.Embed(
        title='🔥 New Drop Alert',
        description=f'{file.filename} from the Flow Cloud Staff Team\n\nDownload the file to access content inside',
        color=discord.Color.cyan(),
        timestamp=datetime.datetime.utcnow()
    )
    embed.add_field(name='📄 File Name', value=file.filename, inline=False)
    embed.add_field(name='Dropped At', value=f'{now} EST', inline=False)
    embed.set_footer(text='Flow Cloud Drop System')

    await channel.send(embed=embed, file=await file.to_file())

@bot.command(name='si', aliases=['serverinfo'])
async def si(ctx):
    g = ctx.guild
    desc = g.description or "No description set"
    owner = g.owner.mention if g.owner else "Unknown"
    created = f"{human_delta(g.created_at)} ({g.created_at.strftime('%B %d, %Y at %I:%M %p')})"

    bots = sum(1 for m in g.members if m.bot)
    humans = g.member_count - bots

    lvl = g.premium_tier.name.replace('_', ' ').title()
    boosts = g.premium_subscription_count

    embed = discord.Embed(
        title=g.name,
        description=f"{desc}\n\n**General Info**\n**Name:** {g.name}\n**Server ID:** {g.id}\n**Owner:** {owner}\n**Created:** {created}",
        color=discord.Color.cyan()
    )
    embed.add_field(
        name="Members & Roles",
        value=f"**Members:** {humans}\n**Bots:** {bots}\n**Total:** {g.member_count}\n**Roles:** {len(g.roles)}",
        inline=False
    )
    embed.add_field(
        name="Boost Status",
        value=f"**Server Boost Level:** {lvl}\n**Amount of Boosts:** {boosts}",
        inline=False
    )
    embed.add_field(
        name="Channels",
        value=f"**Text:** {len(g.text_channels)}\n**Voice:** {len(g.voice_channels)}\n**Categories:** {len(g.categories)}",
        inline=False
    )
    embed.set_thumbnail(url=g.icon.url if g.icon else None)
    embed.set_footer(text="Flow Cloud Utility Bot")
    await ctx.send(embed=embed)

@bot.tree.command(name='si')
async def si_slash(interaction: discord.Interaction):
    g = interaction.guild
    desc = g.description or "No description set"
    owner = g.owner.mention if g.owner else "Unknown"
    created = f"{human_delta(g.created_at)} ({g.created_at.strftime('%B %d, %Y at %I:%M %p')})"

    bots = sum(1 for m in g.members if m.bot)
    humans = g.member_count - bots

    lvl = g.premium_tier.name.replace('_', ' ').title()
    boosts = g.premium_subscription_count

    embed = discord.Embed(
        title=g.name,
        description=f"{desc}\n\n**General Info**\n**Name:** {g.name}\n**Server ID:** {g.id}\n**Owner:** {owner}\n**Created:** {created}",
        color=discord.Color.cyan()
    )
    embed.add_field(
        name="Members & Roles",
        value=f"**Members:** {humans}\n**Bots:** {bots}\n**Total:** {g.member_count}\n**Roles:** {len(g.roles)}",
        inline=False
    )
    embed.add_field(
        name="Boost Status",
        value=f"**Server Boost Level:** {lvl}\n**Amount of Boosts:** {boosts}",
        inline=False
    )
    embed.add_field(
        name="Channels",
        value=f"**Text:** {len(g.text_channels)}\n**Voice:** {len(g.voice_channels)}\n**Categories:** {len(g.categories)}",
        inline=False
    )
    embed.set_thumbnail(url=g.icon.url if g.icon else None)
    embed.set_footer(text="Flow Cloud Utility Bot")
    await interaction.response.send_message(embed=embed)

@bot.command(name='shop')
async def shop(ctx, channel: discord.TextChannel):
    if ctx.author.id != ALLOWED_USER:
        return await ctx.send('❌ Unauthorized', delete_after=5)
    guild = ctx.guild
    icon_url = guild.icon.url if guild.icon else ''
    embed = discord.Embed(
        title='Flow Cloud Shop System',
        description='Welcome to Flow Cloud Shop\n\nHere you can purchase stuff like our discord bots premium Gen stock server access even accounts or methods\n\n**What we offer**\nPremium Generator Access\nStock Server Access\nBot Source Codes\n\n**Important Note:** We are not negotiating our prices we list no exceptions all prices and sales are final\n\n**We take these payment methods**\n💵 Cash App\n🍏 Apple Pay\n💳 PayPal\n🪙 ETH\n🪙 LTC\n🪙 BTC\n💸 Venmo',
        color=discord.Color.cyan()
    )
    embed.set_thumbnail(url=icon_url)
    embed.set_footer(text='Flow Cloud Shop System')

    class ShopDropdown(discord.ui.Select):
        def __init__(self):
            options = [
                discord.SelectOption(label='Premium Generator Access', emoji='🔑', description='Buy premium generator access'),
                discord.SelectOption(label='Stock Server Access', emoji='📊', description='Buy stock server access'),
                discord.SelectOption(label='Bot Source Codes', emoji='🤖', description='Buy bot source codes')
            ]
            super().__init__(placeholder='Choose what u want to buy', options=options)

        async def callback(self, interaction: discord.Interaction):
            if self.values[0] == 'Premium Generator Access':
                await interaction.response.send_message('🔑 You can buy access to our <#1450598555617202339> channel for these prices\n1D = $0.25\n3D = $0.50\n7D/1W = $1\n1 Month = $3\nLifetime = $5', ephemeral=True)
            elif self.values[0] == 'Stock Server Access':
                await interaction.response.send_message('📊 Stock server access for\n1D = $1\n3D = $2\n7D = $5\n1 Month = $8\nLifetime = $10', ephemeral=True)
            elif self.values[0] == 'Bot Source Codes':
                await interaction.response.send_message('🤖 Here you can buy our bots source codes that we made ourself for cheap prices\n\nFlow Cloud Generator Source Code $20\nFlow Cloud Utility Source Code $5\nFlow Cloud Pass Change Bot $25', ephemeral=True)

    class ShopView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=None)
            self.add_item(ShopDropdown())

    await channel.send(embed=embed, view=ShopView())
    await ctx.send('✅ Shop sent', delete_after=3)

@bot.command(name='rules')
async def rules(ctx, channel: discord.TextChannel):
    if ctx.author.id != ALLOWED_USER:
        return await ctx.send('❌ Unauthorized', delete_after=5)
    embed = discord.Embed(
        title='Flow Cloud Rules',
        description=(
            "**Server Rules & Guidelines**\n"
            "Welcome to our server! Please read and follow all rules to ensure a safe and friendly environment. "
            "Violations may result in warnings, kicks, or bans depending on how you acted.\n\n"

            "**1. General Conduct**\n"
            "• Treat all members with respect. Harassment, bullying, or hate speech will not be allowed.\n"
            "• Listen to staff and follow all instructions provided; failing to do so will result in punishment.\n"
            "• Keep discussions civil—no threats, slurs, or personal attacks.\n"
            "• Do not mini-mod; let staff handle rule-breakers.\n"
            "• Use common sense—if it feels wrong, don’t do it.\n\n"

            "**2. Chat Rules**\n"
            "• No spamming, flooding, or excessive caps/emojis.\n"
            "• Keep messages in the correct channels—off-topic goes in off-topic.\n"
            "• No NSFW, gore, or disturbing content anywhere.\n"
            "• Refrain from discussing politics, religion, or other sensitive subjects.\n"
            "• English only in public channels; use DMs for other languages.\n"
            "• No ghost-pinging or mass-pinging without valid reason.\n"
            "• Do not share personal information (yours or anyone else’s).\n\n"

            "**3. Promoting & Advertising**\n"
            "• No self-promotion or advertising of any kind (servers, socials, referral links, etc.).\n"
            "• Do not post Discord invites or IP addresses in any channel or DM.\n"
            "• Paid advertisements must be pre-approved by ownership.\n"
            "• No unsolicited DMs to members for promotion purposes.\n"
            "• Stream links are allowed only in the designated self-promo channel (if one exists) and only once per 24 h.\n"
            "• NFT/crypto projects require explicit staff permission before mention.\n\n"

            "**4. Account Distribution**\n"
            "• You are responsible for the security of any account provided here.\n"
            "• **DO NOT SHARE** account details outside this server—doing so voids your access.\n"
            "• These are temporary, non-full-access (NFA) accounts; do **NOT** store personal info on them.\n"
            "• Accounts expire within 7 days max; no replacements are given for expired or banned accounts.\n"
            "• Do not change passwords, emails, or usernames on distributed accounts.\n"
            "• Report dead accounts in the correct channel so we can restock.\n"
            "• Selling or trading our free accounts is strictly prohibited and will result in an immediate ban.\n"
            "• Use accounts at your own risk—we are not liable for any bans or locks that occur.\n"
            "• No begging for accounts; wait for drops like everyone else.\n\n"

            "**5. Voice Channels**\n"
            "• No ear-rape, soundboards, or excessive background noise.\n"
            "• Respect push-to-talk rules when required.\n"
            "• No screen-sharing NSFW or copyrighted content.\n\n"

            "**6. Bot & Command Usage**\n"
            "• Only use commands in designated bot channels.\n"
            "• Do not spam commands or attempt to crash/attack the bot.\n"
            "• Report bugs privately to staff; exploiting them is bannable.\n\n"

            "**7. Ban Evasion**\n"
            "• Joining on alts after being punished will result in a permanent IP ban.\n"
            "• If you believe a punishment was unfair, open a ticket—do not argue in chat.\n\n"

            "**Final Notes**\n"
            "Rules can be updated at any time; it’s your responsibility to check them. "
            "Staff have the final say in all situations. Welcome to Flow Cloud—enjoy your stay!"
        ),
        color=discord.Color.cyan()
    )
    embed.set_footer(text='Flow Cloud Rules')
    await channel.send(embed=embed)
    await ctx.send('✅ Rules sent', delete_after=3)

@bot.command(name='terms')
async def terms(ctx, channel: discord.TextChannel):
    if ctx.author.id != ALLOWED_USER:
        return await ctx.send('❌ Unauthorized', delete_after=5)
    embed = discord.Embed(
        title='Flow Cloud Terms',
        description=(
            "Please make sure to read the server's Terms and Conditions before using our services. "
            "By accessing or using our services, you acknowledge that you have read, understood, and agreed to comply with the rules outlined below. "
            "These Terms and Conditions are mandatory.\n\n"

            "**1. Free Generator Terms**\n"
            "• We do not own or claim ownership of any free Generator accounts.\n"
            "• These accounts are provided solely as alternative Minecraft accounts.\n"
            "• We are not responsible for any issues or losses if you lose access to the account.\n"
            "• Please use these accounts entirely at your **own risk.**\n"
            "• Accounts except **Pass-changed Accounts** are temporary, lasting anywhere from 1 to 7 days, and are not full access.\n"
            "• If you have an account that lasts more than 7 days that isn't pass-changed, consider yourself lucky.\n"
            "• Pass-changed accounts will not expire like accounts from the free gen; if an account that was pass-changed by us has its password changed or something happens within **ONLY 15 DAYS**, open a ticket to claim a new account.\n"
            "• Pass-changed account email can only be changed after 30 days.\n"
            "• We will not replace accounts for issues related to logging in on specific servers.\n"
            "• If any account doesn't work, generate a new one or wait for new stock.\n"
            "• We don't replace pass-changed accounts after 15 DAYS after first login from the other party.\n\n"

            "**2. Booster Perks Terms**\n"
            "• MCFA account may or may not be PERMANENT.\n"
            "• MCFA account email can only be changed after 30 days.\n"
            "• MCFA account password will be set to your preference.\n"
            "• We will not replace accounts for issues related to logging in on specific servers.\n"
            "• If you encounter login issues, we will provide one replacement only if the issue is reported within 15 DAYS of claiming.\n\n"

            "**3. MCFA from Giveaways**\n"
            "• MCFA accounts are 80 % permanent; if it expires within 15 DAYS, report to us.\n\n"

            "**4. Purchased MFAs**\n"
            "• MFAs are Permanent.\n"
            "• MFAs will be given in the form of recovery code (email:recovery code).\n"
            "• Further information will be given to you if you buy from me.\n\n"

            "**Final Note**\n"
            "If you do not agree with the Server's Terms and Conditions, you are free to leave the server."
        ),
        color=discord.Color.cyan()
    )
    embed.set_footer(text='Flow Cloud Terms')
    await channel.send(embed=embed)
    await ctx.send('✅ Terms sent', delete_after=3)

@bot.tree.command(name='perks')
async def perks(interaction: discord.Interaction, option: str, channel: discord.TextChannel):
    if interaction.user.id != ALLOWED_USER:
        return await interaction.response.send_message('❌ Unauthorized', ephemeral=True)
    guild = interaction.guild
    icon_url = guild.icon.url if guild.icon else ''
    footer = 'Flow Cloud Utility Bot'
    if option == 'boost':
        embed = discord.Embed(
            title='🚀 Booster Perks',
            description='**1x Booster Perks!**\n3x NFA Minecraft Accounts (temp)!\nBooster Gen Access (until unboost)\nStock server access (a few tools and only hypixel banned)\n\n**2x Booster Perks**\nAll perks from 1x\nStock Server Access (banned and hypixel banned)\nDaily drops 🎁\nBooster Giveaways 🎉\nPrivate support channel 🔧\nVIP voice channels 🔊',
            color=discord.Color.cyan()
        )
        embed.set_thumbnail(url=icon_url)
        embed.set_footer(text=footer)
        await channel.send(embed=embed)
    elif option == 'invites':
        embed = discord.Embed(
            title='🎁 Invite Rewards',
            description='**2 Invites** - 1x NFA Minecraft account 🧱\n**5 Invites** - 3x Xbox Game Pass Ultimate NFA 🎮\n**15 Invites** - 1 Pass-changed Minecraft Hypixel temp-banned account 🔁\n**25 Invites** - 3x NFA Minecraft accounts 📦\n**40 Invites** - 5x NFA Minecraft accounts 🏆\n**60 Invites** - Stock Server Access (1D) 🔓\n**80 Invites** - 10x NFA Minecraft accounts 📚\n**100 Invites** - Stock Server Access (3D) 📊\n**150 Invites** - 15x NFA Minecraft accounts 💎\n**200 Invites** - Stock Server Access (7D) 🗃️',
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=icon_url)
        embed.set_footer(text=footer)
        await channel.send(embed=embed)
    await interaction.response.send_message('✅ Sent', ephemeral=True)

class GiveawayView(discord.ui.View):
    def __init__(self, prize, winners, duration, end_time, hoster):
        super().__init__(timeout=None)
        self.prize = prize
        self.winners = winners
        self.duration = duration
        self.end_time = end_time
        self.hoster = hoster
        self.participants = set()
    @discord.ui.button(emoji='🎉', style=discord.ButtonStyle.primary, custom_id='join')
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.participants.add(interaction.user.id)
        await interaction.response.send_message('🎉 You joined the giveaway!', ephemeral=True)
    async def draw(self, message):
        valid = [u for u in self.participants if message.guild.get_member(u)]
        if len(valid) < self.winners:
            winners = valid
        else:
            winners = random.sample(valid, self.winners)
        mentions = [f'<@{w}>' for w in winners]
        embed = discord.Embed(
            title='🎉 Giveaway ended!',
            description=f'Prize: **{self.prize}**\nWinners: {", ".join(mentions) if mentions else "None"}',
            color=discord.Color.gold(),
            timestamp=datetime.datetime.utcnow()
        )
        await message.reply(embed=embed)
        return winners

@bot.tree.command(name='gstart')
async def gstart(interaction: discord.Interaction, duration: str, winners: int, prize: str, channel: discord.TextChannel = None):
    if interaction.user.id != ALLOWED_USER:
        return await interaction.response.send_message('❌ Unauthorized', ephemeral=True)
    target = channel or interaction.channel
    seconds = 0
    if duration.endswith('s'): seconds = int(duration[:-1])
    elif duration.endswith('m'): seconds = int(duration[:-1]) * 60
    elif duration.endswith('h'): seconds = int(duration[:-1]) * 3600
    elif duration.endswith('d'): seconds = int(duration[:-1]) * 86400
    elif duration.endswith('w'): seconds = int(duration[:-1]) * 604800
    end_time = datetime.datetime.utcnow() + datetime.timedelta(seconds=seconds)
    embed = discord.Embed(
        title=f'🎉 {prize}',
        description=f'React with 🎉 to enter!\nEnds: <t:{int(end_time.timestamp())}:R>\nHosted by: {interaction.user.mention}\nTotal participants: **0**',
        color=discord.Color.gold(),
        timestamp=end_time
    )
    embed.set_footer(text='Flow Cloud Utility Bot')
    msg = await target.send(embed=embed)
    view = GiveawayView(prize, winners, duration, end_time, interaction.user)
    await msg.edit(view=view)
    await interaction.response.send_message('✅ Giveaway started', ephemeral=True)
    await asyncio.sleep(seconds)
    view.stop()
    new_embed = discord.Embed(
        title=f'🎉 {prize}',
        description=f'Giveaway ended!\nWinners: **{winners}**\nHosted by: {interaction.user.mention}\nTotal participants: **{len(view.participants)}**',
        color=discord.Color.gold(),
        timestamp=end_time
    )
    new_embed.set_footer(text='Flow Cloud Utility Bot')
    await msg.edit(embed=new_embed, view=None)
    await view.draw(msg)

@bot.tree.command(name='premium')
async def premium(interaction: discord.Interaction, user: discord.Member, duration: str):
    if interaction.user.id != ALLOWED_USER:
        return await interaction.response.send_message('❌ Unauthorized', ephemeral=True)
    role = interaction.guild.get_role(PREMIUM_ROLE_ID)
    if not role:
        return await interaction.response.send_message('Premium role not found', ephemeral=True)
    seconds = 0
    if duration.endswith('s'): seconds = int(duration[:-1])
    elif duration.endswith('m'): seconds = int(duration[:-1]) * 60
    elif duration.endswith('h'): seconds = int(duration[:-1]) * 3600
    elif duration.endswith('d'): seconds = int(duration[:-1]) * 86400
    elif duration.endswith('w'): seconds = int(duration[:-1]) * 604800
    elif duration.endswith('mo'): seconds = int(duration[:-2]) * 2592000
    await user.add_roles(role)
    embed = discord.Embed(
        title='✅ Premium Granted',
        description=f'{user.mention} has received the {role.mention} role for {duration}',
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed)
    await asyncio.sleep(seconds)
    if role in user.roles:
        await user.remove_roles(role)

class ReviewModal(discord.ui.Modal, title='Give A Review'):
    rating = discord.ui.TextInput(label='Rating (1-5 Stars)', placeholder='Enter a number 1-5', required=True, max_length=1)
    experience = discord.ui.TextInput(label='Your Experience', style=discord.TextStyle.paragraph, required=True, max_length=1000)
    suggestions = discord.ui.TextInput(label='Suggestions', style=discord.TextStyle.paragraph, required=False, max_length=1000)

    async def on_submit(self, interaction: discord.Interaction):
        global stats
        channel = bot.get_channel(REVIEW_CHANNEL_ID)
        if not channel:
            return await interaction.response.send_message('Review channel not configured', ephemeral=True)
        stars = '⭐' * int(self.rating.value) if self.rating.value.isdigit() and 1 <= int(self.rating.value) <= 5 else 'Invalid'
        embed = discord.Embed(
            title='Flow Cloud Reviews',
            description=f'Review received from {interaction.user.mention}\n\nRating: {stars}\n\nExperience: {self.experience.value}\n\nSuggestions: {self.suggestions.value or "No suggestions!"}',
            color=discord.Color.cyan(),
            timestamp=datetime.datetime.utcnow()
        )
        await channel.send(embed=embed)
        if self.rating.value.isdigit():
            r = int(self.rating.value)
            stats['total'] += 1
            stats['sum'] += r
            stats['last_five'].append(r)
            if len(stats['last_five']) > 5:
                stats['last_five'].pop(0)
            save_stats(stats)
        await interaction.response.send_message('✅ Review submitted!', ephemeral=True)

@bot.tree.command(name='review')
async def review(interaction: discord.Interaction):
    view = discord.ui.View()
    button = discord.ui.Button(label='⭐ Give A Review', style=discord.ButtonStyle.primary)
    async def btn_callback(interaction: discord.Interaction):
        await interaction.response.send_modal(ReviewModal())
    button.callback = btn_callback
    view.add_item(button)
    guild = interaction.guild
    icon_url = guild.icon.url if guild.icon else ''
    embed = discord.Embed(
        title='Flow Cloud Review System',
        description='We value your honesty\n\nClick the button "Give A Review" below to write and give our server a review you can rate between a 1 star to 5 stars feel free to share your thoughts',
        color=discord.Color.cyan()
    )
    embed.set_thumbnail(url=icon_url)
    embed.set_footer(text='Flow Cloud Review System')
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name='stats')
async def stats_cmd(interaction: discord.Interaction):
    global stats
    total = stats['total']
    s = stats['sum']
    avg = round(s / total, 2) if total else 0
    last = ' '.join(['⭐'*x for x in stats['last_five']]) if stats['last_five'] else 'No recent reviews'
    embed = discord.Embed(
        title='📊 Flow Cloud Review Statistics',
        description=f'**Total Reviews Received:** {total}\n**Average Rating:** {avg}/5 ⭐\n\n**Last 5 Ratings:**\n{last}',
        color=discord.Color.cyan(),
        timestamp=datetime.datetime.utcnow()
    )
    embed.set_footer(text='Flow Cloud Review System')
    await interaction.response.send_message(embed=embed)

bot.run(TOKEN)
