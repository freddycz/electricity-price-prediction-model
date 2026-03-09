import os
import xml.etree.ElementTree as ET
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import requests
from dotenv import load_dotenv


class EntsoeApi:
    def __init__(self, api_key, date_input):
        self.url = 'https://web-api.tp.entsoe.eu/api' 
        self.headers = {
            "SECURITY_TOKEN": api_key
        }

        if isinstance(date_input, datetime):
            self.target_date = date_input.date()
        else:
            self.target_date = datetime.strptime(date_input, '%Y-%m-%d').date()
            
        self.period_start = self._convert_local_midnight_to_utc(self.target_date)
        self.period_end = self._convert_local_midnight_to_utc(self.target_date + timedelta(days=1))
        
        lw_date = self.target_date - timedelta(days=7)
        self.period_start_lw = self._convert_local_midnight_to_utc(lw_date)
        self.period_end_lw = self._convert_local_midnight_to_utc(lw_date + timedelta(days=1))

    def _convert_local_midnight_to_utc(self, pure_date):
        prague_tz = ZoneInfo("Europe/Prague")
        local_midnight = datetime.combine(pure_date, time.min, tzinfo=prague_tz)
        utc_dt = local_midnight.astimezone(ZoneInfo("UTC"))
        return utc_dt.strftime("%Y%m%d%H%M")

    def _parse_hydro_production_data(self, xml_string, target_types):
        root = ET.fromstring(xml_string)
    
        ns = {'gmd': 'urn:iec62325.351:tc57wg16:451-6:generationloaddocument:3:0'}
        
        raw_production_data = {code: [] for code in target_types.keys()}
        global_max_position = 0
        for timeseries in root.findall('gmd:TimeSeries', ns):
            psr_type_elem = timeseries.find('.//gmd:psrType', ns)
            
            if psr_type_elem is not None and psr_type_elem.text in target_types:
                psr_type_code = psr_type_elem.text
                
                for point in timeseries.findall('.//gmd:Point', ns):
                    pos_elem = point.find('gmd:position', ns)
                    qty_elem = point.find('gmd:quantity', ns)
                    
                    if pos_elem is not None and qty_elem is not None:
                        pos_val = int(pos_elem.text)
                        
                        # Update our global maximum position tracker
                        if pos_val > global_max_position:
                            global_max_position = pos_val
                            
                        raw_production_data[psr_type_code].append({
                            "pos": pos_val,
                            "gen": float(qty_elem.text)
                        })

        processed_data = {}
    
        if global_max_position > 0:
            for code, array in raw_production_data.items():
                if not array:
                    processed_data[code] = [{"pos": i, "gen": 0.0} for i in range(1, global_max_position + 1)]
                    continue
                
                df = pd.DataFrame(array)
                df = df.groupby('pos').sum()
                df = df.reindex(range(1, global_max_position + 1))
                df['gen'] = df['gen'].ffill()
                df['gen'] = df['gen'].bfill().fillna(0)
                
                df.reset_index(inplace=True)
                processed_data[code] = df.to_dict(orient='records')

        df = pd.DataFrame()
        for k in target_types:
            df[target_types[k]] = [r['gen'] for r in processed_data[k]]
            
        return df 

    def _parse_xml_response(self, xml_string, namespace):
        root = ET.fromstring(xml_string)
        ns = {"ns": namespace}
    
        parsed_rows = []
    
        for period_block in root.findall(".//ns:Period", ns):
            
            for point in period_block.findall("ns:Point", ns):
                pos = int(point.find("ns:position", ns).text)
                quantity = float(point.find("ns:quantity", ns).text)
                
                parsed_rows.append({"pos": pos, "load": quantity})
            
        df = pd.DataFrame(parsed_rows)
    
        if df.empty:
            return df

        df = df.set_index("pos").sort_index()

        max_pos = df.index.max()
        full_range = range(1, max_pos + 1)

        df_filled = df.reindex(full_range).ffill()

        df_filled = df_filled.reset_index().rename(columns={"index": "pos"})

        return df_filled

    def get_czechia_hydro_lw(self):
        params = {
            "documentType": "A75",
            "processType": "A16",
            "in_Domain": "10YCZ-CEPS-----N",
            "periodStart": self.period_start_lw,
            "periodEnd": self.period_end_lw
        }

        target_types = {
            "B02": "temp", #coal to make sure we have correct number of rows
            "B10": "czechia_hydro_active_gen_last_week",
            "B12": "czechia_hydro_reservoir_gen_last_week"
        }

        try:
            response = requests.get(self.url, params=params, headers=self.headers)
            data = self._parse_hydro_production_data(response.text, target_types)
            data = data.drop(columns=['temp'])

            return data

        except Exception as e:
            print(f"failed to fetch czechia hydro: {e}")
            return None

    def get_germany_production_lw(self):
        params = {
            "documentType": "A75",
            "processType": "A16",
            "in_Domain": "10Y1001A1001A83F",
            "periodStart": self.period_start_lw,
            "periodEnd": self.period_end_lw,
        }

        target_types = {
            "B02": "temp", #coal to make sure we have correct number of rows
            "B10": "germany_hydro_active_gen_last_week",
            "B16": "lw_germany_solar_gen",
            "B18": "germany_wind_offshore_gen_last_week",
            "B19": "germany_wind_onshore_gen_last_week",
        }
        try:
            response = requests.get(self.url, params=params, headers=self.headers)
            data = self._parse_hydro_production_data(response.text, target_types)

            data["lw_germany_wind_gen"] = data["germany_wind_offshore_gen_last_week"] + data["germany_wind_onshore_gen_last_week"]

            data["lw_solar_baseload"] = data["lw_germany_solar_gen"].mean()
            data["lw_wind_baseload"] = data["lw_germany_wind_gen"].mean()

            periods = len(data)
            #peak load periods
            p_start = 32 
            p_end = 80

            if periods == 92:
                p_start -= 4
                p_end -= 4
            elif periods == 100:
                p_start += 4
                p_end += 4

            peak_df = data.iloc[p_start:p_end]
            data["lw_wind_peakload"] = peak_df["lw_germany_wind_gen"].mean()
            
            offpeak_df = data.drop(peak_df.index)
            data["lw_wind_offpeak"] = offpeak_df["lw_germany_wind_gen"].mean()

            data = data.drop(columns=['temp', 'germany_wind_offshore_gen_last_week', 'germany_wind_onshore_gen_last_week'])
            return data
        except Exception as e:
            print(f"failed to fetch germany production lw: {e}")
            return None



    def _align_historical_to_prediction(self, df_hist, df_pred):
        if len(df_hist) == len(df_pred):
            return pd.merge(df_pred, df_hist, on="pos", how="left")

        len_h = len(df_hist)
        len_p = len(df_pred)

        df_map = df_pred[['pos']].copy()
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
            right_on='pos', 
            how='left',
            suffixes=('', '_hist')
        )

        cols_to_drop = ['target_pos', 'pos_hist']
        if 'pos_hist' not in df_aligned.columns and 'pos_y' in df_aligned.columns:
            cols_to_drop = ['target_pos', 'pos_y']
            
        df_aligned = df_aligned.drop(columns=cols_to_drop, errors='ignore')
        
        return pd.merge(df_aligned, df_pred, on="pos", how="left")

    def get_germany_load(self):
        params_lw = {
            "documentType": "A65",
            "processType": "A16",
            "outBiddingZone_Domain": "10Y1001A1001A83F",
            "periodStart": self.period_start_lw,
            "periodEnd": self.period_end_lw
        }

        params_pred = {
            "documentType": "A65",
            "processType": "A01",
            "outBiddingZone_Domain": "10Y1001A1001A83F",
            "periodStart": self.period_start,
            "periodEnd": self.period_end
        }

        try:
            res_lw = requests.get(self.url, params=params_lw, headers=self.headers)
            df_lw = self._parse_xml_response(res_lw.text, "urn:iec62325.351:tc57wg16:451-6:generationloaddocument:3:0")
            df_lw = df_lw.rename(columns={"load": "lw_germany_load"})
            
            res_pred = requests.get(self.url, params=params_pred, headers=self.headers)
            df_pred = self._parse_xml_response(res_pred.text, "urn:iec62325.351:tc57wg16:451-6:generationloaddocument:3:0")
            df_pred = df_pred.rename(columns={"load": "germany_load_prediction"})

            # Merge correctly considering DST
            df = self._align_historical_to_prediction(df_lw, df_pred)
            return df

        except Exception as e:
            print(f"failed to fetch germany load: {e}")
            return None

    def get_czechia_load(self):
        params_lw = {
            "documentType": "A65",
            "processType": "A16",
            "outBiddingZone_Domain": "10YCZ-CEPS-----N",
            "periodStart": self.period_start_lw,
            "periodEnd": self.period_end_lw
        }

        params_pred = {
            "documentType": "A65",
            "processType": "A01",
            "outBiddingZone_Domain": "10YCZ-CEPS-----N",
            "periodStart": self.period_start,
            "periodEnd": self.period_end
        }

        try:
            res_lw = requests.get(self.url, params=params_lw, headers=self.headers)
            df_lw = self._parse_xml_response(res_lw.text, "urn:iec62325.351:tc57wg16:451-6:generationloaddocument:3:0")
            df_lw = df_lw.rename(columns={"load": "lw_czechia_load"})
            
            res_pred = requests.get(self.url, params=params_pred, headers=self.headers)
            df_pred = self._parse_xml_response(res_pred.text, "urn:iec62325.351:tc57wg16:451-6:generationloaddocument:3:0")
            df_pred = df_pred.rename(columns={"load": "czechia_load_prediction"})

            # Merge correctly considering DST
            df = self._align_historical_to_prediction(df_lw, df_pred)
            return df

        except Exception as e:
            print(f"failed to fetch czechia load: {e}")
            return None