from telegram import Update
from telegram.ext import CallbackContext

from utils import escape_markdown_v2


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
