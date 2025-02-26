# flake8: noqa: E501

import datetime
import os
from functools import wraps
from typing import Any, Awaitable, Callable, Optional

import anthropic
from dotenv import load_dotenv
from grobid_client.grobid_client import GrobidClient
from telegram import Document, Update
from telegram.ext import (
    Application,
    CallbackContext,
    CommandHandler,
    MessageHandler,
    filters,
)

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_USERS = os.getenv("ALLOWED_USERS")


def access_control(
    func: Callable[..., Awaitable[Any]],
) -> Callable[..., Awaitable[Any]]:
    """
    Decorator function that restricts access to certain users.

    Args:
        func (function): The function to be wrapped and restricted.

    Returns:
        function: The wrapped function that enforces access control.
    """

    @wraps(func)
    async def wrapped(
        update: Update, context: CallbackContext, *args: Any, **kwargs: Any
    ) -> Any:
        user_id: Optional[str] = update.message.from_user.username
        if user_id not in ALLOWED_USERS:
            await update.message.reply_text(
                "Acesso negado. Você não tem permissão para usar este bot."
            )
            return
        return await func(update, context, *args, **kwargs)

    return wrapped


def get_prompt(question: str) -> str:
    """
    Generates a formatted prompt for an objective response based on a question and article content.

    Args:
        question (str): The question asked by the user.

    Returns:
        str: The formatted string containing the question and article content.
    """
    return f"Pergunta baseada no XML (artigo científico estruturado em XML/TEI) em anexo:\n\n'{question}'\n\nResponda de forma objetiva e em português (PT-BR)."


async def generate_response(
    update: Update, context: CallbackContext, prompt: str, article: str
) -> str:
    """
    Generates a response using the Claude 3.5 Haiku model based on the provided prompt.

    Args:
        update (Update): The update object representing the incoming message and its context.
        context (CallbackContext): The context object containing user-specific data, including the article content.
        prompt (str): The prompt to be sent to the Claude model to generate a response.
        article (str): The content extracted from the article.

    Returns:
        str: The text content of the generated response.
    """
    await update.message.reply_text("⏳ Claude 3.5 Haiku: gerando resposta... (≤1 min)")

    anthropic_client = anthropic.Client(api_key=ANTHROPIC_API_KEY)

    try:
        response = anthropic_client.messages.create(
            max_tokens=1024,
            model="claude-3-5-haiku-20241022",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "document",
                            "source": {
                                "type": "text",
                                "media_type": "text/plain",
                                "data": article,
                            },
                        },
                    ],
                }
            ],
        )

        await update.message.chat.send_action(action="typing")

        return response.content[0].text
    except Exception as e:
        await update.message.reply_text(f"Claude 3.5 Haiku: {e}")
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
    article_content: Optional[str] = context.user_data.get("article")
    question: str = (
        """Pergunta baseada no XML (artigo científico estruturado em XML/TEI) em anexo:\n\nResponda aos seguintes tópicos: Título, Data de publicação, Autores, Resumo em um tweet, Panorama e Principais achados. A resposta deve estar em português (PT-BR)."""
    )

    if not article_content:
        await update.message.reply_text(
            "Nenhum artigo foi enviado ainda. Envie um PDF para análise."
        )
        return

    prompt: str = get_prompt(question)

    summary_text: str = await generate_response(
        update, context, prompt, article_content
    )

    context.user_data["summary"] = summary_text

    await update.message.reply_text(f"Resumo:\n\n{summary_text}")
    await update.message.reply_text("Se preferir, pergunte algo sobre o artigo.")


