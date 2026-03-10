import os
import sys
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import xgboost as xgb
from dotenv import load_dotenv

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from modules.database import Database
from modules.eex_api import EexFetcher
from modules.entsoe_api import EntsoeApi
from modules.ote_api import OteFetcher
from modules.spotrenewables_fetcher import SpotRenewables


def align_historical_to_target_pos(df_hist, len_p, hist_pos_col='pos'):
    if df_hist is None or df_hist.empty:
        return df_hist
        
    len_h = len(df_hist)
    if len_h == len_p:
        return df_hist

    df_map = pd.DataFrame({'pos': range(1, len_p + 1)})
    df_map['target_pos'] = df_map['pos']

    if len_p == 92 and len_h == 96:
        df_map.loc[df_map['pos'] > 8, 'target_pos'] += 4

    elif len_p == 100 and len_h == 96:
        df_map.loc[df_map['pos'] > 12, 'target_pos'] -= 4

    elif len_p == 96 and len_h == 92:
        df_map.loc[df_map['pos'] > 12, 'target_pos'] -= 4
        df_map.loc[df_map['pos'].between(9, 12), 'target_pos'] = -1

    elif len_p == 96 and len_h == 100:
        df_map.loc[df_map['pos'] > 12, 'target_pos'] += 4

    df_aligned = pd.merge(
        df_map, 
        df_hist, 
        left_on='target_pos', 
        right_on=hist_pos_col, 
        how='left',
        suffixes=('', '_hist')
    )

    cols_to_drop = ['target_pos', f'{hist_pos_col}_hist']
    if f'{hist_pos_col}_hist' not in df_aligned.columns and f'{hist_pos_col}_y' in df_aligned.columns:
        cols_to_drop = ['target_pos', f'{hist_pos_col}_y']
        
    df_aligned = df_aligned.drop(columns=cols_to_drop, errors='ignore')
    if hist_pos_col != 'pos' and 'pos' in df_aligned.columns:
        if f'{hist_pos_col}_x' in df_aligned.columns:
            df_aligned = df_aligned.rename(columns={f'{hist_pos_col}_x': hist_pos_col})
        else:
            df_aligned = df_aligned.rename(columns={'pos': hist_pos_col})

    return df_aligned

