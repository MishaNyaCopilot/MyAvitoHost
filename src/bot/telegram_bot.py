"""
Telegram Bot Module for Avito Rental Assistant

This module implements the Telegram bot interface for landlords to manage their
apartment rentals on Avito. It provides commands for closing/opening booking dates,
viewing calendars, and receiving notifications about bookings and guest interactions.

The bot uses conversation handlers to guide users through multi-step processes
like selecting ads and entering date ranges.
"""

import datetime
import logging
import os

from dateutil.relativedelta import relativedelta
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from src.api.avito_api_client import AvitoApiClient
from src.api.avito_auth import AvitoAuth
from src.constants import DEFAULT_USER_TELEGRAM_IDS
from src.database.database import SessionLocal, get_all_ad_descriptions
from src.database.models import AdDescriptionsModel

# Load environment variables
AVITO_BOT_TOKEN = os.getenv("AVITO_TG_BOT_TOKEN")
USER_TELEGRAM_IDS = DEFAULT_USER_TELEGRAM_IDS

# Basic logging setup
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

if not AVITO_BOT_TOKEN:
    logger.error("AVITO_BOT_TOKEN not found in environment variables. Bot cannot start.")
    exit()

if not USER_TELEGRAM_IDS:
    logger.error("USER_TELEGRAM_IDS is empty. Notifications will fail.")
    exit()


