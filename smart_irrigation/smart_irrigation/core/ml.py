"""Modules 4 & 6: Machine-learning models.

Model 1 (Soil)        RandomForestClassifier -> salinity class
                      RandomForestRegressor  -> soil health score (0-100)
Model 2 (Irrigation)  GaussianNB             -> irrigation need (Low / Medium / High)   [as in the SPMP]
                      RandomForestRegressor  -> days until next irrigation
                      RandomForestRegressor  -> irrigation duration (hours)

NOTE ON DATA: no real labelled dataset ships with this project, so models are trained on a
synthetic dataset generated from FAO-56 style water-balance and standard salinity classes
(see generate_*_data). To use a real dataset (e.g. the Kaggle irrigation CSV), replace the
generate_* functions with a pandas.read_csv(...) that returns the same columns and re-run
`python -m core.ml` to retrain.
"""
import os

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import accuracy_score, mean_absolute_error
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import GaussianNB

MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")
SOIL_FEATURES = ["ec", "ph", "moisture", "nitrogen", "phosphorus", "potassium", "organic_carbon"]
IRR_FEATURES = ["moisture", "crop_age", "temperature", "humidity", "rainfall", "wind_speed", "soil_health_score"]
SALINITY_CLASSES = ["Healthy", "Slightly Saline", "Moderately Saline", "Highly Saline", "Unsuitable for Sugarcane"]
NEED_CLASSES = ["Low", "Medium", "High"]

# ---------------------------------------------------------------- ground-truth rules (used to label synthetic data)

FIELD_CAPACITY = 35.0   # % volumetric moisture
TRIGGER_MOISTURE = 18.0  # irrigate when moisture drops to this level


def salinity_label(ec):
    """Standard EC (dS/m) classes; sugarcane tolerance threshold is ~1.7 dS/m."""
    if ec < 2:
        return 0
    if ec < 4:
        return 1
    if ec < 8:
        return 2
    if ec < 12:
        return 3
    return 4


def health_score_rule(ec, ph, moisture, n, p, k, oc):
    score = 100.0
    score -= min(45, max(0, ec - 1.0) * 6.0)                      # salinity penalty
    score -= min(20, abs(ph - 7.0) * 8.0) if abs(ph - 7.0) > 0.5 else 0
    score -= 8 if n < 280 else 0
    score -= 6 if p < 10 else 0
    score -= 6 if k < 120 else 0
    score -= 8 if oc < 0.5 else (3 if oc < 0.75 else 0)
    score -= 5 if moisture < 12 else 0
    return float(np.clip(score, 0, 100))


def kc(age):
    """Sugarcane crop coefficient by age in days."""
    age = np.asarray(age, dtype=float)
    return np.where(age < 35, 0.45,
           np.where(age < 120, 0.45 + (age - 35) / 85 * 0.8,
           np.where(age < 270, 1.25, 0.85)))


def depletion_per_day(temp, humidity, wind, age, health):
    """% volumetric moisture lost per day (crop ET proxy)."""
    et0 = 1.5 + 0.18 * np.maximum(temp - 10, 0) + 0.035 * (100 - humidity) / 10 * 10 / 10 + 0.12 * wind
    stress = 1.0 + (100 - health) / 400.0  # degraded soil dries / stresses faster
    return np.clip(et0 * kc(age) * 0.55 * stress, 0.2, 6.0)


# ---------------------------------------------------------------- synthetic data

