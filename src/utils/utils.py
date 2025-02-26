import re


def escape_markdown_v2(text: str) -> str:
    """Escapes special characters for Telegram's MarkdownV2 format.

    Args:
        text (str): The input text to be escaped.

    Returns:
        str: The escaped text.
    """
    special_chars = r"_*[]()~`>#+-=|{}.!"
    return re.sub(r"([" + re.escape(special_chars) + r"])", r"\\\1", text)
