# flake8: noqa: E501

import datetime
import os
import re
import shutil
from functools import wraps
from typing import Any, Awaitable, Callable, Optional

import openai
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

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
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


def escape_markdown_v2(text: str) -> str:
    """Escapes special characters for Telegram's MarkdownV2 format.

    Args:
        text (str): The input text to be escaped.

    Returns:
        str: The escaped text.
    """
    special_chars = r"_*[]()~`>#+-=|{}.!"
    return re.sub(r"([" + re.escape(special_chars) + r"])", r"\\\1", text)


def get_prompt(question: str) -> str:
    """
    Generates a formatted prompt for an objective response based on a question and article content.

    Args:
        question (str): The question asked by the user.

    Returns:
        str: The formatted string containing the question and article content.
    """
    return f"Pergunta baseada no artigo em anexo, estruturado em XML:\n\n'{question}'\n\nResponda de forma objetiva e em português (PT-BR), porém, ao referenciar trechos de textos, mantenha o idioma original."


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
        escape_markdown_v2(
            """Ferramenta experimental para gerar resumos de artigos científicos diretamente de arquivos PDF. Foi desenvolvida para auxiliar no processo de curadoria da newsletter Periódica.

O modelo de linguagem GPT-4o mini é utilizado em conjunto com a biblioteca de aprendizado de máquina GROBID, responsável pela extração de informações acadêmicas dos artigos.

Comandos:
/resumo: gerar resumo do artigo em PDF
/suporte: obter ajuda
/start: iniciar uma nova conversa

Reporte um erro:
abra uma issue no [GitHub](https://github.com/periodicanews/resumo-periodico/issues) ou envie um e-mail para support@claromes.com.

Créditos:
author: Clarissa Mendes <support@claromes.com>
version: 0.0.2-alpha
license:
source code: [github.com/periodicanews/resumo-periodico](https://github.com/periodicanews/resumo-periodico)
"""
        ),
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
        grobid_server="http://localhost:8070",
        coordinates=[
            "ref",
            "biblStruct",
            "persName",
            "figure",
            "formula",
            "head",
            "s",
            "p",
            "note",
            "title",
            "affiliation",
        ],
        sleep_time=5,
        timeout=60,
    )

    grobid_client.process(
        "processFulltextDocument",
        input_path,
        consolidate_header=True,
        consolidate_citations=True,
        include_raw_citations=True,
        include_raw_affiliations=True,
        tei_coordinates=False,
        segment_sentences=True,
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

    txt_file_path = tei_file_path.replace(".xml", ".txt")
    shutil.copy(tei_file_path, txt_file_path)

    context.user_data["article"] = txt_file_path

    print(context.user_data["article"])

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
    article_path: Optional[str] = context.user_data.get("article")

    if not article_path:
        await update.message.reply_text("Envie um artigo para análise.")
        return

    prompt: str = get_prompt(user_message)
    answer: str = await generate_response(update, context, prompt, article_path)

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
