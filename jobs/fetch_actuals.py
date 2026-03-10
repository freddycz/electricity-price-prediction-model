import os
import sys
from datetime import datetime, timedelta

# Add the parent directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from modules.database import Database
from modules.ote_api import OteFetcher


def run_actual_prices_fetch(target_date_str):
    print(f"Fetching actual market prices for date: {target_date_str}")
    
    # Init fetcher 
    ote = OteFetcher(target_date_str)
    
    # Try fetching array of 15 min prices
    actuals_list = ote.get_electricity_prices()
    
    db = Database()
    db.save_actual_prices(target_date_str, actuals_list)
    print(f"Successfully saved {len(actuals_list)} actual prices to database for {target_date_str}.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        target_date = sys.argv[1]
    else:
        target_date = (datetime.today() + timedelta(days=1)).strftime('%Y-%m-%d')
        
    run_actual_prices_fetch(target_date)
