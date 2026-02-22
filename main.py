import logging
import os
import asyncio
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, BotCommand
from telegram.constants import ChatAction, ParseMode
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
import google.generativeai as genai

# ================= Config =================
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
DEFAULT_MODEL = 'gemini-2.0-flash'
# ===========================================

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO,
    handlers=[
        logging.FileHandler('/home/zrlgs/telegram-chatbot/bot.log'),
        logging.StreamHandler()
    ]
)

if not TELEGRAM_TOKEN or not GEMINI_API_KEY:
    raise ValueError("Please set TELEGRAM_TOKEN and GEMINI_API_KEY environment variables")

genai.configure(api_key=GEMINI_API_KEY)

user_data = {}
_model_cache = None
_model_cache_time = 0
MODEL_CACHE_TTL = 300  # 5 minutes

# ================= Model Discovery =================
def get_available_models():
    """Fetch available models from Google AI API (with caching)"""
    global _model_cache, _model_cache_time
    import time
    
    # Return cached models if still valid
    if _model_cache is not None and (time.time() - _model_cache_time) < MODEL_CACHE_TTL:
        return _model_cache
    
    models = {}
    try:
        for m in genai.list_models():
            # Only include models that support generateContent
            if 'generateContent' in m.supported_generation_methods:
                model_id = m.name.replace('models/', '')
                # Use display_name if available, otherwise use model_id
                display_name = getattr(m, 'display_name', None) or model_id
                models[model_id] = display_name
        # Update cache
        _model_cache = models
        _model_cache_time = time.time()
    except Exception as e:
        logging.error(f"Failed to fetch models: {e}")
        # Return cached models if available, otherwise fallback
        if _model_cache is not None:
            return _model_cache
        models = {
            'gemini-2.0-flash': 'Gemini 2.0 Flash',
            'gemini-1.5-pro': 'Gemini 1.5 Pro',
            'gemini-1.5-flash': 'Gemini 1.5 Flash',
        }
        _model_cache = models
        _model_cache_time = time.time()
    return models

def get_model_display_name(model_id):
    """Get display name for a model"""
    models = get_available_models()
    return models.get(model_id, model_id)
# =====================================================

# ================= Markdown Processing =================
def escape_markdown_v2(text):
    """Escape MarkdownV2 special characters"""
    special_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(special_chars)}])', r'\\\1', text)

def split_message(text, max_length=4000):
    """Split long messages"""
    if len(text) <= max_length:
        return [text]
    
    chunks = []
    while len(text) > max_length:
        split_pos = max_length
        for sep in ['\n\n', '\n', '. ', ' ', '']:
            pos = text.rfind(sep, 0, max_length)
            if pos > max_length // 2:
                split_pos = pos + len(sep)
                break
        chunks.append(text[:split_pos])
        text = text[split_pos:]
    if text:
        chunks.append(text)
    return chunks

def format_for_telegram_simple(text):
    """Simple mode: handle code blocks, rest as plain text"""
    result = []
    parts = re.split(r'(```(?:\w*)\n?.*?```)', text, flags=re.DOTALL)
    
    for part in parts:
        if part.startswith('```'):
            match = re.match(r'```(\w*)\n?(.*?)```', part, re.DOTALL)
            if match:
                code = match.group(2)
                escaped = escape_markdown_v2(code.rstrip('\n'))
                result.append(('code', f"```\n{escaped}\n```"))
        else:
            if part.strip():
                result.append(('text', escape_markdown_v2(part)))
    
    return result
# ========================================================

async def keep_typing(context, chat_id, stop_event):
    """Keep showing typing indicator"""
    while not stop_event.is_set():
        try:
            await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
            await asyncio.sleep(4)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logging.warning(f"Typing indicator error: {e}")
            break

def get_user_chat(user_id, model_name=DEFAULT_MODEL):
    if user_id not in user_data:
        model = genai.GenerativeModel(model_name)
        user_data[user_id] = {
            "chat": model.start_chat(history=[]),
            "model_name": model_name
        }
    return user_data[user_id]

