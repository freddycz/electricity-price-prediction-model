from flask import Flask, render_template, request
from datetime import datetime, timedelta
from database import get_data_for_date

app = Flask(__name__)

@app.route("/")
def dashboard():
    date_str = request.args.get('date', datetime.today().strftime('%Y-%m-%d'))
    period_str = request.args.get('period')
    
    try:
        current_date = datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        current_date = datetime.today()
        date_str = current_date.strftime('%Y-%m-%d')
        
    data = get_data_for_date(date_str, period_str)
    
    prev_date = (current_date - timedelta(days=1)).strftime('%Y-%m-%d')
    next_date = (current_date + timedelta(days=1)).strftime('%Y-%m-%d')

    if period_str and data["period_stats"]:
        if request.headers.get('HX-Request'):
            return render_template("period_stats.html", data=data)
        else:
            return render_template("index.html", data=data, prev_date=prev_date, next_date=next_date, show_period=True)

    '''
    if request.headers.get('HX-Request') and not period_str:
         return render_template("index.html", data=data, prev_date=prev_date, next_date=next_date)
    '''
    return render_template("index.html", data=data, prev_date=prev_date, next_date=next_date, show_period=False)
