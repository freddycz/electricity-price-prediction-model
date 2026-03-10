import os
from datetime import datetime, timedelta

from flask import Flask, render_template, request

from modules.database import Database
from worker import start_background_worker

app = Flask(__name__)

# Ošetření proti dvojímu spuštění v debug módu Flasku (reloader)
if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or os.environ.get("FLASK_RUN_FROM_CLI") is None:
    start_background_worker()

@app.route("/")
def dashboard():
    date_str = request.args.get('date', (datetime.today() + timedelta(days=1)).strftime('%Y-%m-%d'))
    period_str = request.args.get('period')
    
    try:
        current_date = datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        current_date = datetime.today()
        date_str = current_date.strftime('%Y-%m-%d')
        
    db = Database()
    data = db.get_data_for_date(date_str)
    
    if period_str:
        data["period_stats"] = db.get_data_for_period(date_str, period_str)
    
    prev_date = (current_date - timedelta(days=1)).strftime('%Y-%m-%d')
    next_date = (current_date + timedelta(days=1)).strftime('%Y-%m-%d')

    if period_str and data.get("period_stats"):
        if request.headers.get('HX-Request'):
            return render_template("period_stats.html", data=data)
        else:
            return render_template("index.html", data=data, prev_date=prev_date, next_date=next_date, show_period=True)

    return render_template("index.html", data=data, prev_date=prev_date, next_date=next_date, show_period=False)
