import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
import datetime
import asyncio

# Intents and bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True  # Required for role and member actions

bot = commands.Bot(command_prefix='!', intents=intents)

# Global variables
last_active_time = None

# Slash command synchronization
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    await bot.change_presence(activity=discord.Game("Online now!"))
    try:
        await bot.tree.sync()
        print("Slash commands synced.")
    except Exception as e:
        print(f"Error syncing commands: {e}")

# Event: On disconnect
@bot.event
async def on_disconnect():
    global last_active_time
    last_active_time = datetime.datetime.utcnow()

# Event: On connect
@bot.event
async def on_connect():
    global last_active_time
    if last_active_time:
        last_active_str = last_active_time.strftime('%Y-%m-%d %H:%M:%S UTC')
        status_message = f"Last active: {last_active_str}"
    else:
        status_message = "First time online!"
    await bot.change_presence(activity=discord.Game(status_message))

# Slash command: Purge messages
@bot.tree.command(name="purge", description="Delete a number of messages from the current channel")
@app_commands.describe(amount="Number of messages to delete")
async def purge(interaction: discord.Interaction, amount: int):
    if interaction.user.guild_permissions.manage_messages:
        deleted = await interaction.channel.purge(limit=amount)
        await interaction.response.send_message(f"🗑️ Deleted {len(deleted)} messages.", ephemeral=True)
    else:
        await interaction.response.send_message("You don't have permission to manage messages.", ephemeral=True)

# Slash command: Start staff trial
@bot.tree.command(name="start_trial", description="Assign a trial staff role to a user")
@app_commands.describe(user="The user to assign the trial role", trial_role="The trial role to assign")
async def start_trial(interaction: discord.Interaction, user: discord.Member, trial_role: discord.Role):
    if interaction.user.guild_permissions.manage_roles:
        if interaction.guild.me.guild_permissions.manage_roles:
            if trial_role.position < interaction.guild.me.top_role.position:
                await user.add_roles(trial_role)
                await interaction.response.send_message(f"✅ {user.mention} has been given the trial role: {trial_role.name}.")
            else:
                await interaction.response.send_message("I cannot assign a role that is higher than or equal to my role.", ephemeral=True)
        else:
            await interaction.response.send_message("I don't have permission to manage roles.", ephemeral=True)
    else:
        await interaction.response.send_message("You don't have permission to manage roles.", ephemeral=True)

# Slash command: End staff trial
@bot.tree.command(name="end_trial", description="End a trial for a staff member")
@app_commands.describe(user="The user to end the trial for", trial_role="The trial role", promote="Promote to permanent staff")
async def end_trial(interaction: discord.Interaction, user: discord.Member, trial_role: discord.Role, promote: bool):
    if interaction.user.guild_permissions.manage_roles:
        await user.remove_roles(trial_role)
        if promote:
            await interaction.response.send_message(f"✅ {user.mention}'s trial has ended, and they have been promoted.")
        else:
            await interaction.response.send_message(f"❌ {user.mention}'s trial has ended, and they have not been promoted.")
    else:
        await interaction.response.send_message("You don't have permission to manage roles.", ephemeral=True)

# Slash command: Promote to staff
@bot.tree.command(name="promote", description="Promote a user to staff")
@app_commands.describe(user="The user to promote", staff_role="The staff role to assign")
async def promote(interaction: discord.Interaction, user: discord.Member, staff_role: discord.Role):
    if interaction.user.guild_permissions.manage_roles:
        await user.add_roles(staff_role)
        await interaction.response.send_message(f"✅ {user.mention} has been promoted to staff with the role: {staff_role.name}.")
    else:
        await interaction.response.send_message("You don't have permission to manage roles.", ephemeral=True)

# Slash command: Demote from staff
@bot.tree.command(name="demote", description="Demote a staff member")
@app_commands.describe(user="The user to demote", staff_role="The staff role to remove")
async def demote(interaction: discord.Interaction, user: discord.Member, staff_role: discord.Role):
    if interaction.user.guild_permissions.manage_roles:
        await user.remove_roles(staff_role)
        await interaction.response.send_message(f"❌ {user.mention} has been demoted and removed from the staff role: {staff_role.name}.")
    else:
        await interaction.response.send_message("You don't have permission to manage roles.", ephemeral=True)

# Initialize SQLite database
async def init_db():
    async with aiosqlite.connect("partnerships.db") as db:
        await db.execute(""" 
            CREATE TABLE IF NOT EXISTS partnerships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                applier_name TEXT NOT NULL,
                status TEXT NOT NULL
            )
        """)
        await db.commit()

# Slash command: Apply for partnership
@bot.tree.command(name="apply", description="Apply for a partnership")
@app_commands.describe(applier_name="Your name or organization name")
async def apply(interaction: discord.Interaction, applier_name: str):
    async with aiosqlite.connect("partnerships.db") as db:
        await db.execute("INSERT INTO partnerships (applier_name, status) VALUES (?, ?)", (applier_name, "Pending"))
        await db.commit()
    await interaction.response.send_message(f"Partnership application submitted for '{applier_name}'.")

# Slash command: Show partnerships
@bot.tree.command(name="show_partnerships", description="Show all partnership applications")
async def show_partnerships(interaction: discord.Interaction):
    async with aiosqlite.connect("partnerships.db") as db:
        async with db.execute("SELECT id, applier_name, status FROM partnerships") as cursor:
            rows = await cursor.fetchall()

    if rows:
        embed = discord.Embed(title="Partnership Applications", color=discord.Color.blue())
        for row in rows:
            embed.add_field(
                name=f"Application ID: {row[0]}",
                value=f"Name: {row[1]}\nStatus: {row[2]}",
                inline=False,
            )
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message("No partnership applications found.")

# Slash command: Approve a partnership
@bot.tree.command(name="approve", description="Approve a partnership application")
@app_commands.describe(application_id="The ID of the application to approve")
async def approve(interaction: discord.Interaction, application_id: int):
    if interaction.user.guild_permissions.manage_messages:  # Only allow users with permission to approve
        async with aiosqlite.connect("partnerships.db") as db:
            await db.execute("UPDATE partnerships SET status = ? WHERE id = ?", ("Approved", application_id))
            await db.commit()
        await interaction.response.send_message(f"✅ Partnership application ID {application_id} has been approved.")
    else:
        await interaction.response.send_message("You don't have permission to approve partnership applications.", ephemeral=True)

# Slash command: Deny a partnership
@bot.tree.command(name="deny", description="Deny a partnership application")
@app_commands.describe(application_id="The ID of the application to deny")
async def deny(interaction: discord.Interaction, application_id: int):
    if interaction.user.guild_permissions.manage_messages:  # Only allow users with permission to deny
        async with aiosqlite.connect("partnerships.db") as db:
            await db.execute("UPDATE partnerships SET status = ? WHERE id = ?", ("Denied", application_id))
            await db.commit()
        await interaction.response.send_message(f"❌ Partnership application ID {application_id} has been denied.")
    else:
        await interaction.response.send_message("You don't have permission to deny partnership applications.", ephemeral=True)

# Main function to start the bot
async def main():
    await init_db()

# Run the bot
if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())  # Initialize DB before running bot
    bot.run("MTMxNzc4NjA4NjY3MTUxNTczOQ.GYVvYP.6hI9hG2msb7obOAPqm9m9Ea9uvW8VdAkMbbLeM")  # Replace with your bot token
