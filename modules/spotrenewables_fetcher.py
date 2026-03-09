import random
from datetime import datetime, timedelta

import requests


class SpotRenewables:
    def __init__(self, target_date, country="Germany"):
        self.target_date = target_date
        self.country = country
        
        # Date Math: Payload is always Target Date - 2
        self.target_dt = datetime.strptime(target_date, "%Y-%m-%d")
        self.payload_dt = self.target_dt - timedelta(days=2)
        
        # Formats needed for different endpoints
        self.p_date_str = self.payload_dt.strftime("%Y-%m-%d")
        self.p_year = self.payload_dt.strftime("%Y")
        self.p_month_raw = str(int(self.payload_dt.strftime("%m")))
        self.p_day_raw = str(int(self.payload_dt.strftime("%d")))
        self.p_month_pad = self.payload_dt.strftime("%m")
        self.p_day_pad = self.payload_dt.strftime("%d")

        self.session = requests.Session()
        self.ajax_base = 'https://www.spotrenewables.com/ajax/'
        self.headers = {
            'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36',
            'x-requested-with': 'XMLHttpRequest',
            'referer': 'https://www.spotrenewables.com/index.php?page=freeresources',
            'origin': 'https://www.spotrenewables.com',
            'content-type': 'application/x-www-form-urlencoded; charset=UTF-8'
        }

    def _warm_session(self, solar=True, wind=False):
        """Simulating browser behavior to get authorize cookie"""
        # Step 0: Initial Page Load
        self.session.get('https://www.spotrenewables.com/index.php?page=freeresources', headers=self.headers)
        
        # Steps 1-3: General session initialization
        self.session.post(f"{self.ajax_base}findregions.php", headers=self.headers, data={'cachekiller': random.random()})
        self.session.post(f"{self.ajax_base}findsubregions.php", headers=self.headers, data={'selectedlandindex': '10000', 'cachekiller': random.random()})
        self.session.post(f"{self.ajax_base}findmysqltables.php", headers=self.headers, data={'selectedlandindex': '10000', 'typeidentifier': 'freeresources', 'cachekiller': random.random()})

        # Step 4: Find Runs (The critical trigger)
        res_runs = self.session.post(f"{self.ajax_base}findruns.php", headers=self.headers, data={
            'jahr': self.p_year,
            'monat': self.p_month_raw,
            'tag': self.p_day_raw,
            'selectedlandindex': '10000',
            'selectedland': self.country,
            'selectedfilter': 'none',
            'windboxchecked': 'true' if wind else 'false',
            'solarboxchecked': 'true' if solar else 'false',
            'cachekiller': random.random()
        })
        
        # Extract latest laufindex
        laufindex = '6' 
        if ';' in res_runs.text:
            runs = res_runs.text.split(';')[-1].split('|')
            if runs: laufindex = runs[0]
        
        return laufindex

    def _fetch(self, solar=True, wind=False):
        """Private shared logic for the final POST."""
        laufindex = self._warm_session(solar=solar, wind=wind)

        payload = {
            'laufdatum': self.p_date_str,
            'jahr': self.p_year,
            'monat': self.p_month_pad,
            'tag': self.p_day_pad,
            'laufindex': laufindex,
            'selecteddelta': '7',
            'windboxchecked': 'true' if wind else 'false',
            'solarboxchecked': 'true' if solar else 'false',
            'forecastboxchecked': 'true',
            'meterboxchecked': 'false',
            'selectedlandindex': '10000',
            'selectedland': self.country,
            'selectedfilter': 'none',
            'selectedtimezone': 'Europe/Berlin',
            'cachekiller': random.random()
        }

        response = self.session.post(f"{self.ajax_base}updatetabelle.php", headers=self.headers, data=payload)

        if response.status_code == 200:
            data = response.json()
            if not data: return None
            
            f = data.get("summary", {}).get("forecast", {})
            target_key = f"{self.target_date} 00:00:00"
            peak_key = f"{self.target_date} 12:00:00"

            peakload = f.get(peak_key, {}).get("average_production")
            offpeak = f.get(target_key, {}).get("average_production")

            return {
                "baseload": (peakload + offpeak) / 2,
                "offpeak": offpeak,
                "peakload": peakload,
            }
        return None

    def get_solar_forecast(self):
        return self._fetch(solar=True, wind=False)

    def get_wind_forecast(self):
        return self._fetch(solar=False, wind=True)
