from dataclasses import dataclass
from enum import Enum
from typing import Sequence, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from providers import DocumentationProvider


@dataclass
class SearchOptions:
    query: str


class SyntaxType(Enum):
    EFFECT = "effect"
    CONDITION = "condition"
    EXPRESSION = "expression"
    SECTION = "section"
    FUNCTION = "function"
    EVENT = "event"
    CLASSINFO = "classinfo"


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
