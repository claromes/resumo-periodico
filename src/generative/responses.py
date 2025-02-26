import os
import re
from typing import Optional

import openai
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import CallbackContext

from utils import escape_markdown_v2

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


async def generate_response(
    update: Update, context: CallbackContext, prompt: str, article_path: str
) -> str:
    """
    Generates a response using the GPT-4o mini model based on the provided prompt.

    Args:
        update (Update): The update object representing the incoming message and its context.
        context (CallbackContext): The context object containing user-specific data, including the article content.
        prompt (str): The prompt to be sent to the GPT model to generate a response.
        article_path (str): The content extracted from the article.

    Returns:
        str: The text content of the generated response.
    """
    await update.message.reply_text("⏳ GPT-4o mini: gerando resposta... (≤1 min)")

    openai_client = openai.Client(api_key=OPENAI_API_KEY)

    try:
        openai_file = openai_client.files.create(
            file=open(article_path, "rb"), purpose="assistants"
        )

        openai_assistant = openai_client.beta.assistants.create(
            model="gpt-4o-mini",
            name="TEI/XML Scientific Article Assistant",
            instructions="You are an assistant specialized in scientific articles in TEI/XML format. Use the content of the uploaded files to answer the user's questions.",
            tools=[{"type": "file_search"}],
        )

        openai_thread = openai_client.beta.threads.create()

        openai_client.beta.threads.messages.create(
            thread_id=openai_thread.id,
            role="user",
            content=prompt,
            attachments=[
                {"file_id": openai_file.id, "tools": [{"type": "file_search"}]}
            ],
        )

        openai_client.beta.threads.runs.create_and_poll(
            thread_id=openai_thread.id,
            assistant_id=openai_assistant.id,
        )

        messages = openai_client.beta.threads.messages.list(thread_id=openai_thread.id)

        value = messages.data[0].content[0].text.value

        response = re.sub(r"【[^】]+】", "", value)
        response = re.sub(r"\n\s*\n", "\n\n", response).strip()

        return response

    except Exception as e:
        await update.message.reply_text(f"GPT-4o mini: {e}")
        return str(e)


async def generate_summary(update: Update, context: CallbackContext) -> None:
    """
    Generates a summary of an article based on predefined topics and sends it to the user.

    Args:
        update (Update): The update object representing the incoming message and its context.
        context (CallbackContext): The context object containing user-specific data, including the article content.

    Returns:
        None
    """
    article_path: Optional[str] = context.user_data.get("article")
    question: str = (
        """Pergunta baseada no artigo em anexo, estruturado em XML:\n\nResponda aos seguintes tópicos: no bloco <teiHeader>: "Título" (bloco <titleStmt>), "Data de publicação", "Autores" e "Publisher"; no bloco <body>: "Resumo em um tweet", "Panorama" e "Principais achados"; no bloco listBibl, considerar cada bloco biblStruct como 1 referência: "Total estimado de referências". A resposta deve estar em português (PT-BR), porém, ao referenciar trechos de textos, mantenha o idioma original. Não indicar o bloco, somente o tópico, na resposta e em plain text."""
    )

    if not article_path:
        await update.message.reply_text(
            "Nenhum artigo foi enviado ainda. Envie um PDF para análise."
        )
        return

    summary_text: str = await generate_response(update, context, question, article_path)

    context.user_data["summary"] = summary_text

    await update.message.reply_text(
        f"Resumo:\n\n{escape_markdown_v2(summary_text)}", parse_mode="MarkdownV2"
    )
    await update.message.reply_text("Se preferir, pergunte algo sobre o artigo.")
