import os
import xml.etree.ElementTree as ET
from datetime import datetime, time
from zoneinfo import ZoneInfo

import pandas as pd
import requests
from dotenv import load_dotenv


class EntsoeApi:
    def __init__(self, api_key):
        self.url = 'https://web-api.tp.entsoe.eu/api' 
        self.headers = {
            "SECURITY_TOKEN": api_key
        }

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
        full_range = range(max_pos)

        df_filled = df.reindex(full_range).ffill()

        df_filled = df_filled.reset_index().rename(columns={"index": "pos"})

        return df_filled

    def get_czechia_hydro_lw(self):
        params = {
            "documentType": "A75",
            "processType": "A16",
            "in_Domain": "10YCZ-CEPS-----N",
            "periodStart": "202308152200",
            "periodEnd": "202308162200"
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

    def get_germany_hydro_lw(self):
        params = {
            "documentType": "A75",
            "processType": "A16",
            "in_Domain": "10Y1001A1001A83F",
            "periodStart": "202308152200",
            "periodEnd": "202308162200",
        }

        target_types = {
            "B02": "temp", #coal to make sure we have correct number of rows
            "B10": "germany_hydro_active_gen_last_week",
        }
        try:
            response = requests.get(self.url, params=params, headers=self.headers)
            data = self._parse_hydro_production_data(response.text, target_types)
            data = data.drop(columns=['temp'])
            return data
        except Exception as e:
            print(f"failed to fetch germany hydro: {e}")
            return None




        

load_dotenv()
api_key = os.getenv("ENTSOE_API_KEY")

e = EntsoeApi(api_key=api_key)
print(e.get_czechia_hydro_lw())
print(e.get_germany_hydro_lw())