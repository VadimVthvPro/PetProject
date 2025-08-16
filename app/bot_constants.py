# constants used across modules
from dotenv import load_dotenv
import os
load_dotenv()
MASTER_PASSWORD = os.getenv('MASTER_PASSWORD', 'supersecretmasterpass')
# conversation states (same numbers as in bot.py)
(START_REG, PET_NAME, PET_SPECIES, PET_BREED, PET_COLOR, PET_AGE, PET_WEIGHT, PET_LENGTH, PET_MICROCHIP, PET_VACC, PET_SPECIAL, PET_PHOTO, OWNER_NAME, OWNER_PHONE, CONFIRM) = range(15)