def create_prediction_pipeline(target_date_str):
    env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
    load_dotenv(env_path)
    
    api_key = os.getenv("ENTSOE_API_KEY")
    if not api_key:
        raise Exception("ENTSOE_API_KEY is not set")

    entsoe = EntsoeApi(api_key, target_date_str)
    ote = OteFetcher(target_date_str)
    eex = EexFetcher(target_date_str)
    spot_solar = SpotRenewables(target_date_str, country="Germany")
    spot_wind = SpotRenewables(target_date_str, country="Germany")

    df_cz_hydro = entsoe.get_czechia_hydro_lw()
    df_de_prod = entsoe.get_germany_production_lw()
    df_de_load = entsoe.get_germany_load()
    df_cz_load = entsoe.get_czechia_load()
    
    df = df_cz_load

    len_m = len(df)

    if 'pos' not in df_de_load.columns:
        df_de_load['pos'] = df_de_load.index + 1
    df = df.merge(df_de_load, on='pos', how='outer')
        
    if 'pos' not in df_de_prod.columns:
        df_de_prod['pos'] = df_de_prod.index + 1
    df_de_prod = align_historical_to_target_pos(df_de_prod, len_m)
    df = df.merge(df_de_prod, on='pos', how='outer')
        
    if 'pos' not in df_cz_hydro.columns:
        df_cz_hydro['pos'] = df_cz_hydro.index + 1
    df_cz_hydro = align_historical_to_target_pos(df_cz_hydro, len_m)
    df = df.merge(df_cz_hydro, on='pos', how='outer')
        
    df.rename(columns={'pos': 'period'}, inplace=True)
    df.sort_values(by='period', inplace=True)

    periods = len(df)
    if periods == 0:
        periods = 96
    
    # Peak load calculation
    p_start = 32
    p_end = 80
    if periods == 92:
        p_start -= 4
        p_end -= 4
    elif periods == 100:
        p_start += 4
        p_end += 4

    df['is_peak'] = 0
    df.loc[(df['period'] > p_start) & (df['period'] <= p_end), 'is_peak'] = 1

    df['sin_time'] = np.sin(2 * np.pi * df['period'] / periods)
    df['cos_time'] = np.cos(2 * np.pi * df['period'] / periods)

    lw_elec = ote.get_lw_electricity_prices()
    df['lw_price_baseload'] = lw_elec['baseload']
    df['lw_price_peakload'] = lw_elec['peakload']
    df['lw_price_offpeak'] = lw_elec['offpeak']
    
    prices_list = lw_elec['prices']
    if len(prices_list) == len(df):
        df['lw_price'] = prices_list
    else:
        df_prices = pd.DataFrame({'pos': range(1, len(prices_list) + 1), 'lw_price': prices_list})
        df_prices = align_historical_to_target_pos(df_prices, len(df))
        df['lw_price'] = df_prices['lw_price'].values

    gas_prices = ote.get_gas_prices()
    df['gas_price'] = gas_prices['price']
    df['lw_gas_price'] = gas_prices['lw_price']

    # EEX data
    price_loads = eex.get_price_loads()
    df['price_baseload'] = price_loads.get('baseload', np.nan)
    df['price_peakload'] = price_loads.get('peakload', np.nan)
    df['price_offpeak'] = price_loads.get('offpeak', np.nan)

    eua_prices = eex.get_eua_prices()
    df['eua_price'] = eua_prices.get('price', np.nan)
    df['lw_eua_price'] = eua_prices.get('lw_price', np.nan)

    # SpotRenewables
    solar_forecast = spot_solar.get_solar_forecast()
    wind_forecast = spot_wind.get_wind_forecast()

    df['wind_baseload'] = wind_forecast.get('baseload', np.nan)
    df['wind_peakload'] = wind_forecast.get('peakload', np.nan)
    df['wind_offpeak'] = wind_forecast.get('offpeak', np.nan)

    if 'lw_germany_solar_gen' in df.columns and 'lw_solar_baseload' in df.columns:
        df['solar_projection'] = df['lw_germany_solar_gen'] * (solar_forecast.get('baseload', 0) / df['lw_solar_baseload'])
    else:
        df['solar_projection'] = np.nan

    # Final dataframe compilation
    expected_cols = [
       'period', 'is_peak', 'sin_time', 'cos_time', 'czechia_load_prediction',
       'germany_load_prediction', 'wind_baseload', 'wind_peakload',
       'wind_offpeak', 'price_baseload', 'price_peakload', 'price_offpeak',
       'gas_price', 'eua_price', 'lw_price_baseload', 'lw_price_peakload',
       'lw_price_offpeak', 'lw_wind_baseload', 'lw_wind_peakload',
       'lw_wind_offpeak', 'lw_gas_price', 'lw_eua_price', 'lw_price',
       'lw_germany_solar_gen', 'lw_germany_wind_gen', 'lw_germany_load',
       'lw_czechia_load', 'germany_hydro_active_gen_last_week',
       'czechia_hydro_active_gen_last_week',
       'czechia_hydro_reservoir_gen_last_week', 'solar_projection'
    ]

    for col in expected_cols:
        if col not in df.columns:
            df[col] = np.nan
            
    df = df[expected_cols].copy()
    
    # Preprocessing for XGBoost
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    df[numeric_cols] = df[numeric_cols].interpolate(method='linear')
    df[numeric_cols] = df[numeric_cols].bfill().ffill()

    categorical_features = ['is_peak', 'period']
    for col in categorical_features:
        if col in df.columns:
            df[col] = df[col].astype(int).astype('category')

    # Load Model and Predict
    model_path = os.path.join(os.path.dirname(__file__), '..', 'prediction_model.ubj')
    if os.path.exists(model_path):
        try:
            model = xgb.Booster()
            model.load_model(model_path)
            dtest = xgb.DMatrix(df[expected_cols], enable_categorical=True)
            df['prediction'] = model.predict(dtest)
        except Exception as e:
            print(f"Error loading model or predicting: {e}")
            df['prediction'] = np.nan
    else:
        print(f"Warning: Model file not found at {model_path}")
        df['prediction'] = np.nan
        
    predictions_list = df['prediction'].tolist()
    
    db = Database()
    db.save_predictions(target_date_str, predictions_list)

if __name__ == "__main__":
    # Assuming user wants data for tomorrow or a specific day
    # Here choosing typical day-ahead logic or just run with today
    # Because API fetches mix real-time/day-ahead
    
    # Usually pipelines need to be run for the next day 
    tomorrow_str = (datetime.today() + timedelta(days=1)).strftime('%Y-%m-%d')
    print(f"Running prediction pipeline for date: {tomorrow_str}")
    
    create_prediction_pipeline(tomorrow_str)
    
    print("Pipeline finished and data saved to database.")
    
