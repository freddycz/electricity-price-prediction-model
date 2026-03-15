# electricity-price-prediction-model

Prediktivní systém pro krátkodobý trh s elektřinou, který využívá algoritmy strojového učení k předpovědi cen v 15minutových intervalech na českém denním trhu (Day-Ahead).

Cílem projektu bylo otestovat limity **bezplatných veřejných dat** a vytvořit robustní end-to-end systém – od automatizovaného sběru dat až po interaktivní vizualizaci.

## Klíčové vlastnosti

- **Granularita 15 min:** Model předpovídá všech 96 period nadcházejícího obchodního dne.
- **Automatizovaná Pipeline:** \* **11:30 CET:** Sběr dat (EEX, ENTSO-E, Spot Renewables), feature engineering a výpočet predikce před uzavřením burzy.
  - **13:15 CET:** Zpětné stažení reálných cen a automatické vyhodnocení přesnosti (MAE, Bias).
- **ML Engine:** XGBoost regrese dosahující průměrné chyby **MAE ~13 EUR/MWh** (překonává baseline lineární regresi s MAE ~16 EUR/MWh).
- **Interaktivní Dashboard:** Moderní webové rozhraní pro sledování predikcí vs. reality.

## Tech Stack

- **Backend:** Python (Pandas, Scikit-learn, XGBoost)
- **Databáze:** SQL (perzistence predikcí a reálných cen)
- **Web UI:** Flask, HTMX (dynamické načítání bez JS frameworků), Tailwind CSS, Google Charts
- **Automatizace:** Cron Jobs

## Datové zdroje

Systém integruje data z několika klíčových evropských platforem:

- **OTE / ENTSO-E / SMARD:** Historické ceny a fyzikální fundamenty sítě.
- **EEX:** Futures kontrakty (Baseload/Peakload) a ceny emisních povolenek (EUA).
- **Spot Renewables:** Předpovědi výroby solárních a větrných elektráren.

_Tento projekt vznikl jako praktické ověření možností strojového učení v moderní energetice bez použití placených datových rozhraní._
