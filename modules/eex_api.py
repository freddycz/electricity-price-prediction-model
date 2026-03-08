from datetime import datetime, timedelta

import requests


class EexFetcher: 
    def __init__(self, date: str):
        if isinstance(date, str):
            self.date = datetime.strptime(date, '%Y-%m-%d').date()
        else:
            self.date = date

        self.headers = {
            'accept': 'application/json, text/javascript, */*; q=0.01',
            'accept-language': 'cs-CZ,cs;q=0.9,en;q=0.8',
            'origin': 'https://www.eex.com',
            'priority': 'u=1, i',
            'referer': 'https://www.eex.com/',
            'sec-ch-ua': '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Linux"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'cross-site',
            'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36'
        }


    def get_price_loads(self):
        url = 'https://api.eex-group.com/pub/market-data/price-ticker'

        day = self.date.strftime('%d')
        maturity_val = self.date.strftime('%Y%m')

        params = {
            'shortCode': f'FX{day}',
            'area': 'CZ',
            'product': 'Base',
            'commodity': 'POWER',
            'pricing': 'F',
            'maturity': maturity_val
        }
        
        try:
            result = {}
            response = requests.get(url, params=params, headers=self.headers)
            
            response.raise_for_status()
            
            body = response.json()
            result["baseload"] = body["data"][0][1]

            params["product"] = "Peak"
            params["shortCode"] = f"PX{day}"
            response = requests.get(url, params=params, headers=self.headers)
            
            response.raise_for_status()
            
            body = response.json()
            result["peakload"] = body["data"][0][1]

            result["offpeak"] = 2 * result["baseload"] - result["peakload"]

            return result
        except requests.exceptions.HTTPError as err:
            raise Exception(f"HTTP error occurred: {err}")
        except Exception as err:
            raise Exception(f"An error occurred: {err}")

    def get_eua_prices(self):
        url = 'https://api.eex-group.com/pub/market-data/price-ticker'
        url_lw = 'https://api.eex-group.com/pub/market-data/table-data'

        
        year = self.date.strftime('%Y')

        target_date = self.date - timedelta(days=7)
        
        if target_date.weekday() == 5:
            target_date -= timedelta(days=1)
        elif target_date.weekday() == 6:
            target_date -= timedelta(days=2)
            
        target_date_str = target_date.strftime('%Y-%m-%d')


        params = {
            'shortCode': 'FEUA',
            'area': 'EU',
            'product': 'EUA',
            'commodity': 'ENVIRONMENTALS',
            'pricing': 'F',
            'maturity': f'{year}12' 
        }

        params_lw = {
            'shortCode': 'FEUA',
            'area': 'EU',
            'product': 'EUA',
            'commodity': 'ENVIRONMENTALS',
            'pricing': 'F',
            'maturity': f'{year}12',
            'startDate': target_date_str,
            'endDate': target_date_str,
            'maturityType': 'Month',
            'isRolling': 'true'
        }
        
        try:
            result = {}
            response = requests.get(url, params=params, headers=self.headers)
            response.raise_for_status()
            
            body = response.json()
            result["price"] = body["data"][0][1]

            response = requests.get(url_lw, params=params_lw, headers=self.headers)
            response.raise_for_status()
            
            body = response.json()
            result["lw_price"] = body["data"][0][-1]

            return result
        except requests.exceptions.HTTPError as err:
            raise Exception(f"HTTP error occurred: {err}")
        except Exception as err:
            raise Exception(f"An error occurred: {err}")
