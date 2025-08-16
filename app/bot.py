# app/bot.py (enhanced with inline calendar and Stripe payments)
import os
import logging
import asyncio
from dotenv import load_dotenv
from datetime import date, datetime
import tempfile
import csv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes, ConversationHandler,
    MessageHandler, filters, CallbackQueryHandler
)

import stripe

from db import fetch, fetchrow, execute, get_pool, with_transaction
from utils import parse_yyyy_mm_dd, days_between, ranges_overlap
from calendar import build_month_keyboard

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
MASTER_PASSWORD = os.getenv('MASTER_PASSWORD', 'supersecretmasterpass')
STRIPE_API_KEY = os.getenv('STRIPE_API_KEY')
APP_HOST = os.getenv('APP_HOST', 'http://localhost')
APP_PORT = os.getenv('APP_PORT', '8080')

if STRIPE_API_KEY:
    stripe.api_key = STRIPE_API_KEY

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Conversation states
(START_REG, PET_NAME, PET_SPECIES, PET_BREED, PET_COLOR, PET_AGE, PET_WEIGHT, PET_LENGTH, PET_MICROCHIP, PET_VACC, PET_SPECIAL, PET_PHOTO, OWNER_NAME, OWNER_PHONE, CONFIRM) = range(15)

# Booking calendar states stored in user_data['cal']

admin_sessions = {}

async def ensure_owner(telegram_id: int, name: str = None, phone: str = None, email: str = None):
    try:
        row = await fetchrow('SELECT id FROM owners WHERE telegram_id=$1', telegram_id)
        if row:
            return row['id']
        res = await fetchrow('INSERT INTO owners (telegram_id, name, phone, email) VALUES ($1,$2,$3,$4) RETURNING id', telegram_id, name or 'Unknown', phone, email)
        return res['id']
    except Exception as e:
        logger.exception('DB error in ensure_owner')
        raise

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome to PetHotelBot!\nCommands:\n/register_pet - register your pet\n/my_pets - list pets\n/book - book a kennel for a pet\n/admin <password> - admin login\n/export_bookings - admin CSV export"
    )

# (registration flows unchanged, omitted here for brevity) - keep original registration handlers
# For brevity in this file we reuse the registration handlers from earlier version.

# We'll re-import them dynamically to keep the example concise in the zip.
from registration import *

# Booking handlers (use inline calendar)
async def book_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.message.from_user
        row = await fetchrow('SELECT id FROM owners WHERE telegram_id=$1', user.id)
        if not row:
            await update.message.reply_text('You need to register a pet first with /register_pet')
            return
        owner_id = row['id']
        pets = await fetch('SELECT id, name FROM pets WHERE owner_id=$1', owner_id)
        if not pets:
            await update.message.reply_text('No pets found. Use /register_pet.')
            return
        kb = [[InlineKeyboardButton(f"{p['name']} (ID:{p['id']})", callback_data=f"selectpet:{p['id']}")] for p in pets]
        await update.message.reply_text('Choose pet to book:', reply_markup=InlineKeyboardMarkup(kb))
    except Exception as e:
        logger.exception('Error in book_start')
        await update.message.reply_text('Sorry, something went wrong while starting booking. Please try again later.')

async def callback_select_pet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()
        _, pet_id = query.data.split(':')
        context.user_data['booking'] = {'pet_id': int(pet_id)}
        kennels = await fetch('SELECT id, code, size, daily_price FROM kennels WHERE is_active=true')
        kb = [[InlineKeyboardButton(f"{k['code']} ({k['size']}) - ${k['daily_price']}/day", callback_data=f"selectkennel:{k['id']}")] for k in kennels]
        await query.edit_message_text('Choose kennel (availability checked after you enter dates):', reply_markup=InlineKeyboardMarkup(kb))
    except Exception:
        logger.exception('callback_select_pet')
        await query.edit_message_text('Error selecting pet. Try again.')

async def callback_select_kennel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, kennel_id = query.data.split(':')
    context.user_data['booking']['kennel_id'] = int(kennel_id)
    # Launch calendar for start date
    today = datetime.utcnow().date()
    kb_struct = build_month_keyboard(today.year, today.month, 'startcal')
    keyboard = [[InlineKeyboardButton(cell['text'], callback_data=cell['callback_data']) for cell in row] for row in kb_struct]
    await query.edit_message_text('Select START date:', reply_markup=InlineKeyboardMarkup(keyboard))

