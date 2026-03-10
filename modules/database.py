import os
import statistics

import psycopg2
from dotenv import load_dotenv


class Database:
    def __init__(self):
        load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
        self.conn_str = os.getenv("POSTGRESQL_CONNECTION_STRING")
        if not self.conn_str:
            raise ValueError("POSTGRESQL_CONNECTION_STRING environment variable is not set.")

    def save_predictions(self, date_str, predictions_list):
        try:
            with psycopg2.connect(self.conn_str) as conn:
                with conn.cursor() as cursor:
                    for period_idx, pred in enumerate(predictions_list, start=1):
                        if pred is None or (isinstance(pred, float) and pred != pred):
                            continue
                            
                        cursor.execute('''
                            INSERT INTO price_predictions (delivery_date, period, predicted_price)
                            VALUES (%s, %s, %s)
                            ON CONFLICT (delivery_date, period) DO UPDATE 
                            SET predicted_price = EXCLUDED.predicted_price
                        ''', (date_str, period_idx, float(pred)))
                conn.commit()
        except Exception as e:
            print(f"Error saving predictions to database: {e}")

    def save_actual_prices(self, date_str, actuals_list):
        try:
            with psycopg2.connect(self.conn_str) as conn:
                with conn.cursor() as cursor:
                    for period_idx, actual in enumerate(actuals_list, start=1):
                        if actual is None or (isinstance(actual, float) and actual != actual):
                            continue
                            
                        cursor.execute('''
                            UPDATE price_predictions 
                            SET actual_price = %s
                            WHERE delivery_date = %s AND period = %s
                        ''', (float(actual), date_str, period_idx))
                conn.commit()
        except Exception as e:
            print(f"Error saving actual prices to database: {e}")


    def get_data_for_date(self, date_str):
        chart_data = [
            [
                {"label": "Čas", "type": "string"},
                {"label": "Predikce", "type": "number"},
                {"label": "Skutečnost", "type": "number"}
            ]
        ]
        
        predictions = []
        actuals = []
        errors = []
        
        try:
            with psycopg2.connect(self.conn_str) as conn:
                with conn.cursor() as cursor:
                    cursor.execute('''
                        SELECT period, predicted_price, actual_price 
                        FROM price_predictions 
                        WHERE delivery_date = %s 
                        ORDER BY period
                    ''', (date_str,))
                    
                    rows = cursor.fetchall()
                    
                    db_data = {row[0]: {'pred': row[1], 'actual': row[2]} for row in rows}
                    
                    for p in range(1, 97):
                        h = (p - 1) // 4
                        m = ((p - 1) % 4) * 15
                        time_str = f"{h:02d}:{m:02d}"
                        
                        period_data = db_data.get(p, {'pred': None, 'actual': None})
                        pred = period_data['pred']
                        actual = period_data['actual']
                        
                        pred_val = float(pred) if pred is not None else None
                        actual_val = float(actual) if actual is not None else None
                        
                        chart_data.append([time_str, pred_val, actual_val])
                        
                        if pred is not None and actual is not None:
                            errors.append(pred_val - actual_val)
                            
        except Exception as e:
            print(f"Error fetching data from database: {e}")

        # Calculate metrics
        avg_error = 0.0
        bias = 0.0
        max_abs_error = 0.0
        median_error = 0.0
        
        if errors:
            avg_error = sum(abs(e) for e in errors) / len(errors)
            bias = sum(errors) / len(errors)
            max_abs_error = max(abs(e) for e in errors)
            median_error = statistics.median(abs(e) for e in errors)
            
        metrics = {
            "avg_error": round(avg_error, 2),
            "bias": f"+{round(bias, 2)}" if bias > 0 else str(round(bias, 2)),
            "max_abs_error": round(max_abs_error, 2),
            "median_error": round(median_error, 2),
        }

        return {
            "date": date_str,
            "chart_data": chart_data,
            "metrics": metrics,
            "period_stats": None,
            "has_actual_data": len(errors) > 0,
            "has_prediction_data": len(db_data) > 0
        }

    def get_data_for_period(self, date_str, period_idx):
        period_idx = int(period_idx)
        period_stats = None
        
        try:
            with psycopg2.connect(self.conn_str) as conn:
                with conn.cursor() as cursor:
                    cursor.execute('''
                        SELECT predicted_price, actual_price 
                        FROM price_predictions 
                        WHERE delivery_date = %s AND period = %s
                    ''', (date_str, period_idx))
                    
                    row = cursor.fetchone()
                    
                    if row:
                        pred, actual = row
                        
                        pred = float(pred) if pred is not None else None
                        actual = float(actual) if actual is not None else None
                        
                        h = (period_idx - 1) // 4
                        m = ((period_idx - 1) % 4) * 15
                        time_label = f"{h:02d}:{m:02d}"
                        
                        if pred is not None and actual is not None:
                            error = round(pred - actual, 2)
                            error_str = f"+{error}" if error > 0 else str(error)
                        else:
                            error_str = "N/A"
                            
                        period_stats = {
                            "time": time_label,
                            "index": period_idx,
                            "predicted": pred if pred is not None else "N/A",
                            "actual": actual if actual is not None else "N/A",
                            "error": error_str
                        }
        except Exception as e:
            print(f"Error fetching period data from database: {e}")
            
        return period_stats
