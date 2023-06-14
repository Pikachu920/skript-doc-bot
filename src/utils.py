from typing import Sequence

import discord
from discord import User, Member
from discord.abc import Messageable


def escape_code_block_content(content: str) -> str:
    return content.replace("`", "`\u200B`\u200B`\u200B")


def join_english_and(parts: Sequence[str]) -> str:
    if len(parts) > 2:
        return f"{', '.join(parts[:-1])}, and {parts[-1]}"
    elif len(parts) == 2:
        return " and ".join(parts)
    elif len(parts) == 1:
        return parts[0]


def join_english_or(parts: Sequence[str]) -> str:
    if len(parts) > 2:
        return f"{', '.join(parts[:-1])}, or {parts[-1]}"
    elif len(parts) == 2:
        return " or ".join(parts)
    elif len(parts) == 1:
        return parts[0]


async def try_to_get_recent_users(
    bot: discord.Client,
    channel: Messageable,
    excluded_user_ids: Sequence[int],
    message_limit: int = 25,
) -> Sequence[User]:
    async def convert_to_user(
        message: discord.Message,
    ) -> discord.User | discord.Member:
        guild = message.guild
        if guild is not None:
            try:
                fetched_member = await guild.fetch_member(message.author.id)
                if fetched_member is not None:
                    return fetched_member
            except discord.errors.NotFound:
                pass
        return await bot.fetch_user(message.author.id)

    try:
        unique_authors = {
            message.author.id: message
            async for message in channel.history(limit=message_limit)
            if message.author.id not in excluded_user_ids and not message.author.bot
        }
        return [await convert_to_user(message) for message in unique_authors.values()]
    except discord.Forbidden:
        return tuple()


def get_appropriate_name(user: discord.User | discord.Member) -> str:
    if isinstance(user, Member):
        return user.display_name
    return user.mention
