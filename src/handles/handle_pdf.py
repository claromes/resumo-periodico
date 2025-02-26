import datetime
import os
import shutil

from grobid_client.grobid_client import GrobidClient
from telegram import Document, Update
from telegram.ext import CallbackContext


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

    await update.message.reply_text(
        "Artigo processado! Envie /resumo para gerar um resumo ou faça perguntas."
    )
