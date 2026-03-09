from datetime import datetime, timedelta

import pandas as pd
import requests


class OteFetcher:
    def __init__(self, date_input):
        if isinstance(date_input, datetime):
            self.target_date = date_input
        else:
            self.target_date = datetime.strptime(date_input, '%Y-%m-%d')
            
        self.date_str = self.target_date.strftime('%Y-%m-%d')
        
        self.url_ele = "https://www.ote-cr.cz/cs/kratkodobe-trhy/elektrina/denni-trh/@@chart-data"
        self.url_gas = "https://www.ote-cr.cz/cs/kratkodobe-trhy/plyn/vnitrodenni-trh/@@chart-data"

    def _fetch_json(self, url, date_str):
        try:
            params = {'report_date': date_str}
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Chyba při stahování ({url}): {e}")
            return None

    def get_electricity_prices(self):
        json_data = self._fetch_json(self.url_ele, date_str=self.date_str)
        if not json_data:
            return None

        try:
            points = json_data['data']['dataLine'][1]['point']
            
            df = pd.DataFrame(points)
            df['y'] = df['y'].astype(float)

            periods = len(df)
            #peak load periods
            p_start = 32 
            p_end = 80

            if periods == 92:
                p_start -= 4
                p_end -= 4
            elif periods == 100:
                p_start += 4
                p_end += 4

            baseload = df['y'].mean()
    
            peak_df = df.iloc[p_start:p_end]
            peakload = peak_df['y'].mean()
    
            offpeak_df = df.drop(peak_df.index)
            offpeak = offpeak_df['y'].mean()
            
            return {
                'baseload': float(baseload),
                'peakload': float(peakload),
                'offpeak':float(offpeak), 
                'prices': df['y'].tolist()
            } 
            
        except Exception as e:
            print(f"Failed parsing electricity prices: {e}")
            return None


    def get_lw_electricity_prices(self):
        date_week_ago = self.target_date - timedelta(days=7)
        str_week_ago = date_week_ago.strftime('%Y-%m-%d')

        json_data = self._fetch_json(self.url_ele, str_week_ago)
        if not json_data:
            return None

        try:
            points = json_data['data']['dataLine'][1]['point']
            
            df = pd.DataFrame(points)
            df['y'] = df['y'].astype(float)

            periods = len(df)
            #peak load periods
            p_start = 32 
            p_end = 80

            if periods == 92:
                p_start -= 4
                p_end -= 4
            elif periods == 100:
                p_start += 4
                p_end += 4

            baseload = df['y'].mean()
    
            peak_df = df.iloc[p_start:p_end]
            peakload = peak_df['y'].mean()
    
            offpeak_df = df.drop(peak_df.index)
            offpeak = offpeak_df['y'].mean()
            
            return {
                'baseload': float(baseload),
                'peakload': float(peakload),
                'offpeak':float(offpeak), 
                'prices': df['y'].tolist()
            } 
            
        except Exception as e:
            print(f"Failed parsing electricity prices: {e}")
            return None

    def _find_gas_price_in_json(self, json_data, target_date_str):
        if not json_data: return None
        try:
            for line in json_data['data']['dataLine']:
                title = line.get('title', '')

                if "Cena" in title and "Minim" not in title and "Maxim" not in title:
                    for point in line['point']:
                        if point['x'].startswith(target_date_str):
                            return float(point['y'])
            return None
        except Exception:
            return None

    def get_gas_prices(self):
        json_now = self._fetch_json(self.url_gas, self.date_str)
        price_now = self._find_gas_price_in_json(json_now, self.date_str)

        date_week_ago = self.target_date - timedelta(days=7)
        str_week_ago = date_week_ago.strftime('%Y-%m-%d')
        
        price_week_ago = None
        if json_now:
            price_week_ago = self._find_gas_price_in_json(json_now, str_week_ago)
        
        if price_week_ago is None:
            json_history = self._fetch_json(self.url_gas, str_week_ago)
            price_week_ago = self._find_gas_price_in_json(json_history, str_week_ago)

        result = {
            'price': price_now,
            'lw_price': price_week_ago,
        }
        
        return result 
