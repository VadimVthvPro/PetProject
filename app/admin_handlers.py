# app/admin_handlers.py - admin handlers for the bot (wrapped functions)
from telegram import Update, InputFile
from telegram.ext import ContextTypes
from db import fetch, fetchrow
import tempfile, csv, os

from bot_constants import MASTER_PASSWORD

admin_sessions = {}

async def admin_cmd_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if args:
        if args[0] == MASTER_PASSWORD:
            admin_sessions[update.message.from_user.id] = True
            await update.message.reply_text('Admin authenticated. Use /admin_stats, /list_clients, /export_bookings')
            return
        else:
            await update.message.reply_text('Wrong password.')
            return
    await update.message.reply_text('Send /admin <password> to authenticate.')

async def admin_stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    if not admin_sessions.get(uid):
        await update.message.reply_text('Not authenticated. Use /admin <password>.')
        return
    total_pets = await fetchrow('SELECT COUNT(*) FROM pets')
    total_bookings = await fetchrow('SELECT COUNT(*) FROM bookings')
    revenue = await fetchrow('SELECT COALESCE(SUM(estimated_price),0) FROM bookings')
    s = f"Stats:\nPets: {total_pets['count']}\nBookings: {total_bookings['count']}\nEstimated revenue: ${float(revenue['coalesce']):.2f}"
    await update.message.reply_text(s)

async def list_clients_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    if not admin_sessions.get(uid):
        await update.message.reply_text('Not authenticated. Use /admin <password>.')
        return
    rows = await fetch('SELECT o.id as owner_id, o.name, o.phone, p.id as pet_id, p.name as pet_name FROM owners o LEFT JOIN pets p ON p.owner_id=o.id ORDER BY o.id')
    s = 'Clients and pets:\n'
    for r in rows:
        s += f"Owner #{r['owner_id']}: {r['name']} ({r['phone']}) — Pet #{r['pet_id']}: {r['pet_name']}\n"
    await update.message.reply_text(s)

async def export_bookings_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    if not admin_sessions.get(uid):
        await update.message.reply_text('Not authenticated. Use /admin <password>.')
        return
    rows = await fetch('''SELECT b.id, o.name as owner_name, p.name as pet_name, k.code as kennel_code, b.start_date, b.end_date, f.name as food_name, b.food_quantity, b.feeding_frequency_per_day, b.services, b.estimated_price, b.created_at FROM bookings b JOIN pets p ON p.id=b.pet_id JOIN owners o ON o.id=p.owner_id LEFT JOIN kennels k ON k.id=b.kennel_id LEFT JOIN foods f ON f.id=b.food_id ORDER BY b.created_at DESC''')
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.csv')
    try:
        writer = csv.writer(tmp)
        writer.writerow(['booking_id','owner','pet','kennel','start_date','end_date','food','food_qty','freq_per_day','services','estimated_price','created_at'])
        for r in rows:
            writer.writerow([r['id'], r['owner_name'], r['pet_name'], r['kennel_code'], r['start_date'], r['end_date'], r['food_name'], r['food_quantity'], r['feeding_frequency_per_day'], r['services'], float(r['estimated_price']) if r['estimated_price'] else '', r['created_at']])
        tmp.flush()
        tmp.close()
        with open(tmp.name, 'rb') as f:
            await update.message.reply_document(document=InputFile(f, filename='bookings.csv'))
    finally:
        try:
            os.unlink(tmp.name)
        except:
            pass