def generate_soil_data(n=6000, seed=42):
    r = np.random.default_rng(seed)
    ec = np.concatenate([r.uniform(0.1, 4, n // 2), r.uniform(0.1, 16, n - n // 2)])
    df = pd.DataFrame({
        "ec": ec,
        "ph": np.clip(r.normal(7.3, 0.9, n), 4.5, 10),
        "moisture": r.uniform(5, 40, n),
        "nitrogen": r.uniform(100, 700, n),
        "phosphorus": r.uniform(2, 45, n),
        "potassium": r.uniform(50, 400, n),
        "organic_carbon": r.uniform(0.15, 1.2, n),
    })
    df["salinity"] = df["ec"].map(salinity_label)
    df["score"] = [health_score_rule(*row) for row in df[SOIL_FEATURES].itertuples(index=False)]
    df["score"] = np.clip(df["score"] + r.normal(0, 1.5, n), 0, 100)
    return df


def generate_irrigation_data(n=8000, seed=7):
    r = np.random.default_rng(seed)
    df = pd.DataFrame({
        "moisture": r.uniform(8, 40, n),
        "crop_age": r.integers(1, 360, n),
        "temperature": r.uniform(14, 44, n),
        "humidity": r.uniform(25, 95, n),
        "rainfall": np.where(r.random(n) < 0.55, 0, r.exponential(12, n)).clip(0, 120),  # 3-day forecast, mm
        "wind_speed": r.uniform(0, 25, n),
        "soil_health_score": r.uniform(20, 100, n),
    })
    dep = depletion_per_day(df.temperature, df.humidity, df.wind_speed, df.crop_age, df.soil_health_score)
    rain_gain = df.rainfall * 0.25  # effective % moisture gain from forecast rain
    effective = df.moisture + rain_gain
    days = ((effective - TRIGGER_MOISTURE) / dep).clip(0, 14)
    df["days"] = (days + r.normal(0, 0.15, n)).clip(0, 14)
    deficit = (FIELD_CAPACITY - np.minimum(effective, FIELD_CAPACITY)).clip(0, None)
    leach = np.where(df.soil_health_score < 60, 1.15, 1.0)  # extra water to leach salts
    df["duration"] = (0.6 + deficit * 0.18 * leach + r.normal(0, 0.1, n)).clip(0.5, 6)
    df["need"] = pd.cut(df["days"], bins=[-1, 1, 3.5, 99], labels=[2, 1, 0]).astype(int)  # 2=High (soon)
    df["need"] = df["need"].map({0: "Low", 1: "Medium", 2: "High"})
    return df


# ---------------------------------------------------------------- training / loading

def train_all(save=True):
    soil = generate_soil_data()
    Xs = soil[SOIL_FEATURES]
    Xtr, Xte, ytr, yte, str_, ste = train_test_split(Xs, soil["salinity"], soil["score"], test_size=0.2, random_state=1)
    sal = RandomForestClassifier(n_estimators=150, random_state=1, n_jobs=-1).fit(Xtr, ytr)
    score = RandomForestRegressor(n_estimators=150, random_state=1, n_jobs=-1).fit(Xtr, str_)

    irr = generate_irrigation_data()
    Xi = irr[IRR_FEATURES]
    Xtr2, Xte2, ntr, nte, dtr, dte, utr, ute = train_test_split(
        Xi, irr["need"], irr["days"], irr["duration"], test_size=0.2, random_state=1)
    need = GaussianNB(var_smoothing=1e-6).fit(Xtr2, ntr)  # var_smoothing guards zero-frequency/variance errors
    days = RandomForestRegressor(n_estimators=150, random_state=1, n_jobs=-1).fit(Xtr2, dtr)
    dur = RandomForestRegressor(n_estimators=150, random_state=1, n_jobs=-1).fit(Xtr2, utr)

    metrics = {
        "salinity_accuracy": round(accuracy_score(yte, sal.predict(Xte)), 3),
        "score_mae": round(mean_absolute_error(ste, score.predict(Xte)), 2),
        "need_accuracy": round(accuracy_score(nte, need.predict(Xte2)), 3),
        "days_mae": round(mean_absolute_error(dte, days.predict(Xte2)), 2),
        "duration_mae": round(mean_absolute_error(ute, dur.predict(Xte2)), 2),
        "train_rows_soil": len(Xtr), "train_rows_irrigation": len(Xtr2),
    }
    bundle = {"salinity": sal, "score": score, "need": need, "days": days, "duration": dur, "metrics": metrics}
    if save:
        os.makedirs(MODEL_DIR, exist_ok=True)
        joblib.dump(bundle, os.path.join(MODEL_DIR, "models.pkl"), compress=3)
    return bundle


def load_models():
    path = os.path.join(MODEL_DIR, "models.pkl")
    if os.path.exists(path):
        try:
            return joblib.load(path)
        except Exception:
            pass  # version mismatch -> retrain below
    return train_all(save=True)


# ---------------------------------------------------------------- prediction API

def predict_soil(models, ec, ph, moisture, n, p, k, oc):
    X = pd.DataFrame([[ec, ph, moisture, n, p, k, oc]], columns=SOIL_FEATURES)
    level = SALINITY_CLASSES[int(models["salinity"].predict(X)[0])]
    score = float(np.clip(models["score"].predict(X)[0], 0, 100))
    if level == "Unsuitable for Sugarcane":
        suit = "Unsuitable for sugarcane - reclaim soil first"
    elif level == "Highly Saline":
        suit = "Poor - only salt-tolerant varieties after reclamation"
    elif level == "Moderately Saline":
        suit = "Marginal - yield loss likely without management"
    else:
        suit = "Suitable for sugarcane"
    return {"score": round(score, 1), "salinity": level, "suitability": suit}


def predict_irrigation(models, moisture, crop_age, temperature, humidity, rainfall, wind_speed, soil_score):
    X = pd.DataFrame([[moisture, crop_age, temperature, humidity, rainfall, wind_speed, soil_score]],
                     columns=IRR_FEATURES)
    need = str(models["need"].predict(X)[0])
    proba = {str(c): float(round(v, 3)) for c, v in zip(models["need"].classes_, models["need"].predict_proba(X)[0])}
    days = float(np.clip(models["days"].predict(X)[0], 0, 14))
    dur = float(np.clip(models["duration"].predict(X)[0], 0.5, 6))
    return {"need": need, "need_proba": proba, "days": int(round(days)), "duration_hours": round(dur * 2) / 2}


if __name__ == "__main__":
    b = train_all()
    print(b["metrics"])
