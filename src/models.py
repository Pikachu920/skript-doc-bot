from dataclasses import dataclass
from enum import Enum
from typing import Sequence, Optional, TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from providers import DocumentationProvider


@dataclass
class SearchOptions:
    query: str


class SyntaxType(Enum):

    EFFECT = "effect",
    CONDITION = "condition"
    EXPRESSION = "expression"
    SECTION = "section"
    FUNCTION = "function"
    EVENT = "event"
    CLASSINFO = "classinfo"

    @property
    def colour(self) -> discord.Colour:
        match self:
            case SyntaxType.EFFECT:
                return discord.Colour.from_rgb(1, 120, 255)
            case SyntaxType.CONDITION:
                return discord.Colour.from_rgb(255, 61, 61)
            case SyntaxType.SECTION:
                return discord.Colour.from_rgb(26, 188, 156)
            case SyntaxType.FUNCTION:
                return discord.Colour.from_rgb(180, 180, 180)
            case SyntaxType.EVENT:
                return discord.Colour.from_rgb(167, 99, 255)
            case SyntaxType.CLASSINFO:
                return discord.Colour.from_rgb(243, 156, 18)
            case SyntaxType.EXPRESSION:
                return discord.Colour.from_rgb(13, 229, 5)
            case _:
                raise ValueError(f"Unimplemented SyntaxType {self.name}")

    @property
    def emoji(self) -> str:
        match self:
            case SyntaxType.EFFECT:
                return "🇪🇺"
            case SyntaxType.CONDITION:
                return "🟥"
            case SyntaxType.SECTION:
                return "🟦"
            case SyntaxType.FUNCTION:
                return "⬜"
            case SyntaxType.EVENT:
                return "🟪"
            case SyntaxType.CLASSINFO:
                return "🟧"
            case SyntaxType.EXPRESSION:
                return "🟩"
            case _:
                raise ValueError(f"Unimplemented SyntaxType {self.name}")

@dataclass
class SyntaxElement:
    id: str
    provider: "DocumentationProvider"
    name: str
    description: str
    patterns: Sequence[str]
    examples: Optional[Sequence[str]]
    required_addon: Optional[str]
    required_addon_version: Optional[str]
    required_minecraft_version: Optional[str]
    type: SyntaxType
    required_plugins: Optional[Sequence[str]]
    return_type: Optional[str]
    event_values: Optional[Sequence[str]]
    cancellable: Optional[bool]
    link: Optional[str]

    @property
    def provider_specific_id(self) -> str:
        return f"{self.provider.name}:{self.id}"

    @property
    def detailed_name(self) -> str:
        return f"{self.required_addon}: {self.name}"


@dataclass
class GuildConfig:
    preferred_providers: Optional[Sequence[str]]
    enforce_preferred_providers: Optional[bool]