async def suporte(update: Update, context: CallbackContext) -> None:
    """
    Sends a help message providing information about the article summarization tool and its usage.

    Args:
        update (Update): The update object representing the incoming message and its context.
        context (CallbackContext): The context object containing user-specific data, which is not used in this function.

    Returns:
        None
    """
    await update.message.reply_text(
        """Ferramenta experimental para gerar resumos de artigos científicos diretamente de arquivos PDF\. Foi desenvolvida para auxiliar no processo de curadoria da newsletter Periódica\.

O modelo de linguagem Claude 3\.5 Haiku é utilizado em conjunto com a biblioteca de aprendizado de máquina GROBID, responsável pela extração de informações acadêmicas dos artigos\.

Comandos:
/resumo: gerar resumo do artigo em PDF
/suporte: obter ajuda
/start: iniciar uma nova conversa

Reporte um erro:
abra uma issue no [GitHub](https://github\.com/periodicanews/resumo\-periodico/issues) ou envie um e\-mail para support@claromes\.com\.

Créditos:
author: Clarissa Mendes \<support@claromes\.com\>
version: 0\.0\.2\-alpha
license:
source code: [github\.com/periodicanews/resumo\-periodico](https://github\.com/periodicanews/resumo\-periodico)
""",
        parse_mode="MarkdownV2",
    )


async def start(update: Update, context: CallbackContext) -> None:
    """
    Sends a welcome message to the user with instructions to send an article and ask questions.

    Args:
        update (Update): The update object representing the incoming message and its context.
        context (CallbackContext): The context object containing user-specific data, which is not used in this function.

    Returns:
        None
    """
    await update.message.reply_text(
        """Envie seu artigo científico, aguarde a análise e faça suas perguntas.

Digite /suporte para obter ajuda."""
    )


async def handle_pdf(update: Update, context: CallbackContext) -> None:
    """
    Processes a PDF document sent by the user and extracts its content using the GROBID service.

    Args:
        update (Update): The update object representing the incoming message and its context.
        context (CallbackContext): The context object containing user-specific data, including the article content.

    Returns:
        None
    """
    document: Document = update.message.document

    date_now: str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    input_path: str = f"resources/input_{date_now}/"
    os.makedirs(input_path, exist_ok=True)
    pdf_path: str = os.path.join(input_path, document.file_name)

    file = await context.bot.get_file(document.file_id)
    await file.download_to_drive(pdf_path)

    await update.message.reply_text("⏳ GROBID: processando... (≤1 min)")

    grobid_client = GrobidClient(
        grobid_server="http://grobid:8070",
        batch_size=100,
        coordinates=[
            "persName",
            "figure",
            "ref",
            "biblStruct",
            "formula",
            "s",
            "note",
            "title",
        ],
        sleep_time=5,
        timeout=60,
    )

    grobid_client.process(
        "processFulltextDocument",
        input_path,
        consolidate_citations=True,
        tei_coordinates=True,
        force=True,
        verbose=True,
    )

    await update.message.chat.send_action(action="typing")

    xml_name: str = document.file_name.replace(".pdf", ".grobid.tei.xml")
    tei_file_path: str = os.path.join(input_path, xml_name)

    if not os.path.exists(tei_file_path):
        await update.message.reply_text(
            "Erro: O arquivo XML não foi gerado. Verifique o servidor do GROBID."
        )
        return

    with open(tei_file_path, "r") as tei_file:
        article_content: str = tei_file.read()

    context.user_data["article"] = article_content

    await update.message.reply_text(
        "Artigo processado! Envie /resumo para gerar um resumo ou faça perguntas."
    )


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
    article_content: Optional[str] = context.user_data.get("article")

    if not article_content:
        await update.message.reply_text("Envie um artigo para análise.")
        return

    prompt: str = get_prompt(user_message)
    answer: str = await generate_response(update, context, prompt, article_content)

    await update.message.reply_text(answer)


app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
app.add_handler(CommandHandler("start", access_control(start)))
app.add_handler(CommandHandler("resumo", access_control(generate_summary)))
app.add_handler(CommandHandler("suporte", access_control(suporte)))
app.add_handler(MessageHandler(filters.Document.PDF, access_control(handle_pdf)))
app.add_handler(
    MessageHandler(filters.TEXT & ~filters.COMMAND, access_control(handle_text))
)

app.run_polling()
