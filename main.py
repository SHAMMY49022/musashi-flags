import discord
from discord.ext import commands
import os
import requests
from flask import Flask, request, redirect
from threading import Thread

# --- Configuration (Loaded from Railway's Variables) ---
try:
    BOT_TOKEN = os.environ['BOT_TOKEN']
    CLIENT_ID = os.environ['CLIENT_ID']
    CLIENT_SECRET = os.environ['CLIENT_SECRET']
    REDIRECT_URI = os.environ['REDIRECT_URI']
    GUILD_ID = int(os.environ['GUILD_ID'])
    BOT_OWNER_IDS_STR = os.environ.get('BOT_OWNER_IDS', '')
    BOT_OWNER_IDS = [int(id.strip()) for id in BOT_OWNER_IDS_STR.split(',') if id.strip()]
except KeyError as e:
    print(f"FATAL ERROR: The environment variable '{e.args[0]}' is not set.")
    exit()

# This dictionary maps your server's Role IDs to the metadata keys.
ROLE_MAPPING = {
    1400496639680057407: "founder",
    1400496639680057406: "manager",
    1400496639675990026: "developer",
    1400496639675990033: "moderation_team",
    1400496639675990028: "event_management",
    1401960472269291520: "sky",
}

# --- Discord Bot Setup ---
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="?", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} ({bot.user.id})")
    print("Boolean Linked Roles Bot is operational on Railway.")

@bot.event
async def on_command_error(ctx, error):
    # ... (Error handler code is the same)
    if isinstance(error, commands.CommandNotFound): return
    elif isinstance(error, commands.MissingRequiredArgument): await ctx.send(f"Usage: `?{ctx.command.name} {ctx.command.signature}`")
    elif isinstance(error, commands.BadArgument): await ctx.send("Invalid argument provided.")
    elif isinstance(error, discord.Forbidden): await ctx.send("I don't have permissions to do that.")
    else:
        print(f"An unhandled error occurred: {error}")
        await ctx.send("An unexpected error occurred.")

@bot.command()
async def selfrole(ctx, member: discord.Member, role_id: int):
    # ... (selfrole command code is the same)
    if ctx.author.id not in BOT_OWNER_IDS: return await ctx.send("This command is for the bot owner only.")
    role = ctx.guild.get_role(role_id)
    if role is None: return await ctx.send(f"Role with ID `{role_id}` not found.")
    await member.add_roles(role)
    await ctx.send(f"✅ Gave **{role.name}** to **{member.display_name}**.")

# ... (gban command is also the same)

# --- Web Server for OAuth2 Authentication ---
app = Flask(__name__)
@app.route('/linked-role')
async def oauth_callback():
    code = request.args.get('code')
    if not code: return "Error: No code provided.", 400
    data = { 'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET, 'grant_type': 'authorization_code', 'code': code, 'redirect_uri': REDIRECT_URI }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    try:
        token_response = requests.post('https://discord.com/api/v10/oauth2/token', data=data, headers=headers)
        token_response.raise_for_status()
        access_token = token_response.json()['access_token']
    except requests.RequestException: return "Failed to authenticate.", 500
    headers = {'Authorization': f'Bearer {access_token}'}
    try:
        user_response = requests.get('https://discord.com/api/v10/users/@me', headers=headers)
        user_response.raise_for_status()
        user_id = int(user_response.json()['id'])
    except requests.RequestException: return "Failed to retrieve user info.", 500
    guild = bot.get_guild(GUILD_ID)
    if not guild: return "Server config error.", 500
    member = guild.get_member(user_id)
    metadata = {} 
    if member:
        member_role_ids = {role.id for role in member.roles}
        for role_id, key in ROLE_MAPPING.items():
            if role_id in member_role_ids:
                metadata[key] = 1
    url = f'https://discord.com/api/v10/users/@me/applications/{CLIENT_ID}/role-connection'
    payload = { 'platform_name': 'Server Staff Roles', 'metadata': metadata }
    try:
        requests.put(url, json=payload, headers=headers).raise_for_status()
    except requests.RequestException: return "Error updating linked role.", 500
    return "<h1>✅ Verification Successful!</h1><p>Your roles have been linked.</p>"

def run_web_server():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    flask_thread = Thread(target=run_web_server)
    flask_thread.daemon = True
    flask_thread.start()
    bot.run(BOT_TOKEN)