# ================= Menu Setup =================
def get_main_menu():
    """Create main menu keyboard"""
    keyboard = [
        [KeyboardButton("📋 Models"), KeyboardButton("🆕 New Chat")],
        [KeyboardButton("❓ Help"), KeyboardButton("⚙️ Settings")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

async def set_bot_commands(application):
    """Set bot command list for Telegram native menu"""
    commands = [
        BotCommand("start", "Start the bot"),
        BotCommand("models", "View and switch models"),
        BotCommand("model", "Switch model by name"),
        BotCommand("new", "Clear conversation"),
        BotCommand("help", "Show help"),
    ]
    await application.bot.set_my_commands(commands)
# ===============================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = get_user_chat(user_id)
    model_display = get_model_display_name(data["model_name"])
    
    # Show menu on /start
    reply_markup = get_main_menu()
    
    await update.message.reply_text(
        "Gemini Bot Started\n\n"
        "Current model: " + model_display + "\n\n"
        "Use the menu below or type commands:",
        reply_markup=reply_markup
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logging.info(f"[HELP] User {user_id} requested help")
    help_text = """*Telegram Gemini Bot*

*Commands:*
/start - Start the bot
/models - View and switch models
/model \\<name\\> - Switch model directly
/new - Clear conversation
/help - Show this help

*Features:*
* Text conversation
* Image analysis
* Multiple models
* Independent user sessions
* Markdown formatting support"""
    help_text = escape_markdown_v2(help_text)
    # Restore escaped backslashes for Telegram
    help_text = help_text.replace('\\<', '<').replace('\\>', '>')
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN_V2)

async def models_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show available models with switch buttons"""
    user_id = update.effective_user.id
    current_model = user_data.get(user_id, {}).get("model_name", DEFAULT_MODEL)
    
    # Fetch models dynamically
    models = get_available_models()
    
    if not models:
        await update.message.reply_text("❌ Failed to fetch models. Please try again later.")
        return
    
    # Create buttons (max 8 per message for better UX)
    keyboard = []
    sorted_models = sorted(models.items(), key=lambda x: x[0])
    
    for model_id, display_name in sorted_models:
        marker = "✓ " if model_id == current_model else ""
        # Truncate display name if too long
        btn_text = f"{marker}{display_name}"[:40]
        keyboard.append([
            InlineKeyboardButton(btn_text, callback_data=f"model:{model_id}")
        ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    current_display = models.get(current_model, current_model)
    total = len(models)
    await update.message.reply_text(
        f"📋 *Available Models* \\({total} found\\)\n\nCurrent: `{current_display}`\n\nClick to switch:",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN_V2
    )

async def model_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle model switch button callback"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    data = query.data
    
    if data.startswith("model:"):
        new_model = data.split(":", 1)[1]
        try:
            genai.GenerativeModel(new_model)
            user_data[user_id] = {
                "chat": genai.GenerativeModel(new_model).start_chat(history=[]),
                "model_name": new_model
            }
            display_name = get_model_display_name(new_model)
            await query.edit_message_text(
                f"✅ Switched to: `{display_name}`\n\nMemory cleared, ready for new conversation\\!",
                parse_mode=ParseMode.MARKDOWN_V2
            )
        except Exception as e:
            await query.edit_message_text(f"❌ Switch failed: {e}")

async def switch_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Switch model via command"""
    user_id = update.effective_user.id
    if not context.args:
        await models_cmd(update, context)
        return
    
    new_model_name = context.args[0]
    try:
        genai.GenerativeModel(new_model_name)
        user_data[user_id] = {
            "chat": genai.GenerativeModel(new_model_name).start_chat(history=[]),
            "model_name": new_model_name
        }
        display_name = get_model_display_name(new_model_name)
        await update.message.reply_text(f"✅ Switched to: `{display_name}`", parse_mode=ParseMode.MARKDOWN_V2)
    except Exception as e:
        await update.message.reply_text(f"❌ Switch failed: {e}")

async def new_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    name = user_data.get(user_id, {}).get("model_name", DEFAULT_MODEL)
    user_data[user_id] = {"chat": genai.GenerativeModel(name).start_chat(history=[]), "model_name": name}
    await update.message.reply_text("🧹 Memory cleared")

async def chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    user_text = update.message.text or update.message.caption or "What's in this image?"
    logging.info(f"[CHAT] User {user_id} in chat {chat_id}: {user_text[:50]}...")
    
    data = get_user_chat(user_id)
    chat_session = data["chat"]

    stop_typing = asyncio.Event()
    typing_task = asyncio.create_task(keep_typing(context, chat_id, stop_typing))

    try:
        content = [user_text]
        if update.message.photo:
            logging.info(f"[CHAT] User {user_id} sent an image")
            photo_file = await update.message.photo[-1].get_file()
            photo_bytearray = await photo_file.download_as_bytearray()
            content.append({'mime_type': 'image/jpeg', 'data': bytes(photo_bytearray)})

        logging.info(f"[CHAT] Sending to Gemini...")
        response = await chat_session.send_message_async(content)
        reply_text = response.text
        logging.info(f"[CHAT] Gemini responded ({len(reply_text)} chars)")
        
        stop_typing.set()
        await typing_task

        formatted_parts = format_for_telegram_simple(reply_text)
        
        for part_type, part_text in formatted_parts:
            chunks = split_message(part_text)
            for chunk in chunks:
                if part_type == 'code':
                    try:
                        await update.message.reply_text(chunk, parse_mode=ParseMode.MARKDOWN_V2)
                    except Exception:
                        await update.message.reply_text(chunk.replace('\\', ''))
                else:
                    try:
                        await update.message.reply_text(chunk, parse_mode=ParseMode.MARKDOWN_V2)
                    except Exception:
                        await update.message.reply_text(chunk.replace('\\', ''))

    except Exception as e:
        stop_typing.set()
        logging.error(f"Chat error for user {user_id}: {e}")
        await update.message.reply_text(f"⚠️ Error: {e}")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    # Set bot commands menu (native Telegram /menu)
    asyncio.get_event_loop().run_until_complete(set_bot_commands(app))
    
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('help', help_cmd))
    app.add_handler(CommandHandler('model', switch_model))
    app.add_handler(CommandHandler('models', models_cmd))
    app.add_handler(CommandHandler('new', new_chat))
    app.add_handler(CallbackQueryHandler(model_callback, pattern=r'^model:'))
    
    # Handle menu button clicks
    async def handle_menu_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text
        if text == "📋 Models":
            await models_cmd(update, context)
        elif text == "🆕 New Chat":
            await new_chat(update, context)
        elif text == "❓ Help":
            await help_cmd(update, context)
        elif text == "⚙️ Settings":
            await update.message.reply_text("⚙️ Settings: Use /model <name> to switch models", parse_mode=ParseMode.MARKDOWN_V2)
        else:
            # Not a menu button, treat as normal message
            await chat_handler(update, context)
    
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_menu_buttons))
    app.add_handler(MessageHandler(filters.PHOTO & (~filters.COMMAND), chat_handler))
    
    logging.info("Bot starting...")
    app.run_polling()
