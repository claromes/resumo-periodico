import os
from functools import wraps
from typing import Any, Awaitable, Callable, Optional

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CallbackContext,
    CommandHandler,
    MessageHandler,
    filters,
)

from generative import generate_summary
from handles import handle_pdf, handle_text
from telegram_commands import start, suporte

load_dotenv()


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


app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
app.add_handler(CommandHandler("start", access_control(start)))
app.add_handler(CommandHandler("resumo", access_control(generate_summary)))
app.add_handler(CommandHandler("suporte", access_control(suporte)))
app.add_handler(MessageHandler(filters.Document.PDF, access_control(handle_pdf)))
app.add_handler(
    MessageHandler(filters.TEXT & ~filters.COMMAND, access_control(handle_text))
)

app.run_polling()
