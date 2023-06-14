from typing import Sequence

import discord.ui
from discord import ButtonStyle, SelectOption, Colour, TextChannel, User
from discord.ui import Select

import utils
from constants import (
    MAX_SELECT_OPTION_COUNT,
    INTERACTION_TIMEOUT,
    SELECT_OPTION_LABEL_MAX_LENGTH,
    EMBED_FIELD_VALUE_MAX_LENGTH,
    ELEMENT_DESCRIPTION_MAX_LENGTH,
)
from models import SearchOptions, SyntaxElement, GuildConfig
from providers import DocumentationProvider, CombinedDocumentationProvider


class SearchView(discord.ui.View):

    @staticmethod
    async def generate_embed(element: SyntaxElement) -> discord.Embed:
        await element.provider.prepare_element_for_display(element)
        if element.description is not None and element.description != "":
            if len(element.description) > 200:
                clamped_description = element.description[
                    :ELEMENT_DESCRIPTION_MAX_LENGTH
                ].strip()
                description = discord.utils.escape_markdown(clamped_description)
                description += "..."
            else:
                description = discord.utils.escape_markdown(element.description)
        else:
            description = "No description available"

        embed = discord.Embed(
            title=element.name,
            description=description,
            colour=element.type.colour,
            url=element.link,
        )

        code_block_len = len("```vb\n\n```")
        if element.examples and len(element.examples) > 0:
            example_field_content = "```vb\n"
            example_field_content += utils.escape_code_block_content(
                element.examples[0]
            )[: EMBED_FIELD_VALUE_MAX_LENGTH - code_block_len]
            example_field_content += "\n```"
            embed.add_field(name="Example", value=example_field_content, inline=True)
        else:
            all_patterns = "\n".join(element.patterns)
            pattern_field_content = "```vb\n"
            pattern_field_content += utils.escape_code_block_content(all_patterns)[
                : EMBED_FIELD_VALUE_MAX_LENGTH - code_block_len
            ]
            pattern_field_content += "\n```"
            embed.add_field(name="Pattern", value=pattern_field_content, inline=False)

        requirements = []
        if element.required_addon is not None:
            if element.required_addon_version is not None:
                requirements.append(
                    f"{element.required_addon} {element.required_addon_version}"
                )
            else:
                requirements.append(element.required_addon)
        if element.required_minecraft_version is not None:
            requirements.append(f"Minecraft {element.required_minecraft_version}+")
        if element.required_plugins is not None:
            for required_plugin in element.required_plugins:
                requirements.append(required_plugin)
        if len(requirements) > 0:
            embed.add_field(
                name="Requirements",
                value=utils.join_english_and(requirements),
                inline=False,
            )

        embed.set_footer(
            text=f"Documentation provided by {element.provider.name}",
            icon_url=element.provider.icon_url,
        )

        return embed

    def __init__(
        self,
        original_interaction: discord.Interaction,
        elements: Sequence[SyntaxElement],
        available_providers: Sequence[DocumentationProvider],
        enabled_providers: Sequence[DocumentationProvider],
        search_options: SearchOptions,
        guild_config: GuildConfig,
        recent_users: Sequence[User],
        default_recent_user_id: int,
    ):
        super().__init__(timeout=INTERACTION_TIMEOUT.total_seconds())
        self.search_options = search_options
        self.original_interaction = original_interaction
        self.elements = elements[: MAX_SELECT_OPTION_COUNT - 1]
        self.guild_config = guild_config

        self.available_providers = available_providers
        self.combined_provider = CombinedDocumentationProvider(enabled_providers)

        self.element_select_menu = self._create_element_select_menu(self.elements)
        if len(elements) > 0:
            self._set_selected_element(self.elements[0])
        self.add_item(self.element_select_menu)

        self.reply_to = default_recent_user_id
        self.recent_users = recent_users
        if (
            isinstance(original_interaction.channel, TextChannel)
            and len(recent_users) > 0
        ):
            self.reply_select_menu = self._create_reply_select_menu(
                self.recent_users, default_recent_user_id
            )
            self.add_item(self.reply_select_menu)

        if not guild_config.enforce_preferred_providers:
            self.provider_select_menu = self._create_provider_select_menu(
                self.available_providers
            )
            self.add_item(self.provider_select_menu)

        self.confirm_button = discord.ui.Button(
            label="Confirm", style=ButtonStyle.green
        )
        self.confirm_button.callback = self.handle_confirm
        self.add_item(self.confirm_button)

        if len(self.elements) == 0:
            self.confirm_button.disabled = True
            self.element_select_menu.disabled = True

        self.cancel_button = discord.ui.Button(label="Cancel", style=ButtonStyle.red)
        self.cancel_button.callback = self.handle_cancel
        self.add_item(self.cancel_button)

    def _create_reply_select_menu(
        self, users: Sequence[discord.User], default_recent_user_id: int
    ) -> Select:
        reply_select_menu = Select(
            placeholder="Who is this for?",
            min_values=0,
            options=[
                SelectOption(
                    label=user.display_name,
                    value=str(user.id),
                    default=user.id == default_recent_user_id,
                )
                for user in users
            ],
        )
        reply_select_menu.callback = self.handle_reply_select
        return reply_select_menu

    def _create_element_select_menu(self, elements: Sequence[SyntaxElement]) -> Select:
        if len(elements) > 0:
            options = [
                SelectOption(
                    label=element.detailed_name[:SELECT_OPTION_LABEL_MAX_LENGTH],
                    value=element.provider_specific_id,
                    emoji=element.type.emoji,
                )
                for element in elements
            ]
        else:
            options = [SelectOption(label="No results")]
        element_select_menu = Select(
            placeholder="Results",
            options=options,
        )
        element_select_menu.callback = self.handle_element_select
        return element_select_menu

    def _create_provider_select_menu(
        self, providers: Sequence[DocumentationProvider]
    ) -> Select:
        enabled_provider_names = tuple(
            provider.name for provider in self.combined_provider.providers
        )
        provider_select_menu = Select(
            placeholder="Sources",
            max_values=len(providers),
            options=list(
                SelectOption(
                    label=provider.name,
                    value=provider.name,
                    default=(provider.name in enabled_provider_names),
                )
                for provider in providers
            ),
        )
        provider_select_menu.callback = self.handle_provider_select
        return provider_select_menu

    def _disable_ui(self):
        for child in self.children:
            child.disabled = True

    def _set_selected_element(self, element: SyntaxElement):
        for option in self.element_select_menu.options:
            option.default = option.value == element.provider_specific_id

    async def on_timeout(self) -> None:
        self._disable_ui()
        await self.original_interaction.edit_original_response(view=self)
        self.stop()

    async def handle_reply_select(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.reply_to = next(iter(self.reply_select_menu.values), None)

    async def handle_element_select(self, interaction: discord.Interaction):
        await interaction.response.defer()
        selected_element = next(
            element
            for element in self.elements
            if element.provider_specific_id == self.element_select_menu.values[0]
        )
        self._set_selected_element(selected_element)
        await self.original_interaction.edit_original_response(
            view=self, embeds=(await SearchView.generate_embed(selected_element),)
        )

    async def handle_provider_select(self, interaction: discord.Interaction):
        await interaction.response.defer()
        selected_providers = tuple(
            provider
            for provider in self.available_providers
            if provider.name in self.provider_select_menu.values
        )
        new_combined_provider = CombinedDocumentationProvider(selected_providers)
        results = await new_combined_provider.perform_search(self.search_options)
        if len(results) > 0:
            self.element_select_menu.disabled = False
            self.confirm_button.disabled = False
            await self.original_interaction.edit_original_response(
                content="",
                view=SearchView(
                    self.original_interaction,
                    results,
                    self.available_providers,
                    selected_providers,
                    self.search_options,
                    self.guild_config,
                    self.recent_users,
                ),
                embeds=(await SearchView.generate_embed(results[0]),),
            )
        else:
            query = self.search_options.query
            queried_providers = utils.join_english_or(
                tuple(provider.name for provider in new_combined_provider.providers)
            )
            await self.original_interaction.edit_original_response(
                content=f"No results found for {discord.utils.escape_markdown(query)} on {queried_providers}",
                view=SearchView(
                    self.original_interaction,
                    results,
                    self.available_providers,
                    selected_providers,
                    self.search_options,
                    self.guild_config,
                    self.recent_users,
                    self.reply_to
                ),
                embeds=tuple(),
            )

    async def handle_confirm(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.stop()
        self._disable_ui()
        original_response = await self.original_interaction.original_response()
        if self.reply_to is None:
            await interaction.channel.send(embeds=original_response.embeds)
        else:
            reply_text = f"Hey <@{self.reply_to}>, {interaction.user.display_name} thought this might help you!"
            await interaction.channel.send(
                content=reply_text, embeds=original_response.embeds
            )
        await original_response.delete()

    async def handle_cancel(self, interaction: discord.Interaction):
        await interaction.response.defer()

        self.stop()
        await self.original_interaction.delete_original_response()