async def send_message(bot: Bot, chat_id: int, text: str):
    """Sends a message to a specific chat ID."""
    try:
        await bot.send_message(chat_id=chat_id, text=text)
        logger.info(f"Message sent to chat ID {chat_id}.")
    except TelegramError as e:
        logger.error(f"Error sending message to chat ID {chat_id}: {e}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message when the /start command is issued."""
    await update.message.reply_text(
        "Добро пожаловать! Я ваш АвитоХост Про ассистент. Используйте /help, чтобы увидеть доступные команды."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a help message listing available commands when the /help command is issued."""
    help_text = """Доступные команды:
/start - Запуск бота
/help - Показать это сообщение
/close_dates [ID объявления] - Закрыть даты для бронирования. Если ID не указан, будет предложен выбор.
/open_dates [ID объявления] - Открыть даты для бронирования. Если ID не указан, будет предложен выбор.
/calendar - Просмотр календаря бронирований для объявления.
/testnotify - Отправить тестовые уведомления (для разработчика)"""
    await update.message.reply_text(help_text)


# --- States for ConversationHandler ---
SELECTING_AD_CLOSE, GETTING_DATES_CLOSE = range(2)
SELECTING_AD_OPEN, GETTING_DATES_OPEN = range(2, 4)
SELECTING_AD_CALENDAR, GETTING_PERIOD_CALENDAR = range(4, 6)  # New states
# Generic cancel state if needed, though ConversationHandler.END is usually sufficient
CANCEL_CONVERSATION = ConversationHandler.END


# --- Helper Functions ---
def _parse_date_range_input(text: str) -> tuple[str | None, str | None, str | None]:
    """
    Parses user date range input and validates format.

    Accepts dates in DD-MM-YYYY or DD.MM.YYYY format and converts them
    to YYYY-MM-DD format required by the Avito API.

    Args:
        text: User input string containing two dates separated by space

    Returns:
        Tuple of (start_date, end_date, error_message) where dates are in
        YYYY-MM-DD format or None if invalid, and error_message is None
        if successful or contains user-friendly error text
    """
    # Normalize dots to dashes for consistent parsing
    parts = text.replace(".", "-").split()
    if len(parts) != 2:
        return (
            None,
            None,
            "Пожалуйста, введите две даты (начало и конец) в формате ДД-ММ-ГГГГ ДД-ММ-ГГГГ.",
        )

    try:
        date_from_user = parts[0]
        date_to_user = parts[1]
        # Validate and reformat dates to YYYY-MM-DD for API
        date_from_api = datetime.datetime.strptime(date_from_user, "%d-%m-%Y").strftime("%Y-%m-%d")
        date_to_api = datetime.datetime.strptime(date_to_user, "%d-%m-%Y").strftime("%Y-%m-%d")

        # Basic validation: date_from should not be after date_to
        if datetime.datetime.strptime(date_from_api, "%Y-%m-%d") > datetime.datetime.strptime(
            date_to_api, "%Y-%m-%d"
        ):
            return None, None, "Дата начала не может быть позже даты окончания."

        return date_from_api, date_to_api, None
    except ValueError:
        return None, None, "Неверный формат даты. Используйте ДД-ММ-ГГГГ."


async def _get_user_ads_keyboard(
    context: ContextTypes.DEFAULT_TYPE, action_prefix: str
) -> InlineKeyboardMarkup | None:
    """
    Creates an inline keyboard with user's ads for selection.

    Fetches all ads from the database and creates a keyboard where each button
    represents one ad. The button text shows the ad's address, title, or ID.

    Args:
        context: Telegram context containing bot_data with db_session_local
        action_prefix: Prefix for callback data (e.g., "closedates_ad", "opendates_ad")

    Returns:
        InlineKeyboardMarkup with ad selection buttons and a cancel button,
        or None if no ads found or database error occurs
    """
    db_session_local = context.application.bot_data.get("db_session_local")
    if not db_session_local:
        logger.error("db_session_local not found in bot_data.")
        return None

    ads_from_db: list[AdDescriptionsModel] = []
    try:
        with db_session_local() as db:
            ads_from_db = get_all_ad_descriptions(db)
    except Exception as e:
        logger.error(f"Error fetching ads from database: {e}", exc_info=True)
        return None

    if not ads_from_db:
        logger.info("No ads found in the database for keyboard construction.")
        return None

    keyboard = []
    for ad in ads_from_db:
        # Determine button text: prefer address, then title, then ID
        if ad.address:
            button_text = ad.address
        elif ad.title:
            button_text = ad.title
        else:
            button_text = f"Ad ID {ad.ad_id_avito}"

        # Skip ads without a valid Avito ID
        if ad.ad_id_avito is None:
            logger.warning(f"Ad found with None ad_id_avito (DB ID: {ad.id}). Skipping.")
            continue

        # Create button with callback data format: "{action_prefix}_{ad_id}"
        keyboard.append(
            [InlineKeyboardButton(button_text, callback_data=f"{action_prefix}_{ad.ad_id_avito}")]
        )

    # Add cancel button if we have at least one valid ad
    if keyboard:
        keyboard.append([InlineKeyboardButton("Отмена", callback_data="cancel_ad_selection")])

    # Final check: if keyboard is still empty (all ads were invalid), return None
    if not keyboard:
        logger.info(
            "Keyboard is empty after processing ads (e.g., all ads had None Avito ID or no ads found)."
        )
        return None
    return InlineKeyboardMarkup(keyboard)


# --- Core Logic for Date Management ---
async def _manage_dates_on_ad(
    api_client: AvitoApiClient,
    item_id: int,
    date_from_api: str,
    date_to_api: str,
    action: str,  # "close" or "open"
    context: ContextTypes.DEFAULT_TYPE,
) -> bool:
    """
    Manages closing or opening dates for an ad via Avito API.

    Args:
        api_client: Initialized AvitoApiClient instance
        item_id: Avito item (ad) ID
        date_from_api: Start date in YYYY-MM-DD format
        date_to_api: End date in YYYY-MM-DD format
        action: Either "close" (block dates) or "open" (unblock dates)
        context: Telegram context for sending error messages

    Returns:
        True if operation succeeded, False if an error occurred

    Note:
        For "close" action, creates a manual booking to block dates.
        For "open" action, updates availability intervals to mark dates as available.
    """
    try:
        if action == "close":
            # Create a manual booking to block the dates
            payload = {
                "bookings": [
                    {
                        "date_start": date_from_api,
                        "date_end": date_to_api,
                        "type": "manual",
                        "comment": "Закрыто через Telegram-бот",
                    }
                ],
                "source": "telegram_bot_conversation",
            }
            api_client.update_item_bookings(
                item_id=item_id, bookings_payload=payload
            )  # Removed await, changed to sync
        elif action == "open":
            # Update availability intervals to mark dates as open
            payload = {
                "intervals": [
                    {
                        "date_start": date_from_api,
                        "date_end": date_to_api,
                        "open": 1,  # 1 for open/available
                    }
                ],
                "source": "telegram_bot_conversation",
            }
            api_client.update_item_availability(
                item_id=item_id, availability_payload=payload
            )  # Removed await, changed to sync
        else:
            raise ValueError("Invalid action specified for _manage_dates_on_ad")

        return True
    except Exception as e:
        logger.error(f"Error during {action} dates for item {item_id}: {e}", exc_info=True)
        await context.bot.send_message(
            chat_id=context.user_data["chat_id"],
            text=f"Произошла ошибка при попытке {action} даты для объявления {item_id}: {e}",
        )
        return False


# --- Conversation Entry Points (/close_dates, /open_dates) ---
async def close_dates_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the conversation to close dates. Handles optional ad_id argument."""
    logger.info(f"/close_dates command initiated by user {update.effective_user.id}")
    if context.user_data:  # Check if user_data has any content
        logger.info(
            f"Clearing previous user_data for user {update.effective_user.id} due to command restart."
        )
        context.user_data.clear()
    context.user_data["chat_id"] = update.effective_chat.id
    # api_client is no longer passed to _get_user_ads_keyboard

    if context.args and len(context.args) >= 1:
        try:
            ad_id = int(context.args[0])
            context.user_data["selected_ad_id"] = ad_id
            logger.info(f"Ad ID {ad_id} provided as argument for /close_dates.")
            cancel_button = InlineKeyboardButton("Отмена", callback_data="cancel_date_input")
            keyboard = InlineKeyboardMarkup([[cancel_button]])
            await update.message.reply_text(
                f"Вы выбрали объявление ID: {ad_id}.\n"
                "Теперь введите даты для закрытия в формате: <code>ДД-ММ-ГГГГ ДД-ММ-ГГГГ</code> (например, 25-12-2023 28-12-2023).",
                parse_mode="HTML",
                reply_markup=keyboard,
            )
            return GETTING_DATES_CLOSE
        except ValueError:
            await update.message.reply_text(
                "Неверный ID объявления. Пожалуйста, введите числовой ID."
            )
            return ConversationHandler.END  # Or ask again, or show list
    else:
        logger.info("No ad ID provided for /close_dates, attempting to show ad list.")
        # Pass context and action_prefix. api_client is no longer needed.
        keyboard = await _get_user_ads_keyboard(context, action_prefix="closedates_ad")
        if keyboard:
            await update.message.reply_text(
                "Выберите объявление для закрытия дат:", reply_markup=keyboard
            )
            return SELECTING_AD_CLOSE
        else:
            await update.message.reply_text(
                "Не удалось получить список ваших объявлений. Попробуйте указать ID объявления напрямую: "
                "/close_dates <ID объявления>"
            )
            return ConversationHandler.END


async def open_dates_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the conversation to open dates. Handles optional ad_id argument."""
    logger.info(f"/open_dates command initiated by user {update.effective_user.id}")
    if context.user_data:  # Check if user_data has any content
        logger.info(
            f"Clearing previous user_data for user {update.effective_user.id} due to command restart."
        )
        context.user_data.clear()
    context.user_data["chat_id"] = update.effective_chat.id
    # api_client is no longer passed to _get_user_ads_keyboard

    if context.args and len(context.args) >= 1:
        try:
            ad_id = int(context.args[0])
            context.user_data["selected_ad_id"] = ad_id
            logger.info(f"Ad ID {ad_id} provided as argument for /open_dates.")
            cancel_button = InlineKeyboardButton("Отмена", callback_data="cancel_date_input")
            keyboard = InlineKeyboardMarkup([[cancel_button]])
            await update.message.reply_text(
                f"Вы выбрали объявление ID: {ad_id}.\n"
                "Теперь введите даты для открытия в формате: <code>ДД-ММ-ГГГГ ДД-ММ-ГГГГ</code> (например, 01-01-2024 05-01-2024).",
                parse_mode="HTML",
                reply_markup=keyboard,
            )
            return GETTING_DATES_OPEN
        except ValueError:
            await update.message.reply_text(
                "Неверный ID объявления. Пожалуйста, введите числовой ID."
            )
            return ConversationHandler.END
    else:
        logger.info("No ad ID provided for /open_dates, attempting to show ad list.")
        # Pass context and action_prefix. api_client is no longer needed.
        keyboard = await _get_user_ads_keyboard(context, action_prefix="opendates_ad")
        if keyboard:
            await update.message.reply_text(
                "Выберите объявление для открытия дат:", reply_markup=keyboard
            )
            return SELECTING_AD_OPEN
        else:
            await update.message.reply_text(
                "Не удалось получить список ваших объявлений. Попробуйте указать ID объявления напрямую: "
                "/open_dates <ID объявления>"
            )
            return ConversationHandler.END


async def calendar_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the conversation to view the calendar for an ad."""
    logger.info(f"/calendar command initiated by user {update.effective_user.id}")
    if context.user_data:  # Check if user_data has any content
        logger.info(
            f"Clearing previous user_data for user {update.effective_user.id} due to command restart."
        )
        context.user_data.clear()
    context.user_data["chat_id"] = update.effective_chat.id

    # Pass context and action_prefix.
    keyboard = await _get_user_ads_keyboard(context, action_prefix="calendar_ad")
    if keyboard:
        await update.message.reply_text(
            "Выберите объявление для просмотра календаря:", reply_markup=keyboard
        )
        return SELECTING_AD_CALENDAR
    else:
        await update.message.reply_text(
            "Не удалось получить список ваших объявлений. У вас есть активные объявления?"
        )
        return ConversationHandler.END


# --- Conversation States Handlers ---
async def select_ad_for_close_dates(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles ad selection for closing dates via inline keyboard."""
    query = update.callback_query
    await query.answer()
    ad_id = int(query.data.split("_")[2])  # e.g., "closedates_ad_12345"
    context.user_data["selected_ad_id"] = ad_id
    logger.info(f"User selected Ad ID {ad_id} for closing dates via inline keyboard.")

    cancel_button = InlineKeyboardButton("Отмена", callback_data="cancel_date_input")
    keyboard = InlineKeyboardMarkup([[cancel_button]])
    await query.edit_message_text(
        text=f"Вы выбрали объявление ID: {ad_id}.\n"
        "Теперь введите даты для закрытия в формате: <code>ДД-ММ-ГГГГ ДД-ММ-ГГГГ</code> (например, 25-12-2023 28-12-2023).",
        parse_mode="HTML",
        reply_markup=keyboard,
    )
    return GETTING_DATES_CLOSE


async def select_ad_for_open_dates(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles ad selection for opening dates via inline keyboard."""
    query = update.callback_query
    await query.answer()
    ad_id = int(query.data.split("_")[2])  # e.g., "opendates_ad_12345"
    context.user_data["selected_ad_id"] = ad_id
    logger.info(f"User selected Ad ID {ad_id} for opening dates via inline keyboard.")

    cancel_button = InlineKeyboardButton("Отмена", callback_data="cancel_date_input")
    keyboard = InlineKeyboardMarkup([[cancel_button]])
    await query.edit_message_text(
        text=f"Вы выбрали объявление ID: {ad_id}.\n"
        "Теперь введите даты для открытия в формате: <code>ДД-ММ-ГГГГ ДД-ММ-ГГГГ</code> (например, 01-01-2024 05-01-2024).",
        parse_mode="HTML",
        reply_markup=keyboard,
    )
    return GETTING_DATES_OPEN


async def select_ad_for_calendar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles ad selection for calendar view via inline keyboard."""
    query = update.callback_query
    await query.answer()
    # Assuming callback data like "calendar_ad_12345"
    ad_id = int(query.data.split("_")[2])
    context.user_data["selected_ad_id"] = ad_id
    logger.info(f"User selected Ad ID {ad_id} for calendar view via inline keyboard.")

    cancel_button = InlineKeyboardButton(
        "Отмена", callback_data="cancel_input"
    )  # Using "cancel_input" as agreed
    keyboard = InlineKeyboardMarkup([[cancel_button]])

    await query.edit_message_text(
        text=f"Вы выбрали объявление ID: {ad_id}.\n"
        "Введите количество месяцев, на которое отобразить календарь (1-12):",
        reply_markup=keyboard,
    )
    return GETTING_PERIOD_CALENDAR


async def cancel_ad_selection_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the 'Cancel' button press during ad selection."""
    query = update.callback_query
    await query.answer()  # Acknowledge the button press

    logger.info(f"User {query.from_user.id} canceled ad selection via inline button.")

    await query.edit_message_text(text="Выбор объявления отменен.")

    # Clear user_data that might have been set in this conversation
    context.user_data.clear()

    return ConversationHandler.END


async def cancel_date_input_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the 'Cancel' button press during date input."""
    query = update.callback_query
    await query.answer()  # Acknowledge the button press

    logger.info(f"User {query.from_user.id} canceled date input via inline button.")

    await query.edit_message_text(text="Ввод дат отменен.")

    context.user_data.clear()  # Clear user_data for this conversation

    return ConversationHandler.END


async def get_dates_for_close(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receives dates, closes them on Avito, and ends conversation."""
    user_input = update.message.text
    ad_id = context.user_data.get("selected_ad_id")
    api_client: AvitoApiClient = context.application.bot_data["avito_api_client"]

    if not ad_id:
        await update.message.reply_text(
            "ID объявления не найден. Пожалуйста, начните сначала с /close_dates."
        )
        return ConversationHandler.END

    logger.info(f"Received dates '{user_input}' for closing on Ad ID {ad_id}.")

    date_from_api, date_to_api, error_msg = _parse_date_range_input(user_input)

    if error_msg:
        await update.message.reply_text(
            error_msg + " Попробуйте еще раз или введите /cancel для отмены."
        )
        return GETTING_DATES_CLOSE  # Stay in the same state to allow re-entry

    success = await _manage_dates_on_ad(
        api_client, ad_id, date_from_api, date_to_api, "close", context
    )

    if success:
        confirmation_message = (
            f"Даты с {date_from_api} по {date_to_api} для объявления {ad_id} успешно закрыты."
        )
        await update.message.reply_text(confirmation_message)
        await notify_command_confirmation(context.bot, confirmation_message)  # Notify admin
        logger.info(f"Successfully closed dates for Ad ID {ad_id}: {date_from_api} - {date_to_api}")
    else:
        # Error message already sent by _manage_dates_on_ad
        logger.error(f"Failed to close dates for Ad ID {ad_id}: {date_from_api} - {date_to_api}")
        await update.message.reply_text(
            "Не удалось закрыть даты. Попробуйте позже или свяжитесь с поддержкой."
        )

    context.user_data.pop("selected_ad_id", None)
    context.user_data.pop("chat_id", None)
    return ConversationHandler.END


async def get_dates_for_open(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receives dates, opens them on Avito, and ends conversation."""
    user_input = update.message.text
    ad_id = context.user_data.get("selected_ad_id")
    api_client: AvitoApiClient = context.application.bot_data["avito_api_client"]

    if not ad_id:
        await update.message.reply_text(
            "ID объявления не найден. Пожалуйста, начните сначала с /open_dates."
        )
        return ConversationHandler.END

    logger.info(f"Received dates '{user_input}' for opening on Ad ID {ad_id}.")

    date_from_api, date_to_api, error_msg = _parse_date_range_input(user_input)

    if error_msg:
        await update.message.reply_text(
            error_msg + " Попробуйте еще раз или введите /cancel для отмены."
        )
        return GETTING_DATES_OPEN  # Stay in the same state

    success = await _manage_dates_on_ad(
        api_client, ad_id, date_from_api, date_to_api, "open", context
    )

    if success:
        confirmation_message = (
            f"Даты с {date_from_api} по {date_to_api} для объявления {ad_id} успешно открыты."
        )
        await update.message.reply_text(confirmation_message)
        await notify_command_confirmation(context.bot, confirmation_message)  # Notify admin
        logger.info(f"Successfully opened dates for Ad ID {ad_id}: {date_from_api} - {date_to_api}")
    else:
        logger.error(f"Failed to open dates for Ad ID {ad_id}: {date_from_api} - {date_to_api}")
        await update.message.reply_text(
            "Не удалось открыть даты. Попробуйте позже или свяжитесь с поддержкой."
        )

    context.user_data.pop("selected_ad_id", None)
    context.user_data.pop("chat_id", None)
    return ConversationHandler.END


async def get_period_and_display_calendar(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Receives number of months, fetches bookings, displays them, and ends conversation."""
    ad_id = context.user_data.get("selected_ad_id")
    if not ad_id:
        await update.message.reply_text(
            "ID объявления не найден. Пожалуйста, начните сначала с /calendar."
        )
        return ConversationHandler.END

    api_client: AvitoApiClient = context.application.bot_data["avito_api_client"]
    user_input = update.message.text
    months_num = 0

    try:
        months_num = int(user_input)
        if not (1 <= months_num <= 12):
            raise ValueError("Months must be between 1 and 12.")
    except ValueError:
        await update.message.reply_text(
            "Пожалуйста, введите число от 1 до 12. Попробуйте еще раз или введите /cancel для отмены."
        )
        return GETTING_PERIOD_CALENDAR  # Stay in the same state

    # Calculate dates
    date_start = datetime.date.today()
    date_end = date_start + relativedelta(months=+months_num)
    date_start_str = date_start.strftime("%Y-%m-%d")
    date_end_str = date_end.strftime("%Y-%m-%d")

    # Fetch Ad Title
    ad_title = f"Объявление ID {ad_id}"  # Default
    db_session_local = context.application.bot_data.get("db_session_local")
    if db_session_local:
        try:
            with db_session_local() as db:
                ad_model = (
                    db.query(AdDescriptionsModel)
                    .filter(AdDescriptionsModel.ad_id_avito == str(ad_id))
                    .first()
                )
                if ad_model:
                    ad_title = ad_model.title if ad_model.title else ad_model.address
        except Exception as e:
            logger.error(f"Error fetching ad title from DB for ad_id {ad_id}: {e}", exc_info=True)
            # Silently continue, will try API or use default if needed

    if ad_title == f"Объявление ID {ad_id}":  # If not found in DB or DB error
        try:
            item_details = api_client.get_item_details(item_id=ad_id)  # Synchronous
            if item_details:
                ad_title = item_details.get(
                    "title", item_details.get("address", f"Объявление ID {ad_id}")
                )
        except Exception as e:
            logger.error(
                f"Error fetching ad details from API for ad_id {ad_id}: {e}", exc_info=True
            )
            # Silently continue, use default title if API fails

    # Fetch bookings
    bookings_list = []
    try:
        logger.info(f"Fetching bookings for ad {ad_id} from {date_start_str} to {date_end_str}")
        # api_client.get_item_bookings уже возвращает список, если есть данные
        bookings_list = await api_client.get_item_bookings(  # <-- ДОБАВИТЬ AWAIT, т.к. api_client.get_item_bookings тоже async!
            item_id=ad_id, date_start=date_start_str, date_end=date_end_str, with_unpaid=True
        )
        # Remove this check: if bookings_data and 'list' in bookings_data:
        # bookings_list = bookings_data['list']
        logger.info(f"Received {len(bookings_list)} bookings for ad {ad_id}.")

    except Exception as e:
        logger.error(f"Error fetching bookings for ad {ad_id} from API: {e}", exc_info=True)
        await update.message.reply_text(
            f"Произошла ошибка при получении бронирований для объявления '{ad_title}'. Попробуйте позже."
        )
        context.user_data.clear()
        return ConversationHandler.END

    # Format message
    period_str = f"{date_start.strftime('%d-%m-%Y')} - {date_end.strftime('%d-%m-%Y')}"
    message_text = f"🗓️ Календарь бронирований для '{ad_title}'\nПериод: {period_str}\n\n"

    if bookings_list:
        for booking in bookings_list:
            try:
                # Даты: YYYY-MM-DD
                check_in_date_obj = datetime.datetime.strptime(
                    booking["check_in"], "%Y-%m-%d"
                ).date()
                check_out_date_obj = datetime.datetime.strptime(
                    booking["check_out"], "%Y-%m-%d"
                ).date()
                check_in_fmt = check_in_date_obj.strftime("%d-%m-%Y")
                check_out_fmt = check_out_date_obj.strftime("%d-%m-%Y")

                guest_name = booking.get("contact", {}).get("name", "Не указано")
                status = booking.get(
                    "status", "Неизвестно"
                )  # Это уже строка: 'active', 'pending', 'canceled'
                price = booking.get("base_price", "N/A")  # Цена в поле 'base_price'
                booking_id_avito = booking.get(
                    "avito_booking_id", "N/A"
                )  # ID бронирования называется 'avito_booking_id'

                message_text += (
                    f"Бронь ID: {booking_id_avito}\n"
                    f"  Заезд: {check_in_fmt}\n"
                    f"  Выезд: {check_out_fmt}\n"
                    f"  Гость: {guest_name}\n"
                    f"  Статус: {status}\n"
                    f"  Сумма: {price} руб.\n---\n"
                )
            except Exception as e:
                logger.error(
                    f"Error processing booking entry {booking.get('avito_booking_id')}: {e}",
                    exc_info=True,
                )
                message_text += f" - Ошибка при обработке данных бронирования ID {booking.get('avito_booking_id', 'N/A')}\n"
    else:
        message_text += "Нет бронирований на указанный период."

    await update.message.reply_text(message_text)

    try:
        await notify_command_confirmation(
            context.bot,
            f"Пользователь {update.effective_user.id} запросил календарь для '{ad_title}' на {months_num} мес.",
        )
    except Exception as e:
        logger.error(f"Error sending calendar request confirmation: {e}", exc_info=True)

    context.user_data.pop("selected_ad_id", None)
    context.user_data.pop("chat_id", None)
    return ConversationHandler.END


# --- Notification Functions ---
async def notify_new_booking(
    bot: Bot,
    ad_title: str,
    guest_name: str | None,
    check_in_date: str,
    check_out_date: str,
    total_price: float | None,
    avito_booking_id: str,
) -> None:
    """Notifies about a new booking."""
    guest_name_str = guest_name if guest_name else "Не указано"
    price_str = f"{total_price:.2f} руб." if total_price is not None else "Не указана"
    message = (
        f"🔔 Новое бронирование!\n"
        f"🏡 Объявление: {ad_title}\n"
        f"👤 Гость: {guest_name_str}\n"
        f"📅 Заезд: {check_in_date}\n"  # Assuming check_in_date is already DD-MM-YYYY or YYYY-MM-DD
        f"📅 Выезд: {check_out_date}\n"  # Assuming check_out_date is already DD-MM-YYYY or YYYY-MM-DD
        f"💰 Сумма: {price_str}\n"
        f"🆔 ID брони Avito: {avito_booking_id}"
    )
    logger.info(
        f"Attempting to send new booking notification for Ad: {ad_title}, Booking ID: {avito_booking_id}"
    )
    for chat_id in USER_TELEGRAM_IDS:
        await send_message(bot, chat_id, message)


async def notify_upcoming_check_in(
    bot: Bot,
    ad_title: str,
    guest_name: str | None,
    check_in_date: str,
    check_in_time: str | None,
    avito_booking_id: str,
) -> None:
    """Notifies about an upcoming check-in."""
    guest_name_str = guest_name if guest_name else "Не указано"
    time_str = check_in_time if check_in_time else "Время не указано"
    try:
        # Convert check_in_date (expected as YYYY-MM-DD from DB) to DD-MM-YYYY for display
        formatted_check_in_date = datetime.datetime.strptime(check_in_date, "%Y-%m-%d").strftime(
            "%d-%m-%Y"
        )
    except ValueError:
        formatted_check_in_date = check_in_date  # Fallback if format is unexpected

    message = (
        f"⏰ Напоминание о заселении!\n"
        f"🏡 Объявление: {ad_title}\n"
        f"👤 Гость: {guest_name_str}\n"
        f"📅 Дата: {formatted_check_in_date}\n"
        f"🕒 Время: {time_str}\n"
        f"🆔 ID брони Avito: {avito_booking_id}"
    )
    logger.info(
        f"Attempting to send upcoming check-in notification for Ad: {ad_title}, Booking ID: {avito_booking_id}"
    )
    for chat_id in USER_TELEGRAM_IDS:
        await send_message(bot, chat_id, message)


async def notify_client_check_in_intention(bot: Bot, address: str, time: str) -> None:
    """Notifies about a client's intention to check in."""
    message = f"Клиент по квартире {address} хочет заселиться в {time}."
    logger.info(
        f"Attempting to send client check-in intention notification for {address} at {time}"
    )
    for chat_id in USER_TELEGRAM_IDS:
        await send_message(bot, chat_id, message)


async def notify_ad_status_change(bot: Bot, ad_id: str, status: str) -> None:
    """Notifies about an ad status change."""
    message = f"Объявление {ad_id} изменило статус на: {status}."
    logger.info(
        f"Attempting to send ad status change notification for ad {ad_id}, new status: {status}"
    )
    for chat_id in USER_TELEGRAM_IDS:
        await send_message(bot, chat_id, message)


async def notify_promotion_issue(bot: Bot, issue_description: str) -> None:
    """Notifies about a promotion issue."""
    message = f"Проблема с продвижением: {issue_description}."
    logger.info(f"Attempting to send promotion issue notification: {issue_description}")
    for chat_id in USER_TELEGRAM_IDS:
        await send_message(bot, chat_id, message)


async def notify_low_balance(bot: Bot, balance: float) -> None:
    """Notifies about low Avito wallet balance."""
    message = f"Низкий баланс кошелька Авито: {balance} руб."
    logger.info(f"Attempting to send low balance notification: {balance}")
    for chat_id in USER_TELEGRAM_IDS:
        await send_message(bot, chat_id, message)


async def notify_command_confirmation(bot: Bot, message: str) -> None:
    """Sends a generic command confirmation message."""
    logger.info(f"Attempting to send command confirmation: {message}")
    for chat_id in USER_TELEGRAM_IDS:
        await send_message(bot, chat_id, message)


async def test_notify_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Temporary command to test notification functions."""
    if not USER_TELEGRAM_IDS:
        logger.error("USER_TELEGRAM_IDS not set, cannot send test notifications.")
        await update.message.reply_text(
            "USER_TELEGRAM_IDS не установлен. Тестовые уведомления не могут быть отправлены."
        )
        return

    logger.info(f"Test notify command received. Sending notifications to {USER_TELEGRAM_IDS}")
    await update.message.reply_text(f"Отправка тестовых уведомлений на ID: {USER_TELEGRAM_IDS}...")

    # Using DD-MM-YYYY for test notifications as well for consistency, though not strictly required by plan
    # await notify_new_booking(context.bot, "Тестовый адрес ул. Пушкина, д. Колотушкина", "01-01-2024", "05-01-2024")
    # Updated call for notify_new_booking:
    await notify_new_booking(
        context.bot,
        ad_title="Тестовое объявление Приморский бульвар, 1",
        guest_name="Иван Петров",
        check_in_date="01-08-2024",
        check_out_date="05-08-2024",
        total_price=12500.00,
        avito_booking_id="test_booking_123",
    )
    # await notify_upcoming_check_in(context.bot, "Тестовый адрес ул. Лермонтова, д. 15", "14:00")
    # Updated call for notify_upcoming_check_in:
    await notify_upcoming_check_in(
        context.bot,
        ad_title="Тестовое объявление Морская, 10",
        guest_name="Анна Сидорова",
        check_in_date="2024-08-15",  # YYYY-MM-DD for the function to format
        check_in_time="14:30",
        avito_booking_id="test_checkin_456",
    )
    await notify_client_check_in_intention(
        context.bot, "Тестовый адрес пр. Мира, д. 1", "12:30"
    )  # Stays same for now
    await notify_ad_status_change(context.bot, "adv_123456789", "активно")  # Stays same
    await notify_promotion_issue(context.bot, "Не удалось применить скидку X2")
    await notify_low_balance(context.bot, 150.25)
    await notify_command_confirmation(
        context.bot, "Тестовое подтверждение команды: Все прошло успешно!"
    )

    await update.message.reply_text("Тестовые уведомления отправлены.")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log Errors caused by Updates."""
    logger.error("Exception while handling an update:", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "Извините, произошла ошибка при обработке вашего запроса. Попробуйте еще раз."
            )
        except Exception as e:
            logger.error(f"Failed to send error message to user: {e}", exc_info=True)


def main() -> None:
    """Starts the bot."""
    logger.info("Starting bot...")

    if not AVITO_BOT_TOKEN:
        logger.error("AVITO_BOT_TOKEN not found. Bot cannot start.")
        return

    # Create the Application
    application = Application.builder().token(AVITO_BOT_TOKEN).build()
    logger.info("Telegram Application created.")

    # Register command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    # application.add_handler(CommandHandler("close_dates", close_dates_command)) # Replaced by ConversationHandler
    # application.add_handler(CommandHandler("open_dates", open_dates_command)) # Replaced by ConversationHandler
    application.add_handler(CommandHandler("testnotify", test_notify_command))

    # --- Conversation Handler for Closing Dates ---
    close_dates_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("close_dates", close_dates_start)],
        states={
            SELECTING_AD_CLOSE: [
                CallbackQueryHandler(select_ad_for_close_dates, pattern="^closedates_ad_\\d+$"),
                CallbackQueryHandler(cancel_ad_selection_callback, pattern="^cancel_ad_selection$"),
            ],
            GETTING_DATES_CLOSE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_dates_for_close),
                CallbackQueryHandler(cancel_date_input_callback, pattern="^cancel_date_input$"),
            ],
        },
        fallbacks=[],
        allow_reentry=True,
        # per_user=True, per_chat=True # Ensure user_data is specific
    )
    application.add_handler(close_dates_conv_handler)

    # --- Conversation Handler for Opening Dates ---
    open_dates_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("open_dates", open_dates_start)],
        states={
            SELECTING_AD_OPEN: [
                CallbackQueryHandler(select_ad_for_open_dates, pattern="^opendates_ad_\\d+$"),
                CallbackQueryHandler(cancel_ad_selection_callback, pattern="^cancel_ad_selection$"),
            ],
            GETTING_DATES_OPEN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_dates_for_open),
                CallbackQueryHandler(cancel_date_input_callback, pattern="^cancel_date_input$"),
            ],
        },
        fallbacks=[],
        allow_reentry=True,
        # per_user=True, per_chat=True
    )
    application.add_handler(open_dates_conv_handler)

    # --- Conversation Handler for Calendar View ---
    calendar_conv_states = {
        SELECTING_AD_CALENDAR: [
            CallbackQueryHandler(select_ad_for_calendar, pattern="^calendar_ad_\\d+$"),
            CallbackQueryHandler(cancel_ad_selection_callback, pattern="^cancel_ad_selection$"),
        ],
        GETTING_PERIOD_CALENDAR: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, get_period_and_display_calendar),
            CallbackQueryHandler(cancel_date_input_callback, pattern="^cancel_input$"),
        ],
    }
    calendar_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("calendar", calendar_start)],
        states=calendar_conv_states,
        fallbacks=[],  # No fallbacks for now, can be added for e.g. /cancel command
        allow_reentry=True,
    )
    application.add_handler(calendar_conv_handler)

    # Register error handler
    application.add_error_handler(error_handler)

    # logger.info("Bot is polling...") # Controlled by main.py now
    # application.run_polling() # Controlled by main.py now

    # logger.info("Bot stopped.") # Controlled by main.py now


