"""
lettuce_bot.py
A fun Discord bot that monitors chat for "lettuce" (and sneaky permutations),
deletes the offending message, and posts a loud public warning.

Also includes a manual trigger command (!inspect) so a moderator can run the
check on demand instead of waiting for auto-detection.

Requirements:
  pip install "discord.py>=2.3"

Setup:
  1. Go to https://discord.com/developers/applications
  2. Create an app -> Bot tab -> copy the token
  3. Under "Privileged Gateway Intents" enable:
       - MESSAGE CONTENT INTENT  (required to read message text)
  4. Invite the bot with scopes: bot
     Permissions needed:
       - Read Messages / View Channels
       - Send Messages
       - Manage Messages  (to delete the flagged message)
  5. Set your token as an environment variable (do NOT hardcode it):
       export DISCORD_TOKEN="your-token-here"        # macOS/Linux
       set DISCORD_TOKEN=your-token-here              # Windows (cmd)
  6. python lettuce_bot.py

SECURITY NOTE: never commit a real bot token to a file or paste it into chat.
If a token has ever been exposed, reset it immediately in the Developer Portal.
"""

import os
import re
import discord
from discord.ext import commands

# --- Config -----------------------------------------------------------------

# Token is loaded from the environment. Set DISCORD_TOKEN before running.
TOKEN = os.environ.get("DISCORD_TOKEN")

# Command prefix for manual commands like !inspect
COMMAND_PREFIX = "!"

# The public warning message posted after a detection.
# {user} is replaced with the @ mention of the offender.
# {context} is replaced with the (spoilered) original message text.
WARNING_TEMPLATE = (
    "<a:siren:1507766030355923164> **BANNED PRODUCE ALERT** <a:siren:1507766030355923164>\n"
    "{user} tried to bring banned produce into chat -- and that's not allowed here.\n"
    "Their message has been composted. \n"
    "\n"
    "Context: {context}"
)

# Whether to delete the original message (requires Manage Messages permission).
DELETE_MESSAGE = True

# --- Regex -- catches "lettuce" plus common permutations --------------------
#
# Covers:
#   - Basic:          lettuce, Lettuce, LETTUCE
#   - Leet-speak:     l3ttuc3, l3ttuce, l3ttu(c|k)e, etc.
#   - Letter swap:    letuce, letttuce, lettuc, lettuuce (repeats)
#   - Separator spam: l-e-t-t-u-c-e, l.e.t.t.u.c.e, l e t t u c e
#   - Unicode lookalikes for l, e, t, u, c
#
# The separator pattern [\W_]* allows zero or more non-word chars between
# every letter, catching things like "l e t t u c e" or "l3ttu(c)e".

_SEP = r"[\s\._\-,\*\/]*"

_L = r"(?:[lL1!|\u0142\u028f\u013a\u013c\u013e\u0140\u0142]|\|_)+"
_E = r"(?:[eE3\u20ac\u0259\u0454\u0435\u0451])+"
_T = r"(?:[tT7+\u2020\u03c4\u0442])+"
_U = r"(?:[uU\u03bc\u03c5\u0446]|\|/\|)+"
_C = r"(?:[cC\u00a9\u00e7\u00a2\u0107\u0109\u010b\u010d\u0441\(])+"

LETTUCE_RE = re.compile(
    rf"{_L}{_SEP}{_E}{_SEP}{_T}{_SEP}{_T}{_SEP}{_U}{_SEP}{_C}{_SEP}{_E}",
    re.IGNORECASE | re.MULTILINE,
)

# --- Bot ----------------------------------------------------------------

intents = discord.Intents.default()
intents.message_content = True          # privileged -- must be enabled in dev portal

bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)


def spoiler_matches(text: str) -> str:
    """Wrap every lettuce match in spoiler+strikethrough tags."""
    return LETTUCE_RE.sub(lambda m: f"||~~{m.group(0)}~~||", text)


async def run_inspection(channel: discord.abc.Messageable, offender: str, content: str,
                          delete_target: discord.Message | None = None) -> str:
    """
    Runs the lettuce check against `content`, optionally deletes `delete_target`,
    and posts the warning. Returns the matched text (or "" if nothing matched).
    """
    match = LETTUCE_RE.search(content)
    matched_word = match.group(0) if match else ""

    if delete_target is not None and DELETE_MESSAGE:
        try:
            await delete_target.delete()
        except discord.Forbidden:
            print(f"WARNING: Missing 'Manage Messages' permission in #{channel}")
        except discord.NotFound:
            pass  # message was already gone

    spoilered = spoiler_matches(content) if matched_word else content
    warning = WARNING_TEMPLATE.format(user=offender, context=spoilered)
    await channel.send(warning)
    return matched_word


@bot.event
async def on_ready():
    print("")
    print(f"Produce Inspector online as {bot.user} (ID: {bot.user.id})")
    print("Watching all channels for banned produce...")


@bot.event
async def on_message(message: discord.Message):
    # Ignore messages from bots (including ourselves)
    if message.author.bot:
        return

    # Let commands (like !inspect) run first
    await bot.process_commands(message)

    # Skip auto-detection on command invocations
    if message.content.startswith(COMMAND_PREFIX):
        return

    match = LETTUCE_RE.search(message.content)
    if not match:
        return

    matched_word = match.group(0)
    channel = message.channel
    offender = message.author.mention

    await run_inspection(channel, offender, message.content, delete_target=message)

    print(
        f"[BANNED PRODUCE / LETTUCE DETECTED] "
        f"User: {message.author} | "
        f"Channel: #{channel} | "
        f"Matched: '{matched_word}' | "
        f"Original: '{message.content[:80]}'"
    )


@bot.command(name="inspect")
@commands.has_permissions(manage_messages=True)
async def inspect(ctx: commands.Context, *, arg: str = ""):
    """
    Manually trigger the produce inspector.

    Usage:
      !inspect                  -> checks the message you replied to
      !inspect some text        -> checks the given text
      !inspect force            -> (while replying) forces a warning even if
                                    the replied message doesn't match
    Requires: Manage Messages permission.
    """
    force = False
    target_message: discord.Message | None = None
    offender = ctx.author.mention
    content = arg

    # If this command is a reply, use the replied-to message as the target
    if ctx.message.reference and ctx.message.reference.message_id:
        try:
            target_message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
        except discord.NotFound:
            target_message = None

    if target_message is not None:
        offender = target_message.author.mention
        content = target_message.content
        if arg.strip().lower() == "force":
            force = True

    if not content and not force:
        await ctx.send(
            "Reply to a message with `!inspect` to check it, or run "
            "`!inspect <text>` to check specific text."
        )
        return

    match = LETTUCE_RE.search(content) if content else None

    if not match and not force:
        await ctx.send("No banned produce detected. This message is clean. ")
        return

    matched_word = await run_inspection(
        ctx.channel,
        offender,
        content if content else "(forced check, no message content)",
        delete_target=target_message if (match or force) else None,
    )

    print(
        f"[MANUAL INSPECTION] "
        f"By: {ctx.author} | "
        f"Channel: #{ctx.channel} | "
        f"Matched: '{matched_word}' | "
        f"Forced: {force}"
    )


@inspect.error
async def inspect_error(ctx: commands.Context, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("You need the **Manage Messages** permission to use this command.")
    else:
        raise error


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit(
            "No token found. Set the DISCORD_TOKEN environment variable before running:\n"
            '  export DISCORD_TOKEN="your-token-here"   (macOS/Linux)\n'
            "  set DISCORD_TOKEN=your-token-here         (Windows cmd)"
        )
    bot.run(TOKEN)