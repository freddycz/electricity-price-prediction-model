# database logic
import random

def get_data_for_date(date_str, period=None):
    """
    Returns mock data for the given date.
    The date parameter should be in 'YYYY-MM-DD' format.
    The optional period string adjusts the mocked metrics.
    """
    # Typical hourly prices (EUR/MWh) for a day in CZ (simulating standard shape with morning/evening peaks and low midday)
    hourly_prices = [
        60, 58, 55, 56, 60, 75, 95, 110, 105, 80, 60, 45, 
        30, 25, 35, 50, 70, 95, 115, 125, 110, 90, 75, 65
    ]

    random.seed(date_str)
    multiplier = random.uniform(0.7, 1.3)
    
    chart_data = [["Čas", "Predikce", "Skutečnost"]]
    
    for h in range(24):
        for m in (0, 15, 30, 45):
            time_str = f"{h:02d}:{m:02d}"
            base_price = hourly_prices[h] * multiplier
            
            # Base actual with 15-min fluctuation
            actual = base_price + random.uniform(-5, 5)
            
            # Prediction miss - normally small, but with occasional larger spikes up to ~15 EUR
            if random.random() < 0.10: # 10% chance of a larger miss
                miss = random.uniform(5, 15) * random.choice([-1, 1])
            else:
                miss = random.uniform(-3, 3)
                
            pred = actual + miss
            
            # Format to 2 decimal places and avoid negative prices unless typical (we cap at 0 for simplicity)
            actual = round(max(0, actual), 2)
            pred = round(max(0, pred), 2)
            
            chart_data.append([time_str, pred, actual])

    # Re-seed if a particular period string is provided so metrics change based on selection
    if period:
        random.seed(f"{date_str}_{period}")

    metrics = {
        "avg_error": round(1.7 * random.uniform(0.5, 1.5), 2),
        "bias": round(0.5 * random.uniform(-1.0, 1.5), 2),
        "max_abs_error": round(4.8 * random.uniform(0.8, 1.5), 2),
    }

    # Format bias with a plus sign if positive
    if metrics["bias"] > 0:
        metrics["bias"] = f"+{metrics['bias']}"
    else:
        metrics["bias"] = str(metrics["bias"])

    # Extract specific period stats if provided as integer (1-96)
    period_stats = None
    if period:
        try:
            period_idx = int(period)
            # data has header at 0, so 1st period is index 1
            if 1 <= period_idx < len(chart_data):
                item = chart_data[period_idx]
                time_label = item[0]
                pred = item[1]
                actual = item[2]
                error = round(pred - actual, 2)
                error_str = f"+{error}" if error > 0 else str(error)
                period_stats = {
                    "time": time_label,
                    "index": period_idx,
                    "predicted": pred,
                    "actual": actual,
                    "error": error_str
                }
        except ValueError:
            pass # Ignore if period is not a valid integer

    return {
        "date": date_str,
        "chart_data": chart_data,
        "metrics": metrics,
        "period_stats": period_stats
    }
