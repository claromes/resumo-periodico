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

# Summary prompt
question = """Respond to the topics: Title ('Título'), Publication Date ('Data de publicação'), Authors ('Autores'), Summary in a Tweet ('Resumo em um tweet'), Overview ('Panorama'), and Key Findings ('Principais achados'). The response should be in PT-BR and based on the article."""

# Welcome message
welcome_msg = """Envie seu artigo científico, gere um resumo e tire dúvidas com o chatbot.

O chatbot usa a biblioteca de aprendizado de máquina GROBID para extrair, analisar e reestruturar a publicação técnica, e o modelo de linguagem Claude 3.5 Haiku para gerar as respostas."""

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


async def start(update: Update, context: CallbackContext):
    await update.message.reply_text(welcome_msg)


async def handle_pdf(update: Update, context: CallbackContext):
    document: Document = update.message.document

    date_now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    input_path = f"resources/input_{date_now}/"
    os.makedirs(input_path, exist_ok=True)
    pdf_path = os.path.join(input_path, document.file_name)

    file = await context.bot.get_file(document.file_id)
    await file.download_to_drive(pdf_path)
    await update.message.reply_text("⏳ GROBID: iniciando análise...")

    grobid_client.process(
        "processFulltextDocument",
        input_path,
        consolidate_citations=True,
        tei_coordinates=True,
        force=True,
        verbose=True,
    )

    xml_name = document.file_name.replace(".pdf", ".grobid.tei.xml")
    tei_file_path = os.path.join(input_path, xml_name)

    if not os.path.exists(tei_file_path):
        await update.message.reply_text(
            "Erro: O arquivo XML não foi gerado. Verifique o servidor do GROBID."
        )
        return

    with open(tei_file_path, "r") as tei_file:
        article_content = tei_file.read()

    prompt = f"Baseando-se neste artigo:\n\n{article_content}\n\n{question}"

    await update.message.reply_text("🤖 Claude 3.5 Haiku: gerando resumo...")
    response = anthropic_client.messages.create(
        max_tokens=1000,
        model="claude-3-5-haiku-20241022",
        messages=[{"role": "user", "content": prompt}],
    )

    summary_text = response.content[0].text
    summary_text_clean = re.sub(r"<\?xml.*?</TEI>", "", summary_text, flags=re.DOTALL)

    await update.message.reply_text(f"📄 Resumo gerado:\n\n{summary_text_clean}")


app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.Document.PDF, handle_pdf))

app.run_polling()
