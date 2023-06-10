import logging
import os

import discord
from asynctinydb import TinyDB, Query
from discord import app_commands

from discord.ext import commands

import utils
from models import SearchOptions, GuildConfig
from providers import (
    SkriptHubDocumentationProvider,
    SkUnityDocumentationProvider,
    CombinedDocumentationProvider,
)
from views import SearchView

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="/", description="Skript bot", intents=intents)

providers = {
    "skripthub": SkriptHubDocumentationProvider(os.environ["SKRIPT_SKRIPTHUB_TOKEN"]),
    "skunity": SkUnityDocumentationProvider(os.environ["SKRIPT_SKUNITY_KEY"]),
}

database = TinyDB("data.json")
config_table = database.table("configurations")


@bot.event
async def on_ready():
    logging.info(f"Logged in as {bot.user} (ID: {bot.user.id})")


async def get_guild_config(guild_id: int) -> GuildConfig:
    guild_config_records = await config_table.search(
        Query().guild_id == guild_id, limit=1
    )
    if len(guild_config_records) == 0:
        return GuildConfig(enforce_preferred_providers=None, preferred_providers=None)
    # noinspection PyTypeChecker
    raw_guild_config = guild_config_records[0]["config"]
    return GuildConfig(**raw_guild_config)


async def set_guild_config(guild_id: int, guild_config: GuildConfig) -> None:
    await config_table.upsert(
        {"guild_id": guild_id, "config": guild_config.__dict__},
        Query().guild_id == guild_id,
    )


@bot.tree.command(
    name="get-sources",
    description="Displays the preferred documentation sources used for searches",
)
@app_commands.checks.has_permissions(administrator=True)
async def handle_get_sources_command(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    guild_config = await get_guild_config(interaction.guild_id)
    preferred_providers = guild_config.preferred_providers
    if preferred_providers is not None:
        await interaction.followup.send(
            f"Sources are set to {utils.join_english_and(guild_config.preferred_providers)}",
            ephemeral=True,
        )
    else:
        await interaction.followup.send(
            f"No sources are set",
            ephemeral=True,
        )


@bot.tree.command(
    name="set-sources",
    description="Sets the preferred documentation sources used for searches",
)
@app_commands.describe(sources="The sources to use seperated by commas")
@app_commands.checks.has_permissions(administrator=True)
async def handle_set_sources_command(interaction: discord.Interaction, sources: str):
    await interaction.response.defer(ephemeral=True)

    guild_config = await get_guild_config(interaction.guild_id)
    if sources == "default":
        guild_config.preferred_providers = None
        await set_guild_config(interaction.guild_id, guild_config)
        await interaction.followup.send(
            f"Sources reset to default",
            ephemeral=True,
        )
        return

    preferred_providers = []
    for source in sources.split(","):
        source = source.lower()
        if source not in providers:
            await interaction.followup.send(
                f"No such source {discord.utils.escape_markdown(source)}",
                ephemeral=True,
            )
            return
        preferred_providers.append(source)

    guild_config.preferred_providers = preferred_providers
    await set_guild_config(interaction.guild_id, guild_config)
    await interaction.followup.send(f"Sources set successfully", ephemeral=True)


@bot.tree.command(
    name="set-sources-enforced",
    description="Allows you to enforce the use of the preferred sources",
)
@app_commands.describe(enforced="Whether to enforce the preferred sources")
@app_commands.checks.has_permissions(administrator=True)
async def handle_set_sources_enforce_command(
    interaction: discord.Interaction, enforced: bool
):
    await interaction.response.defer(ephemeral=True)
    guild_config = await get_guild_config(interaction.guild_id)
    guild_config.enforce_preferred_providers = enforced
    await set_guild_config(interaction.guild_id, guild_config)
    if enforced:
        await interaction.followup.send("Sources are now enforced", ephemeral=True)
    else:
        await interaction.followup.send("Sources are now not enforced", ephemeral=True)


@bot.tree.command(name="docs", description="Searches Skript documentation")
@app_commands.describe(query="The query to search for")
async def handle_sources_command(interaction: discord.Interaction, query: str):
    await interaction.response.defer(ephemeral=True)

    guild_config = await get_guild_config(interaction.guild_id)
    if guild_config.preferred_providers is not None:
        available_providers = []
        for preferred_provider in guild_config.preferred_providers:
            available_providers.append(providers[preferred_provider])
    else:
        available_providers = providers.values()
    doc_provider = CombinedDocumentationProvider(available_providers)

    search_options = SearchOptions(query=query)
    results = await doc_provider.perform_search(search_options)

    if len(results) > 0:
        await interaction.followup.send(
            view=SearchView(
                interaction,
                results,
                doc_provider.providers,
                doc_provider.providers,
                search_options,
                guild_config,
            ),
            embed=await SearchView.generate_embed(results[0]),
            ephemeral=True,
        )
    else:
        await interaction.followup.send(
            f"No results found for {discord.utils.escape_markdown(query)}",
            ephemeral=True,
        )


bot.run(os.environ["SKRIPT_DISCORD_TOKEN"])