# app/admin_web.py - Admin UI + Stripe endpoints
import os
from fastapi import FastAPI, Request, HTTPException, Form
from fastapi.responses import HTMLResponse, StreamingResponse, PlainTextResponse, RedirectResponse
import csv, io, asyncio
from dotenv import load_dotenv
from db import get_pool
from datetime import datetime
import stripe

load_dotenv()
MASTER_PASSWORD = os.getenv('MASTER_PASSWORD', 'supersecretmasterpass')
STRIPE_API_KEY = os.getenv('STRIPE_API_KEY')
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')
APP_HOST = os.getenv('APP_HOST', 'http://localhost')
APP_PORT = os.getenv('APP_PORT', '8080')

if STRIPE_API_KEY:
    stripe.api_key = STRIPE_API_KEY

app = FastAPI()

def check_token(token: str):
    return token == MASTER_PASSWORD

@app.get('/', response_class=HTMLResponse)
async def index(request: Request, token: str = ''):
    if not check_token(token):
        raise HTTPException(status_code=401, detail='Unauthorized - provide ?token=MASTER_PASSWORD')
    pool = await get_pool()
    async with pool.acquire() as conn:
        total_pets = await conn.fetchval('SELECT COUNT(*) FROM pets')
        total_bookings = await conn.fetchval('SELECT COUNT(*) FROM bookings')
        revenue = await conn.fetchval('SELECT COALESCE(SUM(estimated_price),0) FROM bookings')
        kennels = await conn.fetch('SELECT id, code, size, daily_price, is_active FROM kennels ORDER BY id')
    html = f"""<html><head><title>PetHotel Admin</title></head><body>
    <h1>PetHotel - Admin</h1>
    <p>Total pets: {total_pets}</p>
    <p>Total bookings: {total_bookings}</p>
    <p>Estimated revenue: ${float(revenue):.2f}</p>
    <h2>Kennels</h2>
    <ul>
    """
    for k in kennels:
        html += f"<li>{k['code']} ({k['size']}) - ${k['daily_price']} - {'active' if k['is_active'] else 'inactive'}</li>"
    html += "</ul>"
    html += f"<p><a href='/export_bookings?token={token}'>Download bookings CSV</a></p>"
    html += "</body></html>"
    return HTMLResponse(content=html)

@app.get('/export_bookings')
async def export_bookings(token: str = ''):
    if not check_token(token):
        raise HTTPException(status_code=401, detail='Unauthorized')
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch('''SELECT b.id, o.name as owner_name, p.name as pet_name, k.code as kennel_code, b.start_date, b.end_date, f.name as food_name, b.food_quantity, b.feeding_frequency_per_day, b.services, b.estimated_price, b.created_at FROM bookings b JOIN pets p ON p.id=b.pet_id JOIN owners o ON o.id=p.owner_id LEFT JOIN kennels k ON k.id=b.kennel_id LEFT JOIN foods f ON f.id=b.food_id ORDER BY b.created_at DESC''')
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(['booking_id','owner','pet','kennel','start_date','end_date','food','food_qty','freq_per_day','services','estimated_price','created_at'])
    for r in rows:
        writer.writerow([r['id'], r['owner_name'], r['pet_name'], r['kennel_code'], r['start_date'], r['end_date'], r['food_name'], r['food_quantity'], r['feeding_frequency_per_day'], r['services'], float(r['estimated_price']) if r['estimated_price'] else '', r['created_at']])
    buf.seek(0)
    filename = f'bookings_{datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")}.csv'
    return StreamingResponse(iter([buf.getvalue()]), media_type='text/csv', headers={'Content-Disposition': f'attachment; filename="{filename}"'})

# Success and cancel pages for Stripe
@app.get('/payment_success', response_class=HTMLResponse)
async def payment_success(session_id: str = None):
    return HTMLResponse('<html><body><h1>Payment successful</h1><p>Thank you. You can close this page.</p></body></html>')

@app.get('/payment_cancel', response_class=HTMLResponse)
async def payment_cancel():
    return HTMLResponse('<html><body><h1>Payment cancelled</h1><p>Your booking is saved but not paid.</p></body></html>')

# (Optional) basic Stripe webhook handler placeholder
@app.post('/stripe_webhook')
async def stripe_webhook(request: Request):
    if not STRIPE_WEBHOOK_SECRET:
        return PlainTextResponse('Webhook not configured', status_code=400)
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    # handle event types here (checkout.session.completed, etc.)
    return {'status': 'received'}