# Calendar callbacks
async def calendar_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    try:
        parts = data.split(':')
        prefix = parts[0]
        action = parts[1]
        if action == 'month':
            y,m = map(int, parts[2].split('-'))
            kb_struct = build_month_keyboard(y, m, prefix)
            keyboard = [[InlineKeyboardButton(cell['text'], callback_data=cell['callback_data']) for cell in row] for row in kb_struct]
            await query.edit_message_text('Pick a date:', reply_markup=InlineKeyboardMarkup(keyboard))
            return
        if action == 'day':
            sel_date = datetime.strptime(parts[2], '%Y-%m-%d').date()
            if prefix == 'startcal':
                context.user_data['booking']['start_date'] = sel_date
                # ask for end date with calendar starting at same month
                kb_struct = build_month_keyboard(sel_date.year, sel_date.month, 'endcal')
                keyboard = [[InlineKeyboardButton(cell['text'], callback_data=cell['callback_data']) for cell in row] for row in kb_struct]
                await query.edit_message_text(f'Start date set to {sel_date}. Now select END date:', reply_markup=InlineKeyboardMarkup(keyboard))
                return
            if prefix == 'endcal':
                context.user_data['booking']['end_date'] = sel_date
                booking = context.user_data['booking']
                if booking['end_date'] < booking['start_date']:
                    await query.edit_message_text('End date must be after start date. Please start again with /book.')
                    context.user_data.pop('booking', None)
                    return
                # Check availability
                available = await is_kennel_available(booking['kennel_id'], booking['start_date'], booking['end_date'])
                if not available:
                    await query.edit_message_text('Selected kennel is not available for these dates. Start /book again and choose other dates or kennel.')
                    context.user_data.pop('booking', None)
                    return
                # Ask for food
                foods = await fetch('SELECT id, name, unit_price FROM foods')
                kb = [[InlineKeyboardButton(f"{f['name']} - ${f['unit_price']}", callback_data=f"selectfood:{f['id']}")] for f in foods]
                await query.edit_message_text('Choose food option:', reply_markup=InlineKeyboardMarkup(kb))
                return
    except Exception:
        logger.exception('calendar_callback')
        await query.edit_message_text('Calendar error. Try /book again.')

async def is_kennel_available(kennel_id: int, start_date, end_date) -> bool:
    try:
        row = await fetchrow('''SELECT COUNT(*) FROM bookings WHERE kennel_id=$1 AND ($2 <= end_date) AND ($3 >= start_date)''', kennel_id, start_date, end_date)
        return row['count'] == 0
    except Exception:
        logger.exception('is_kennel_available')
        return False

async def callback_select_food(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, food_id = query.data.split(':')
    context.user_data['booking']['food_id'] = int(food_id)
    await query.edit_message_text('Enter food quantity (number of units for stay):')

# Other booking steps same as before; reuse handlers from registration module and previous implementation for quantity, feeding, services
from booking_steps import *

# Admin/export/payment handlers reused
from admin_handlers import *

async def main():
    await get_pool()
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # registration conversation from registration.py
    from registration import conv as reg_conv
    application.add_handler(reg_conv)

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('my_pets', my_pets))
    application.add_handler(CommandHandler('book', book_start))
    application.add_handler(CallbackQueryHandler(callback_select_pet, pattern='^selectpet:' ))
    application.add_handler(CallbackQueryHandler(callback_select_kennel, pattern='^selectkennel:' ))
    application.add_handler(CallbackQueryHandler(calendar_callback, pattern='^(startcal|endcal):'))
    application.add_handler(CallbackQueryHandler(callback_select_food, pattern='^selectfood:' ))

    # text handlers reused
    from booking_steps import book_start_date_handler, book_end_date_handler, food_quantity_handler, feeding_freq_handler, services_done_handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, book_start_date_handler), block=False)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, book_end_date_handler), block=False)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, food_quantity_handler), block=False)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, feeding_freq_handler), block=False)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, services_done_handler), block=False)

    # admin handlers
    from admin_handlers import admin_cmd_handler, admin_stats_handler, list_clients_handler, export_bookings_handler
    application.add_handler(CommandHandler('admin', admin_cmd_handler))
    application.add_handler(CommandHandler('admin_stats', admin_stats_handler))
    application.add_handler(CommandHandler('list_clients', list_clients_handler))
    application.add_handler(CommandHandler('export_bookings', export_bookings_handler))

    logger.info('Starting bot...')
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    await application.idle()

if __name__ == '__main__':
    asyncio.run(main())
