import html
import logging
from abc import abstractmethod, ABCMeta
from typing import Sequence, Optional
from urllib.parse import quote_plus
from datetime import datetime, timedelta

import httpx

from constants import MAX_SELECT_OPTION_COUNT, PROVIDER_TIMEOUT, USER_AGENT
from models import SearchOptions, SyntaxElement, SyntaxType


def _convert_addon_version(addon_version: Optional[str]) -> Optional[str]:
    if addon_version is None:
        return None
    casefold_addon_version = addon_version.strip().casefold()
    if casefold_addon_version == "unknown":
        return None
    elif casefold_addon_version.startswith("unknown"):
        return addon_version[len("unknown"):].strip()
    return addon_version


class DocumentationProvider(metaclass=ABCMeta):
    # TODO: caching!
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def icon_url(self) -> str:
        pass

    @abstractmethod
    async def perform_search(self, options: SearchOptions) -> Sequence[SyntaxElement]:
        pass

    async def prepare_element_for_display(self, element: SyntaxElement) -> None:
        pass


class SkriptLangDocumentationProvider(DocumentationProvider):

    def __init__(self):
        self.all_elements = None
        self.last_request_time = None

    @staticmethod
    def _compute_event_values(element: dict) -> Optional[Sequence[str]]:
        return None

    def _convert_element(self, type: SyntaxType, element: dict) -> SyntaxElement:
        examples = None
        if "examples" in element:
            examples = [element["examples"].join("\n")]
        return SyntaxElement(
            id=element["id"],
            provider=self,
            name=element["name"],
            description=element.get("description", []).join("\n"),
            patterns=html.unescape(element["patterns"].join("\n")),
            examples=examples,
            required_addon="Skript",
            required_addon_version=element["since"],
            required_minecraft_version=None,
            type=type,
            required_plugins=None,
            return_type=element.get("return-type", None),
            event_values=None,
            cancellable=None,
            link=f"https://docs.skriptlang.org/docs.html?search=#{quote_plus(element['id'])}",
        )

    
    @staticmethod
    def _compute_match_level(query: str, element: SyntaxElement) -> Optional[int]:
        name_matches = query in element.description
        description_matches = query in element.description
        if name_matches and description_matches:
            return 1
        elif name_matches:
            return 2
        elif description_matches:
            return 3
        else:
            return None

    @staticmethod
    async def _get_all_elements() -> Sequence[SyntaxElement]:
        async with httpx.AsyncClient(timeout=PROVIDER_TIMEOUT.total_seconds()) as client:
            response = await client.get("https://docs.skriptlang.org/docs.json")
            response.raise_for_status()
            response_body = response.json()
            all_elements = []
            for type, key in (
                (SyntaxType.CONDITION, "conditions"),
                (SyntaxType.EFFECT, "effects"),
                (SyntaxType.EXPRESSION, "expressions"),
                (SyntaxType.EVENT, "events"),
                (SyntaxType.CLASSINFO, "classes"),
                (SyntaxType.STRUCTURE, "structures"),
                (SyntaxType.SECTION, "sections"),
                (SyntaxType.FUNCTION, "functions"),
            ):
                all_elements += [
                    SkriptLangDocumentationProvider._convert_element(type, element)
                    for element in response_body[key]
                ]
        return all_elements
    
    async def perform_search(self, options: SearchOptions) -> Sequence[SyntaxElement]:
        if self.all_elements is None or (datetime.now() - self.last_request_time) > timedelta(hours=1):
            self.last_request_time = datetime.now()
            self.all_elements = SkriptLangDocumentationProvider._get_all_elements()
        matching_elements = [element for element in self.all_elements if SkriptLangDocumentationProvider._compute_match_level(options.query, element) is not None]
        matching_elements.sort(key=lambda element: SkriptLangDocumentationProvider._compute_match_level(options.query, element))
        return matching_elements

    async def prepare_element_for_display(self, element: SyntaxElement) -> None:
        if element.provider.name != self.name:
            raise ValueError(
                f"'element' was provided by {element.provider.name}, but must be provided by {self.name}"
            )

    @property
    def name(self):
        return "SkriptLang"

    @property
    def icon_url(self):
        return "https://docs.skriptlang.org/assets/icon.png"

