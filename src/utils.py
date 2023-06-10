from typing import Sequence


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