# --- Conversation Handler for Closing Dates ---
close_dates_conv_handler = ConversationHandler(
    entry_points=[CommandHandler("close_dates", close_dates_start)],
    states={
        SELECTING_AD_CLOSE: [
            CallbackQueryHandler(select_ad_for_close_dates, pattern="^closedates_ad_\\d+$"),
            CallbackQueryHandler(cancel_ad_selection_callback, pattern="^cancel_ad_selection$"),
        ],
        GETTING_DATES_CLOSE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, get_dates_for_close),
            CallbackQueryHandler(cancel_date_input_callback, pattern="^cancel_date_input$"),
        ],
    },
    fallbacks=[],
    allow_reentry=True,
    # per_user=True, per_chat=True # Ensure user_data is specific
)

# --- Conversation Handler for Opening Dates ---
open_dates_conv_handler = ConversationHandler(
    entry_points=[CommandHandler("open_dates", open_dates_start)],
    states={
        SELECTING_AD_OPEN: [
            CallbackQueryHandler(select_ad_for_open_dates, pattern="^opendates_ad_\\d+$"),
            CallbackQueryHandler(cancel_ad_selection_callback, pattern="^cancel_ad_selection$"),
        ],
        GETTING_DATES_OPEN: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, get_dates_for_open),
            CallbackQueryHandler(cancel_date_input_callback, pattern="^cancel_date_input$"),
        ],
    },
    fallbacks=[],
    allow_reentry=True,
    # per_user=True, per_chat=True
)

