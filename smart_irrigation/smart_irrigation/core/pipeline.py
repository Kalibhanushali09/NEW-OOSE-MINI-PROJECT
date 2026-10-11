"""Glue: runs soil + nutrient + irrigation + recommendation steps and persists the results."""
import json

import pandas as pd

from . import db, ml, nutrients, recommend

# Validation ranges (reject impossible soil values)
RANGES = {
    "ec": (0.0, 30.0, "EC (dS/m)"),
    "ph": (3.0, 11.0, "Soil pH"),
    "moisture": (0.0, 60.0, "Soil moisture (%)"),
    "nitrogen": (0.0, 1500.0, "Nitrogen (kg/ha)"),
    "phosphorus": (0.0, 200.0, "Phosphorus (kg/ha)"),
    "potassium": (0.0, 1500.0, "Potassium (kg/ha)"),
    "organic_carbon": (0.0, 5.0, "Organic carbon (%)"),
    "crop_age": (0, 450, "Crop age (days)"),
}


def validate_inputs(values: dict):
    errors = []
    for k, (lo, hi, label) in RANGES.items():
        v = values.get(k)
        if v is None:
            errors.append(f"{label} is required.")
        elif not (lo <= v <= hi):
            errors.append(f"{label} must be between {lo} and {hi}.")
    return errors


def run(models, farm_id, soil_in: dict, weather: dict):
    soil = ml.predict_soil(models, soil_in["ec"], soil_in["ph"], soil_in["moisture"], soil_in["nitrogen"],
                           soil_in["phosphorus"], soil_in["potassium"], soil_in["organic_carbon"])
    nut = nutrients.analyze(soil_in["nitrogen"], soil_in["phosphorus"], soil_in["potassium"],
                            soil_in["organic_carbon"], soil_in["ph"])
    irr = ml.predict_irrigation(models, soil_in["moisture"], soil_in["crop_age"], weather["temperature"],
                                weather["humidity"], weather["rainfall"], weather["wind_speed"], soil["score"])
    rec = recommend.build(soil, nut, irr, weather, soil_in)

    test_id = db.execute(
        "INSERT INTO soil_tests(farm_id, ec, ph, moisture, nitrogen, phosphorus, potassium, organic_carbon, crop_age) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (farm_id, soil_in["ec"], soil_in["ph"], soil_in["moisture"], soil_in["nitrogen"], soil_in["phosphorus"],
         soil_in["potassium"], soil_in["organic_carbon"], soil_in["crop_age"]))
    db.execute(
        "INSERT INTO weather(farm_id, temperature, humidity, rainfall, wind_speed, source) VALUES (?,?,?,?,?,?)",
        (farm_id, weather["temperature"], weather["humidity"], weather["rainfall"], weather["wind_speed"],
         weather.get("source", "manual")))
    pid = db.execute(
        "INSERT INTO predictions(test_id, farm_id, soil_health_score, salinity_level, suitability, "
        "nutrient_deficiency, fertilizer_recommendation, next_irrigation_date, irrigation_in_days, "
        "irrigation_duration_hours, irrigation_need, recommendation) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (test_id, farm_id, soil["score"], soil["salinity"], soil["suitability"],
         ", ".join(nut["deficient"]) or "None", "; ".join(nut["fertilizers"]) or "None",
         rec["next_irrigation_date"], irr["days"], irr["duration_hours"], irr["need"],
         json.dumps(rec["recommendations"])))
    return {"prediction_id": pid, "soil": soil, "nutrients": nut, "irrigation": irr, "rec": rec}


def history(farm_id=None, farmer_id=None):
    sql = ("SELECT p.*, f.farm_name, t.ec, t.ph, t.moisture, t.nitrogen, t.phosphorus, t.potassium, "
           "t.organic_carbon, t.crop_age FROM predictions p "
           "JOIN farms f ON f.farm_id=p.farm_id LEFT JOIN soil_tests t ON t.test_id=p.test_id WHERE ")
    params = []
    if farm_id is not None:
        sql += "p.farm_id=?"
        params.append(farm_id)
    else:
        sql += "f.farmer_id=?"
        params.append(farmer_id)
    sql += " ORDER BY p.prediction_id DESC"
    df = pd.DataFrame(db.query(sql, tuple(params)))
    return df
