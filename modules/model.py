import numpy as np
import pandas as pd
import xgboost as xgb


def train_model():
    df = pd.read_csv("../dataset/2023-2025_dataset.csv", sep=";")
    df["solar_projection"] = df["lw_germany_solar_gen"] * (df["solar_baseload"] / df["lw_solar_baseload"])

    numeric_cols = df.select_dtypes(include=[np.number]).columns
    df[numeric_cols] = df[numeric_cols].interpolate(method='linear')

    df[numeric_cols] = df[numeric_cols].bfill().ffill()

    categorical_features = ['is_peak', 'period']
    for col in categorical_features:
        if col in df.columns:
            df[col] = df[col].astype(int).astype('category')

    features_to_remove = [
        'price',
        'germany_nuclear_gen_last_week', 
        'germany_lignite_gen_last_week',
        'germany_other_gen_last_week',
        'czechia_other_gen_last_week',
        'czechia_hard_coal_gen_last_week',
        'czechia_nuclear_gen_last_week',
        'germany_hydro_passive_gen_last_week',
        'czechia_hydro_passive_gen_last_week',
        'czechia_biomass_gen_last_week',
        'germany_biomass_gen_last_week',
        'germany_hard_coal_gen_last_week',
        'czechia_fossil_gas_gen_last_week',
        'germany_fossil_gas_gen_last_week',
        'czechia_lignite_gen_last_week',
        'solar_baseload', 'solar_peakload', 'solar_offpeak', 'lw_solar_offpeak', 'lw_solar_baseload', 'lw_solar_peakload',
    ]
    
    X = df.drop(columns=features_to_remove)
    y = df['price']

    params = {
        'objective': 'reg:absoluteerror',
        'learning_rate': 0.05,     # Slow and steady learning
        'max_depth': 6,            # Enough to catch complex DE/CZ interactions
        'subsample': 0.9,          # Use 90% of data to prevent overfitting
        'colsample_bytree': 0.8,   # Use 80% of features per tree
        'min_child_weight': 50,
        'reg_lambda': 10,
        'eval_metric': 'mae'       # Mean Absolute Error is best for prices
    }

    d = xgb.DMatrix(X, label=y, enable_categorical=True)

    model = xgb.train(
        params,
        d,
        num_boost_round=10000,
    )

    model.save_model("../prediction_model.ubj")
    print("Model saved!")

train_model()