# --- Conversation Handler for Calendar View ---
calendar_conv_states = {
    SELECTING_AD_CALENDAR: [
        CallbackQueryHandler(select_ad_for_calendar, pattern="^calendar_ad_\\d+$"),
        CallbackQueryHandler(cancel_ad_selection_callback, pattern="^cancel_ad_selection$"),
    ],
    GETTING_PERIOD_CALENDAR: [
        MessageHandler(filters.TEXT & ~filters.COMMAND, get_period_and_display_calendar),
        CallbackQueryHandler(cancel_date_input_callback, pattern="^cancel_input$"),
    ],
}
calendar_conv_handler = ConversationHandler(
    entry_points=[CommandHandler("calendar", calendar_start)],
    states=calendar_conv_states,
    fallbacks=[],  # No fallbacks for now, can be added for e.g. /cancel command
    allow_reentry=True,
)


def register_handlers(
    application: Application,
    avito_auth_instance: AvitoAuth,
    avito_api_client_instance: AvitoApiClient,
):
    """
    Registers all command handlers and conversation handlers with the bot.

    Sets up bot_data with necessary instances (auth, API client, database session)
    and registers all command handlers, conversation handlers, and error handlers.

    Args:
        application: Telegram Application instance
        avito_auth_instance: Authenticated AvitoAuth instance
        avito_api_client_instance: Initialized AvitoApiClient instance
    """
    # Store instances in bot_data for access in handlers
    application.bot_data["avito_auth"] = avito_auth_instance
    application.bot_data["avito_api_client"] = avito_api_client_instance
    application.bot_data["db_session_local"] = SessionLocal

    # Register command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("testnotify", test_notify_command))

    # --- Conversation Handler for Closing Dates ---
    close_dates_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("close_dates", close_dates_start)],
        states={
            SELECTING_AD_CLOSE: [
                CallbackQueryHandler(select_ad_for_close_dates, pattern="^closedates_ad_\\d+$"),
                CallbackQueryHandler(cancel_ad_selection_callback, pattern="^cancel_ad_selection$"),
            ],
            GETTING_DATES_CLOSE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_dates_for_close),
                CallbackQueryHandler(cancel_date_input_callback, pattern="^cancel_date_input$"),
            ],
        },
        fallbacks=[],
        allow_reentry=True,
    )
    application.add_handler(close_dates_conv_handler)

    # --- Conversation Handler for Opening Dates ---
    open_dates_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("open_dates", open_dates_start)],
        states={
            SELECTING_AD_OPEN: [
                CallbackQueryHandler(select_ad_for_open_dates, pattern="^opendates_ad_\\d+$"),
                CallbackQueryHandler(cancel_ad_selection_callback, pattern="^cancel_ad_selection$"),
            ],
            GETTING_DATES_OPEN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_dates_for_open),
                CallbackQueryHandler(cancel_date_input_callback, pattern="^cancel_date_input$"),
            ],
        },
        fallbacks=[],
        allow_reentry=True,
    )
    application.add_handler(open_dates_conv_handler)

    # --- Conversation Handler for Calendar View ---
    # Define calendar_conv_handler here within this function
    calendar_conv_states = {
        SELECTING_AD_CALENDAR: [
            CallbackQueryHandler(select_ad_for_calendar, pattern="^calendar_ad_\\d+$"),
            CallbackQueryHandler(cancel_ad_selection_callback, pattern="^cancel_ad_selection$"),
        ],
        GETTING_PERIOD_CALENDAR: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, get_period_and_display_calendar),
            CallbackQueryHandler(cancel_date_input_callback, pattern="^cancel_input$"),
        ],
    }
    calendar_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("calendar", calendar_start)],
        states=calendar_conv_states,
        fallbacks=[],
        allow_reentry=True,
    )

    # --- Conversation Handlers (defined globally) ---
    application.add_handler(close_dates_conv_handler)
    application.add_handler(open_dates_conv_handler)
    # calendar_conv_handler is defined in the global scope and can be accessed directly
    # calendar_conv_handler is defined in the global scope and can be accessed directly
    application.add_handler(calendar_conv_handler)

    # Register error handler
    application.add_error_handler(error_handler)
    logger.info("Telegram command and error handlers registered.")


# if __name__ == "__main__":
# main() # This main function is removed or commented as per plan
