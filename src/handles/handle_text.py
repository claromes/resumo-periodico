from typing import Optional

from telegram import Update
from telegram.ext import CallbackContext

from generative import generate_response


def get_prompt(question: str) -> str:
    """
    Generates a formatted prompt for an objective response based on a question and article content.

    Args:
        question (str): The question asked by the user.

    Returns:
        str: The formatted string containing the question and article content.
    """
    return f"Pergunta baseada no artigo em anexo, estruturado em JSON:\n\n'{question}'\n\nResponda de forma objetiva, em português (PT-BR) e em plain text, porém, ao referenciar trechos de textos, mantenha o idioma original."


async def handle_text(update: Update, context: CallbackContext) -> None:
    """
    Handles a user's text input, generates a response based on the article content, and sends it back to the user.

    Args:
        update (Update): The update object representing the incoming message and its context.
        context (CallbackContext): The context object containing user-specific data, including the article content.

    Returns:
        None
    """
    user_message: str = update.message.text
    article_path: Optional[str] = context.user_data.get("article")

    if not article_path:
        await update.message.reply_text("Envie um artigo para análise.")
        return

    prompt: str = get_prompt(user_message)
    answer: str = await generate_response(update, context, prompt, article_path)

    await update.message.reply_text(answer)
