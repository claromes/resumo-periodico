import anthropic
import os
from dotenv import load_dotenv
from grobid_client.grobid_client import GrobidClient
import datetime
import re
from telegram import Update, Document
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackContext,
)

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

anthropic_client = anthropic.Client(api_key=ANTHROPIC_API_KEY)

grobid_client = GrobidClient(
    grobid_server="http://localhost:8070",
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


def get_prompt(question, article_content):
    return f"O usuário fez a seguinte pergunta baseada no artigo:\n\n'{question}'\n\nTexto extraído do artigo:\n\n{article_content}\n\nResponda de forma objetiva, em português (PT-BR) e limite-se a 850 tokens."


async def generate_response(update: Update, prompt):
    await update.message.reply_text("⏳ Claude 3.5 Haiku: gerando resposta...")

    try:
        response = anthropic_client.messages.create(
            max_tokens=850,
            model="claude-3-5-haiku-20241022",
            messages=[{"role": "user", "content": prompt}],
        )

        await update.message.chat.send_action(action="typing")

        return response.content[0].text
    except Exception as e:
        await update.message.reply_text(f"Claude 3.5 Haiku: {e}")


async def generate_summary(update: Update, context: CallbackContext):
    article_content = context.user_data.get("article")
    question = """Responda aos seguintes tópicos: Título ('Título'), Data de publicação ('Data de publicação'), Autores ('Autores'), Resumo em um tweet ('Resumo em um tweet'), Panorama ('Panorama') e Principais achados ('Principais achados'). A resposta deve estar em português (PT-BR), baseada no artigo e com um máximo de 850 tokens."""

    if not article_content:
        await update.message.reply_text(
            "Nenhum artigo foi enviado ainda. Envie um PDF para análise."
        )
        return

    prompt = get_prompt(question, article_content)

    summary_text = await generate_response(update, prompt)
    summary_text_clean = re.sub(r"<\?xml.*?</TEI>", "", summary_text, flags=re.DOTALL)

    context.user_data["summary"] = summary_text_clean

    await update.message.reply_text(f"Resumo:\n\n{summary_text_clean}")
    await update.message.reply_text("Se preferir, pergunte algo sobre o artigo.")


async def suporte(update: Update, context: CallbackContext):
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


async def start(update: Update, context: CallbackContext):
    await update.message.reply_text(
        """Envie seu artigo científico, aguarde a análise e faça suas perguntas.

Digite /suporte para obter ajuda."""
    )


async def handle_pdf(update: Update, context: CallbackContext):
    document: Document = update.message.document

    date_now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    input_path = f"resources/input_{date_now}/"
    os.makedirs(input_path, exist_ok=True)
    pdf_path = os.path.join(input_path, document.file_name)

    file = await context.bot.get_file(document.file_id)
    await file.download_to_drive(pdf_path)

    await update.message.reply_text("⏳ GROBID: processando...")

    grobid_client.process(
        "processFulltextDocument",
        input_path,
        consolidate_citations=True,
        tei_coordinates=True,
        force=True,
        verbose=True,
    )

    await update.message.chat.send_action(action="typing")

    xml_name = document.file_name.replace(".pdf", ".grobid.tei.xml")
    tei_file_path = os.path.join(input_path, xml_name)

    if not os.path.exists(tei_file_path):
        await update.message.reply_text(
            "Erro: O arquivo XML não foi gerado. Verifique o servidor do GROBID."
        )
        return

    with open(tei_file_path, "r") as tei_file:
        article_content = tei_file.read()

    context.user_data["article"] = article_content

    await update.message.reply_text(
        "Artigo processado! Envie /resumo para gerar um resumo ou faça perguntas."
    )


async def generate_summary(update: Update, context: CallbackContext):
    article_content = context.user_data.get("article")
    question = """Responda aos seguintes tópicos: Título ('Título'), Data de publicação ('Data de publicação'), Autores ('Autores'), Resumo em um tweet ('Resumo em um tweet'), Panorama ('Panorama') e Principais achados ('Principais achados'). A resposta deve estar em português (PT-BR), baseada no artigo e com um máximo de 850 tokens."""

    if not article_content:
        await update.message.reply_text(
            "Nenhum artigo foi enviado ainda. Envie um PDF para análise."
        )
        return

    prompt = get_prompt(question, article_content)

    summary_text = await generate_response(update, prompt)
    summary_text_clean = re.sub(r"<\?xml.*?</TEI>", "", summary_text, flags=re.DOTALL)

    context.user_data["summary"] = summary_text_clean

    await update.message.reply_text(f"Resumo:\n\n{summary_text_clean}")
    await update.message.reply_text("Se preferir, pergunte algo sobre o artigo.")


async def handle_text(update: Update, context: CallbackContext):
    user_message = update.message.text
    article_content = context.user_data.get("article")

    if not article_content:
        await update.message.reply_text("Envie um artigo para análise.")
        return

    prompt = get_prompt(user_message, article_content)
    answer = await generate_response(update, prompt)

    await update.message.reply_text(answer)


app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("resumo", generate_summary))
app.add_handler(CommandHandler("suporte", suporte))
app.add_handler(MessageHandler(filters.Document.PDF, handle_pdf))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

app.run_polling()