class SkriptHubDocumentationProvider(DocumentationProvider):
    def __init__(self, token: str):
        self.headers = (("Authorization", f"Token {token}"), ("User-Agent", USER_AGENT))

    @staticmethod
    def _compute_type(element: dict) -> SyntaxType:
        if element["syntax_type"] == "type":
            return SyntaxType.CLASSINFO
        return SyntaxType[element["syntax_type"].upper()]

    @staticmethod
    def _compute_event_values(element: dict) -> Optional[Sequence[str]]:
        if element["event_values"] is not None:
            return tuple(
                piece.strip()
                for piece in element["event_values"].split(", ")
                if piece.strip() != ""
            )
        return None

    def _convert_element(self, element: dict) -> SyntaxElement:
        return SyntaxElement(
            id=element["id"],
            provider=self,
            name=element["title"],
            description=element["description"],
            patterns=html.unescape(element["syntax_pattern"]).split("\n"),
            examples=None,
            required_addon=element["addon"],
            required_addon_version=_convert_addon_version(
                element["compatible_addon_version"]
            ),
            required_minecraft_version=element["compatible_minecraft_version"],
            type=SkriptHubDocumentationProvider._compute_type(element),
            required_plugins=tuple(
                plugin["name"] for plugin in element["required_plugins"]
            ),
            return_type=element["return_type"],
            event_values=SkriptHubDocumentationProvider._compute_event_values(element),
            cancellable=element["event_cancellable"],
            link=element["link"],
        )

    async def perform_search(self, options: SearchOptions) -> Sequence[SyntaxElement]:
        async with httpx.AsyncClient(
            headers=self.headers, timeout=PROVIDER_TIMEOUT.total_seconds()
        ) as client:
            query_params = {"search": options.query}
            response = await client.get(
                "https://skripthub.net/api/v1/syntax/", params=query_params
            )
            response.raise_for_status()
            return tuple(self._convert_element(element) for element in response.json())

    async def prepare_element_for_display(self, element: SyntaxElement) -> None:
        if element.provider.name != self.name:
            raise ValueError(
                f"'element' was provided by {element.provider.name}, but must be provided by {self.name}"
            )
        if element.examples is None:
            async with httpx.AsyncClient(
                headers=self.headers, timeout=PROVIDER_TIMEOUT.total_seconds()
            ) as client:
                query_params = {"syntax": element.id}
                response = await client.get(
                    "https://skripthub.net/api/v1/syntaxexample/", params=query_params
                )
                response.raise_for_status()
                element.examples = tuple(
                    example["example_code"] for example in response.json()
                )

    @property
    def name(self):
        return "Skript Hub"

    @property
    def icon_url(self):
        return "https://i.imgur.com/YkzJ97l.png"


class SkUnityDocumentationProvider(DocumentationProvider):
    def __init__(self, key: str):
        self.key = key
        self.headers = (("User-Agent", USER_AGENT),)

    @staticmethod
    def _compute_type(element: dict) -> SyntaxType:
        syntax_type_name = element["doc"]
        if syntax_type_name == "types" or syntax_type_name == "classes":
            return SyntaxType.CLASSINFO
        if syntax_type_name == "expression":
            return SyntaxType.EXPRESSION
        syntax_type_name = syntax_type_name[:len(syntax_type_name) - 1]
        return SyntaxType[syntax_type_name.upper()]

    @staticmethod
    def _compute_event_values(element: dict) -> Optional[Sequence[str]]:
        if element["eventvalues"] is not None:
            return element["eventvalues"].split("\n")
        return None

    def _convert_element(self, element: dict) -> SyntaxElement:
        return SyntaxElement(
            id=element["id"],
            provider=self,
            name=element["name"],
            description=element["desc"],
            patterns=html.unescape(element["pattern"]).split("\n"),
            examples=None,
            required_addon=element["addon"],
            required_addon_version=_convert_addon_version(element["version"]),
            required_minecraft_version=None,  # TODO: this
            type=SkUnityDocumentationProvider._compute_type(element),
            required_plugins=tuple(element["plugin"]),
            return_type=element["returntype"],
            event_values=SkUnityDocumentationProvider._compute_event_values(element),
            cancellable=None,
            link=f"https://docs.skunity.com/syntax/search/id:{element['id']}",
        )

    async def perform_search(self, options: SearchOptions) -> Sequence[SyntaxElement]:
        async with httpx.AsyncClient(headers=self.headers, timeout=PROVIDER_TIMEOUT.total_seconds()) as client:
            response = await client.get(
                f"https://api.skunity.com/v1/{quote_plus(self.key)}/docs/search/{quote_plus(options.query)}"
            )
            response.raise_for_status()
            response_body = response.json()
            elements = response_body["result"]
            return tuple(self._convert_element(element) for element in elements)

    async def prepare_element_for_display(self, element: SyntaxElement) -> None:
        if element.provider.name != self.name:
            raise ValueError(
                f"'element' was provided by {element.provider.name}, but must be provided by {self.name}"
            )
        if element.examples is None:
            async with httpx.AsyncClient(headers=self.headers, timeout=PROVIDER_TIMEOUT.total_seconds()) as client:
                response = await client.get(
                    f"https://api.skunity.com/v1/{quote_plus(self.key)}/docs/getExamplesByID/{quote_plus(element.id)}"
                )
                response.raise_for_status()
                example_response = response.json()["result"]
                if isinstance(example_response, list):
                    return
                element.examples = tuple(
                    html.unescape(example_object["example"])
                    for example_object in example_response.values() if isinstance(example_object, dict) and example_object.get("example")
                )

    @property
    def name(self):
        return "skUnity"

    @property
    def icon_url(self):
        return "https://i.imgur.com/Ci6jjhv.png"


class CombinedDocumentationProvider(DocumentationProvider):
    def __init__(self, providers: Sequence[DocumentationProvider]):
        self.providers = list(providers)

    async def perform_search(self, options: SearchOptions) -> Sequence[SyntaxElement]:
        discovered_elements = {}
        elements = []
        for provider in self.providers:
            if len(elements) >= MAX_SELECT_OPTION_COUNT:
                break
            # noinspection PyBroadException
            try:
                results = await provider.perform_search(options)
                for result in results:
                    if result.detailed_name not in discovered_elements:
                        discovered_elements[result.detailed_name] = True
                        elements.append(result)
            except Exception:
                logging.error(
                    f"Provider {provider.name} failed to provide results", exc_info=True
                )
        return elements[: MAX_SELECT_OPTION_COUNT - 1]

    @property
    def name(self):
        return f"CombinedDocumentationProvider({list(provider.name for provider in self.providers)}"

    @property
    def icon_url(self):
        raise AttributeError()
