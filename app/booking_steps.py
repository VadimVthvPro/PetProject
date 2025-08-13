# app/booking_steps.py - handlers for booking steps that use text input (quantity, freq, services)
from telegram import Update
from telegram.ext import ContextTypes
from db import fetchrow, execute, with_transaction, fetch
from datetime import datetime
from utils import days_between
import logging
logger = logging.getLogger(__name__)

async def book_start_date_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # this handler is invoked for general text messages; ignore if not in booking flow
    if 'booking' not in context.user_data or 'kennel_id' not in context.user_data['booking']:
        return
    # try to parse as date (legacy path) - but calendar should handle dates
    d = None
    try:
        d = datetime.strptime(update.message.text.strip(), '%Y-%m-%d').date()
    except:
        return
    context.user_data['booking']['start_date'] = d
    await update.message.reply_text('Enter end date (YYYY-MM-DD)')

async def book_end_date_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'booking' not in context.user_data or 'start_date' not in context.user_data['booking']:
        return
    try:
        d = datetime.strptime(update.message.text.strip(), '%Y-%m-%d').date()
    except:
        return
    booking = context.user_data['booking']
    booking['end_date'] = d
    if booking['end_date'] < booking['start_date']:
        await update.message.reply_text('End date must be after start date. Start again with /book.')
        context.user_data.pop('booking', None)
        return
    foods = await fetch('SELECT id, name, unit_price FROM foods')
    kb = [[InlineKeyboardButton(f"{f['name']} - ${f['unit_price']}", callback_data=f"selectfood:{f['id']}")] for f in foods]
    await update.message.reply_text('Choose food option:', reply_markup=InlineKeyboardMarkup(kb))

async def food_quantity_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'booking' not in context.user_data or 'food_id' not in context.user_data['booking']:
        return
    try:
        q = int(update.message.text.strip())
    except:
        await update.message.reply_text('Please enter a valid integer for food quantity.')
        return
    context.user_data['booking']['food_quantity'] = q
    await update.message.reply_text('Feeding frequency per day (e.g. 2):')

async def feeding_freq_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'booking' not in context.user_data or 'food_quantity' not in context.user_data['booking']:
        return
    try:
        f = int(update.message.text.strip())
    except:
        await update.message.reply_text('Please enter a valid integer for feeding frequency.')
        return
    context.user_data['booking']['feeding_frequency_per_day'] = f
    await update.message.reply_text('Additional services? (comma separated: grooming, walking) or type none:')

async def services_done_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'booking' not in context.user_data or 'feeding_frequency_per_day' not in context.user_data['booking']:
        return
    services = update.message.text.strip()
    booking = context.user_data['booking']
    booking['services'] = services

    # Save booking in transaction and compute price
    async def tx(conn):
        res = await conn.fetchrow('''SELECT COUNT(*) FROM bookings WHERE kennel_id=$1 AND ($2 <= end_date) AND ($3 >= start_date)''', booking['kennel_id'], booking['start_date'], booking['end_date'])
        if res['count'] != 0:
            raise RuntimeError('Selected kennel is no longer available')
        k = await conn.fetchrow('SELECT daily_price FROM kennels WHERE id=$1', booking['kennel_id'])
        f = await conn.fetchrow('SELECT unit_price FROM foods WHERE id=$1', booking['food_id'])
        days = (booking['end_date'] - booking['start_date']).days + 1
        kennel_total = float(k['daily_price']) * days
        food_total = float(f['unit_price']) * booking['food_quantity']
        svc_total = 0
        if 'groom' in services.lower():
            svc_total += 5
        if 'walk' in services.lower():
            svc_total += 2
        est = kennel_total + food_total + svc_total
        booking['estimated_price'] = est
        rec = await conn.execute('''INSERT INTO bookings (pet_id, kennel_id, start_date, end_date, food_id, food_quantity, feeding_frequency_per_day, services, estimated_price) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
        ''', booking['pet_id'], booking['kennel_id'], booking['start_date'], booking['end_date'], booking['food_id'], booking['food_quantity'], booking['feeding_frequency_per_day'], booking['services'], booking['estimated_price'])
        return est

    try:
        est = await with_transaction(tx)
    except Exception as e:
        await update.message.reply_text('Sorry, booking failed because the kennel was taken. Please try different dates or kennel.')
        context.user_data.pop('booking', None)
        return

    # If Stripe configured, create a checkout session
    import stripe, os
    STRIPE_API_KEY = os.getenv('STRIPE_API_KEY')
    if STRIPE_API_KEY:
        stripe.api_key = STRIPE_API_KEY
        try:
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data':{
                        'currency':'usd',
                        'product_data':{'name':'Pet Hotel Booking'},
                        'unit_amount': int(est*100)
                    },
                    'quantity':1
                }],
                mode='payment',
                success_url=f"{os.getenv('APP_HOST','http://localhost')}:{os.getenv('APP_PORT','8080')}/payment_success?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{os.getenv('APP_HOST','http://localhost')}:{os.getenv('APP_PORT','8080')}/payment_cancel",
            )
            await update.message.reply_text(f'Booking confirmed with estimated price ${est:.2f}. Pay here: {session.url}')
            context.user_data.pop('booking', None)
            return
        except Exception:
            logger.exception('Stripe session creation failed')
            await update.message.reply_text(f'Booking confirmed (${est:.2f}) but payment link could not be created. Admin will contact you.')
            context.user_data.pop('booking', None)
            return
    else:
        await update.message.reply_text(f'Booking confirmed! Estimated price: ${est:.2f}. Payment not configured. Admin will contact you.')
        context.user_data.pop('booking', None)
        return

