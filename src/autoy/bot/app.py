from __future__ import annotations

import asyncio
import logging
import threading

from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from autoy.bot.commands import COMMANDS, CommandRouter
from autoy.bot.core import BotService
from autoy.bot.loop import ScheduleLoop
from autoy.pipeline import AppContext
from autoy.storage import BotStore

log = logging.getLogger(__name__)


def build_application(ctx: AppContext) -> Application:
    settings = ctx.settings
    if not settings.telegram_bot_token:
        raise SystemExit("TELEGRAM_BOT_TOKEN is not set")

    service = BotService(ctx, BotStore(settings.paths.bot_db))
    router = CommandRouter(service)
    loop = ScheduleLoop(service)

    async def on_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_chat and update.message and update.message.text:
            router.dispatch(update.effective_chat.id, update.message.text)

    async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if not query or not query.message:
            return
        chat_id, message_id = int(query.message.chat_id), int(query.message.message_id)
        if not service.is_authorized(chat_id):
            await query.answer("Access denied.")
            return
        await query.answer("Accepted")
        action, _, token = (query.data or "").partition(":")
        handler = {
            "approve": service.handle_approve,
            "remake": service.handle_remake,
            "delete": service.handle_delete,
        }.get(action)
        if handler:
            threading.Thread(target=handler, args=(token, chat_id, message_id), daemon=True).start()

    async def on_startup(app: Application) -> None:
        service.loop = asyncio.get_running_loop()
        loop.start()
        if settings.telegram_chat_id:
            await app.bot.send_message(chat_id=settings.telegram_chat_id, text="AUTOY bot started.\n/help")

    app = Application.builder().token(settings.telegram_bot_token).post_init(on_startup).build()
    app.add_handler(CommandHandler(list(COMMANDS), on_command))
    app.add_handler(CallbackQueryHandler(on_callback))
    service.app = app
    return app


def run_bot(ctx: AppContext) -> None:
    app = build_application(ctx)
    log.info("Telegram polling started")
    app.run_polling(allowed_updates=["message", "callback_query"])
