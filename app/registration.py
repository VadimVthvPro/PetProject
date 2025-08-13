# app/registration.py - registration conversation extracted for modularity
from telegram import Update
from telegram.ext import MessageHandler, filters, CommandHandler, ConversationHandler, ContextTypes
from db import fetchrow, execute
from utils import parse_yyyy_mm_dd

# reuse state constants
from bot_constants import *

async def register_pet_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Let\'s register a pet. What is the pet\'s name?')
    return PET_NAME

async def pet_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['pet'] = {}
    context.user_data['pet']['name'] = update.message.text.strip()
    await update.message.reply_text('Species (e.g. dog, cat):')
    return PET_SPECIES

async def pet_species(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['pet']['species'] = update.message.text.strip()
    await update.message.reply_text('Breed (or "unknown"):')
    return PET_BREED

async def pet_breed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['pet']['breed'] = update.message.text.strip()
    await update.message.reply_text('Color:')
    return PET_COLOR

async def pet_color(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['pet']['color'] = update.message.text.strip()
    await update.message.reply_text('Age (years):')
    return PET_AGE

async def pet_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data['pet']['age'] = int(update.message.text.strip())
    except:
        context.user_data['pet']['age'] = None
    await update.message.reply_text('Weight (kg):')
    return PET_WEIGHT

async def pet_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data['pet']['weight_kg'] = float(update.message.text.strip())
    except:
        context.user_data['pet']['weight_kg'] = None
    await update.message.reply_text('Length (cm):')
    return PET_LENGTH

async def pet_length(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data['pet']['length_cm'] = float(update.message.text.strip())
    except:
        context.user_data['pet']['length_cm'] = None
    await update.message.reply_text('Microchip ID (or "none"):')
    return PET_MICROCHIP

async def pet_microchip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['pet']['microchip_id'] = update.message.text.strip()
    await update.message.reply_text('Vaccination notes (short):')
    return PET_VACC

async def pet_vacc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['pet']['vaccination_notes'] = update.message.text.strip()
    await update.message.reply_text('Special needs (if any):')
    return PET_SPECIAL

async def pet_special(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['pet']['special_needs'] = update.message.text.strip()
    await update.message.reply_text('Please send a photo of the pet (or type /skip):')
    return PET_PHOTO

async def pet_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        context.user_data['pet']['photo_file_id'] = file_id
    else:
        context.user_data['pet']['photo_file_id'] = None
    await update.message.reply_text('Now enter your full name (owner):')
    return OWNER_NAME

async def skip_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['pet']['photo_file_id'] = None
    await update.message.reply_text('Now enter your full name (owner):')
    return OWNER_NAME

async def owner_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['owner_name'] = update.message.text.strip()
    await update.message.reply_text('Phone number:')
    return OWNER_PHONE

async def owner_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['owner_phone'] = update.message.text.strip()
    pet = context.user_data['pet']
    s = f"Please confirm:\nPet: {pet.get('name')} ({pet.get('species')})\nBreed: {pet.get('breed')}\nAge: {pet.get('age')}\nWeight: {pet.get('weight_kg')} kg\nOwner: {context.user_data['owner_name']} - {context.user_data['owner_phone']}"
    await update.message.reply_text(s + "\n\nType /confirm to save or /cancel to abort.")
    return CONFIRM

async def confirm_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    owner_row = await fetchrow('SELECT id FROM owners WHERE telegram_id=$1', user.id)
    if owner_row:
        owner_id = owner_row['id']
    else:
        owner_res = await fetchrow('INSERT INTO owners (telegram_id, name, phone) VALUES ($1,$2,$3) RETURNING id', user.id, context.user_data.get('owner_name'), context.user_data.get('owner_phone'))
        owner_id = owner_res['id']
    pet = context.user_data['pet']
    await execute(
        '''INSERT INTO pets (owner_id, name, species, breed, color, age, weight_kg, length_cm, microchip_id, vaccination_notes, special_needs, photo_file_id)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
        ''',
        owner_id, pet.get('name'), pet.get('species'), pet.get('breed'), pet.get('color'), pet.get('age'), pet.get('weight_kg'), pet.get('length_cm'), pet.get('microchip_id'), pet.get('vaccination_notes'), pet.get('special_needs'), pet.get('photo_file_id')
    )
    await update.message.reply_text('Pet registered! Use /my_pets to see your pets or /book to make a booking.')
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Registration cancelled.')
    context.user_data.clear()
    return ConversationHandler.END

# ConversationHandler object to be imported
conv = ConversationHandler(
    entry_points=[CommandHandler('register_pet', register_pet_start)],
    states={
        PET_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, pet_name)],
        PET_SPECIES: [MessageHandler(filters.TEXT & ~filters.COMMAND, pet_species)],
        PET_BREED: [MessageHandler(filters.TEXT & ~filters.COMMAND, pet_breed)],
        PET_COLOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, pet_color)],
        PET_AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, pet_age)],
        PET_WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, pet_weight)],
        PET_LENGTH: [MessageHandler(filters.TEXT & ~filters.COMMAND, pet_length)],
        PET_MICROCHIP: [MessageHandler(filters.TEXT & ~filters.COMMAND, pet_microchip)],
        PET_VACC: [MessageHandler(filters.TEXT & ~filters.COMMAND, pet_vacc)],
        PET_SPECIAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, pet_special)],
        PET_PHOTO: [MessageHandler(filters.PHOTO, pet_photo), CommandHandler('skip', skip_photo)],
        OWNER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, owner_name)],
        OWNER_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, owner_phone)],
        CONFIRM: [CommandHandler('confirm', confirm_save), CommandHandler('cancel', cancel)]
    },
    fallbacks=[CommandHandler('cancel', cancel)]
)
