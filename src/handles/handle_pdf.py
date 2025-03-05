import datetime
import json
import os

import xmltodict
from grobid_client.grobid_client import GrobidClient
from telegram import Document, Update
from telegram.ext import CallbackContext


def tei_to_json(tei_file_path: str, json_file_path: str) -> str:
    """Converts a TEI-XML file to JSON and saves the result to a file.

    Args:
        tei_file_path (str): Path to the input TEI-XML file.
        json_file_path (str): Path where the JSON file will be saved.

    Returns:
        str: Path to the generated JSON file.
    """
    with open(tei_file_path, "r", encoding="utf-8") as tei_file:
        tei_content: str = tei_file.read()

    tei_dict: dict = xmltodict.parse(tei_content)

    with open(json_file_path, "w", encoding="utf-8") as json_file:
        json.dump(tei_dict, json_file, indent=4, ensure_ascii=False)

    return json_file_path


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

    try:
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
    except Exception as e:
        await update.message.reply_text(f"Verifique o servidor do GROBID.\nErro: {e}")
        return str(e)

    await update.message.chat.send_action(action="typing")

    xml_name: str = document.file_name.replace(".pdf", ".grobid.tei.xml")
    tei_file_path: str = os.path.join(input_path, xml_name)

    if not os.path.exists(tei_file_path):
        await update.message.reply_text(
            "Erro: O arquivo XML não foi gerado. Verifique o servidor do GROBID."
        )
        return

    json_name: str = document.file_name.replace(".pdf", ".json")
    json_file_path: str = os.path.join(input_path, json_name)
    article_path: str = tei_to_json(tei_file_path, json_file_path)

    context.user_data["article"] = article_path

    await update.message.reply_text(
        "Artigo processado! Envie /resumo para gerar um resumo ou faça perguntas."
    )
