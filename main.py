import discord
from discord.ext import commands
from discord import app_commands, ui
import aiosqlite
import asyncio
import random
import datetime

# --- CONFIGURATION ---
TOKEN = 'YOUR_BOT_TOKEN_HERE'
DB_PATH = 'titan_database.db'
THEME = 0x2b2d31  # Discord's native dark mode color
LOG_CHANNEL_ID = 123456789012345678  # REPLACE WITH YOUR LOG CHANNEL ID

# --- TICKET SYSTEM UI ---
class TicketView(ui.View):
    def __init__(self):
        super().__init__(timeout=None) # Timeout=None makes the button last forever

    @ui.button(label="Open Support Ticket", style=discord.ButtonStyle.blurple, emoji="🎫", custom_id="ticket_btn")
    async def create_ticket(self, interaction: discord.Interaction, button: ui.Button):
        guild = interaction.guild
        # Check if user already has a ticket
        existing_channel = discord.utils.get(guild.channels, name=f"ticket-{interaction.user.name.lower()}")
        if existing_channel:
            return await interaction.response.send_message(f"❌ You already have a ticket open at {existing_channel.mention}!", ephemeral=True)

        # Create private channel permissions
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        # Create the channel
        ticket_channel = await guild.create_text_channel(name=f"ticket-{interaction.user.name}", overwrites=overwrites)
        await interaction.response.send_message(f"✅ Ticket created: {ticket_channel.mention}", ephemeral=True)
        
        # Send welcome message inside the ticket
        embed = discord.Embed(title="Support Ticket", description=f"Welcome {interaction.user.mention}! A staff member will be with you shortly.\n\nTo close this, an admin can type `/close`.", color=THEME)
        await ticket_channel.send(embed=embed)

# --- BOT CLASS SETUP ---
class TitanBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all() # ALL intents required for logging
        super().__init__(command_prefix="!", intents=intents, help_command=None)
        self.db = None

    async def setup_hook(self):
        self.db = await aiosqlite.connect(DB_PATH)
        # Create DB Tables for Leveling AND Economy
        await self.db.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, xp INTEGER DEFAULT 0, level INTEGER DEFAULT 1, coins INTEGER DEFAULT 0)")
        await self.db.commit()
        
        # Add the persistent Ticket button to the bot's memory
        self.add_view(TicketView())
        await self.tree.sync()
        print(f"✅ {self.user} is fully operational and database is locked in.")

bot = TitanBot()

# --- ADVANCED AUDIT LOGGING ---
@bot.event
async def on_message_delete(message):
    if message.author.bot: return
    
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if not log_channel: return

    embed = discord.Embed(title="🗑️ Message Deleted", color=discord.Color.red(), timestamp=datetime.datetime.now())
    embed.add_field(name="Author", value=message.author.mention, inline=True)
    embed.add_field(name="Channel", value=message.channel.mention, inline=True)
    embed.add_field(name="Content", value=message.content or "No text (Image/Embed)", inline=False)
    embed.set_thumbnail(url=message.author.display_avatar.url)
    await log_channel.send(embed=embed)

# --- LEVELING & ECONOMY LISTENER ---
@bot.event
async def on_message(message):
    if message.author.bot: return
    
    async with bot.db.execute("SELECT xp, level, coins FROM users WHERE id = ?", (message.author.id,)) as cursor:
        row = await cursor.fetchone()
        
    if row is None:
        await bot.db.execute("INSERT INTO users (id, xp, level, coins) VALUES (?, ?, ?, ?)", (message.author.id, 5, 1, 10))
    else:
        xp, level, coins = row
        new_xp = xp + random.randint(5, 15)
        new_coins = coins + random.randint(1, 5) # Earn coins for talking
        next_level_xp = (level ** 2) * 100
        
        if new_xp >= next_level_xp:
            level += 1
            await message.channel.send(f"🎊 **LEVEL UP!** {message.author.mention} reached Level **{level}** and earned a 100 Coin bonus!")
            new_coins += 100
            
        await bot.db.execute("UPDATE users SET xp = ?, level = ?, coins = ? WHERE id = ?", (new_xp, level, new_coins, message.author.id))
    
    await bot.db.commit()
    await bot.process_commands(message)

# --- COMMANDS ---

@bot.tree.command(name="setup_tickets", description="Admin: Spawns the ticket creation panel")
@app_commands.checks.has_permissions(administrator=True)
async def setup_tickets(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📬 Contact Support",
        description="Click the button below to open a private channel with our staff team.",
        color=THEME
    )
    await interaction.channel.send(embed=embed, view=TicketView())
    await interaction.response.send_message("Ticket panel spawned successfully.", ephemeral=True)

@bot.tree.command(name="close", description="Admin: Close a support ticket")
@app_commands.checks.has_permissions(manage_channels=True)
async def close_ticket(interaction: discord.Interaction):
    if "ticket-" in interaction.channel.name:
        await interaction.response.send_message("Closing ticket in 3 seconds...")
        await asyncio.sleep(3)
        await interaction.channel.delete()
    else:
        await interaction.response.send_message("❌ This command can only be used inside a ticket channel.", ephemeral=True)

@bot.tree.command(name="profile", description="Check your Level, XP, and Wallet")
async def profile(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    async with bot.db.execute("SELECT xp, level, coins FROM users WHERE id = ?", (target.id,)) as cursor:
        row = await cursor.fetchone()
    
    if not row:
        return await interaction.response.send_message("❌ User has no data yet!", ephemeral=True)
    
    xp, level, coins = row
    next_xp = (level ** 2) * 100
    
    embed = discord.Embed(title=f"💳 {target.display_name}'s Profile", color=THEME)
    embed.add_field(name="Level", value=f"**{level}**", inline=True)
    embed.add_field(name="Wallet", value=f"🪙 **{coins}** Coins", inline=True)
    embed.add_field(name="XP Progress", value=f"**{xp} / {next_xp}**", inline=False)
    embed.set_thumbnail(url=target.display_avatar.url)
    
    await interaction.response.send_message(embed=embed)

# --- FINAL BOOT ---
async def main():
    async with bot:
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
