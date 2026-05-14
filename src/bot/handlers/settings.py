from telegram import Update
from telegram.ext import ContextTypes
from src.bot.handlers import get_user_service


async def settings_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_svc = get_user_service()
    user = user_svc.get_by_telegram_id(update.effective_user.id)
    if not user:
        await update.message.reply_text("Use /start to set up your account first.")
        return

    strategies = ", ".join(user.strategies) if user.strategies else "All"
    await update.message.reply_text(
        f"*Your Settings*\n\n"
        f"Language: {user.lang}\n"
        f"Scan Mode: {user.scan_mode}\n"
        f"Strategies: {strategies}\n\n"
        f"/lang EN|ZH — change language\n"
        f"/mode US — scan mode (crypto paused)",
        parse_mode="Markdown",
    )


async def lang_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_svc = get_user_service()
    user = user_svc.get_by_telegram_id(update.effective_user.id)
    if not user:
        return

    if not context.args or context.args[0].upper() not in ("EN", "ZH"):
        await update.message.reply_text("Usage: /lang EN or /lang ZH")
        return

    lang = context.args[0].upper()
    user_svc.update_preferences(user.id, lang=lang)
    await update.message.reply_text(f"Language set to {lang}.")


async def mode_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_svc = get_user_service()
    user = user_svc.get_by_telegram_id(update.effective_user.id)
    if not user:
        return

    if not context.args or context.args[0].upper() not in ("US", "CRYPTO", "ALL"):
        await update.message.reply_text("Usage: /mode US  (crypto scanning is currently paused)")
        return

    requested = context.args[0].upper()
    if requested != "US":
        user_svc.update_preferences(user.id, scan_mode="US")
        await update.message.reply_text(
            f"Crypto scanning is currently paused. Scan mode set to US."
        )
        return

    user_svc.update_preferences(user.id, scan_mode="US")
    await update.message.reply_text("Scan mode set to US.")


ALL_STRATEGIES = ["TRINITY", "PANIC", "2B"]


async def strategies_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_svc = get_user_service()
    user = user_svc.get_by_telegram_id(update.effective_user.id)
    if not user:
        await update.message.reply_text("Use /start to set up your account first.")
        return

    if not context.args:
        current = user.strategies or ALL_STRATEGIES
        lines = [f"  {'✅' if s in current else '❌'} {s}" for s in ALL_STRATEGIES]
        await update.message.reply_text(
            f"*Active Strategies*\n\n" + "\n".join(lines) +
            "\n\nToggle: /strategies TRINITY (toggles on/off)",
            parse_mode="Markdown",
        )
        return

    toggle = context.args[0].upper()
    if toggle not in ALL_STRATEGIES:
        await update.message.reply_text(f"Unknown strategy. Choose from: {', '.join(ALL_STRATEGIES)}")
        return

    current = list(user.strategies or ALL_STRATEGIES)
    if toggle in current:
        current.remove(toggle)
        if not current:
            await update.message.reply_text("You need at least one strategy active.")
            return
        action = "disabled"
    else:
        current.append(toggle)
        action = "enabled"

    user_svc.update_preferences(user.id, strategies=current)
    await update.message.reply_text(f"{toggle} {action}. Active: {', '.join(current)}")
