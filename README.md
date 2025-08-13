PetHotelBot - Complete Package (Datepicker, Payments, Tests)
-----------------------------------------------------------

This package includes:
- Telegram bot with inline calendar date pickers
- Stripe Checkout payment flow (requires STRIPE_API_KEY in .env)
- PayPal placeholder endpoint and instructions
- Admin web UI (FastAPI) with CSV export
- Unit tests (pytest) for utils & calendar

Quick start:

1. Copy the repo to your machine.
2. Open `.env.example`, set `BOT_TOKEN`, `MASTER_PASSWORD`, and (optionally) `STRIPE_API_KEY`; save as `.env`.
3. Run:

   docker compose up --build

Notes:
- Stripe checkout requires valid `STRIPE_API_KEY`. For local testing use Stripe test keys.
- After booking, users will receive a payment URL if Stripe is configured.
- PayPal support is a placeholder and requires you to implement PayPal SDK integration.
