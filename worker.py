import logging
import os
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from jobs.fetch_actuals import run_actual_prices_fetch
from jobs.predict import create_prediction_pipeline

# 1. Nastavení logování (tohle u maturity ukaž, vypadá to profi)
os.makedirs("logs", exist_ok=True) 
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.FileHandler("logs/worker.log"), logging.StreamHandler(sys.stdout)]
)

# 2. Definice časového pásma
PRAGUE_TZ = ZoneInfo("Europe/Prague")

# Pomocné funkce pro logování a správné datum
def run_prediction_job():
    logging.info("Spouštím denní predikci...")
    try:
        # Původní predict.py run chytá target date (v main bloku s včerejškem kvůli day-ahead/real-time)
        # Nyní využijeme logiku, kterou preferuje predict skript - default datum
        target_date_str = (datetime.today() - timedelta(days=1)).strftime('%Y-%m-%d')
        create_prediction_pipeline(target_date_str)
        logging.info("Predikce byla úspěšně dokončena.")
    except Exception as e:
        logging.error(f"Chyba při běhu predikce: {e}", exc_info=True)

def sync_actual_prices_job():
    logging.info("Spouštím stahování skutečných cen...")
    try:
        # Skutečné ceny za včerejšek
        yesterday_str = (datetime.now(PRAGUE_TZ) - timedelta(days=1)).strftime('%Y-%m-%d')
        run_actual_prices_fetch(yesterday_str)
        logging.info("Stahování skutečných cen bylo úspěšně dokončeno.")
    except Exception as e:
        logging.error(f"Chyba při stahování skutečných cen: {e}", exc_info=True)

if __name__ == "__main__":
    logging.info("Worker startuje v standalone režimu... Časové pásmo: Europe/Prague")
    
    # Pro standalone běh použijeme BlockingScheduler
    standalone_scheduler = BlockingScheduler(timezone=PRAGUE_TZ)

    standalone_scheduler.add_job(
        run_prediction_job,
        trigger=CronTrigger(hour=14, minute=0, timezone=PRAGUE_TZ),
        id='prediction_job',
        name='Denní predikce na zítřek'
    )

    standalone_scheduler.add_job(
        sync_actual_prices_job,
        trigger=CronTrigger(hour=1, minute=15, timezone=PRAGUE_TZ),
        id='actuals_job',
        name='Stažení skutečných cen'
    )

    try:
        standalone_scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logging.info("Worker se ukončuje...")
