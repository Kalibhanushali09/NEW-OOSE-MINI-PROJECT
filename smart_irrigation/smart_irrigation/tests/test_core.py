import os, tempfile, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ["IRRIGATION_DB"] = os.path.join(tempfile.mkdtemp(), "t.db")
from core import auth, db, farms, ml, nutrients, pipeline, recommend

db.init_db()
models = ml.load_models()

def test_auth():
    assert not auth.register("A", "123", "x")[0]
    assert auth.register("Kali", "9876543210", "secret1")[0]
    assert not auth.register("Kali", "9876543210", "secret1")[0]
    assert auth.login("9876543210", "secret1")["name"] == "Kali"
    assert auth.login("9876543210", "wrong") is None

def test_farms_and_pipeline():
    f = auth.login("9876543210", "secret1")
    fid, _ = farms.add_farm(f["farmer_id"], "Plot 1", "Kolhapur", 2.0, "Black (Regur)")
    assert fid
    assert farms.add_farm(f["farmer_id"], "", "x", 0, "Red")[0] is None
    vals = dict(ec=3.2, ph=7.4, moisture=24, nitrogen=280, phosphorus=35, potassium=220, organic_carbon=0.6, crop_age=115)
    assert not pipeline.validate_inputs(vals)
    assert pipeline.validate_inputs({**vals, "ec": -1})
    w = dict(temperature=34, humidity=68, rainfall=8, wind_speed=8, source="manual")
    r = pipeline.run(models, fid, vals, w)
    print(r["soil"], r["irrigation"], r["rec"]["recommendations"])
    assert r["soil"]["salinity"] == "Slightly Saline"
    assert 0 <= r["soil"]["score"] <= 100
    assert not pipeline.history(farmer_id=f["farmer_id"]).empty
    assert farms.delete_farm(fid, f["farmer_id"])

def test_extremes():
    s = ml.predict_soil(models, 14, 9.2, 10, 120, 4, 80, 0.2)
    assert s["salinity"] == "Unsuitable for Sugarcane" and s["score"] < 40
    dry = ml.predict_irrigation(models, 12, 150, 40, 30, 0, 15, 80)
    wet = ml.predict_irrigation(models, 34, 150, 25, 80, 40, 3, 80)
    assert dry["days"] < wet["days"] and dry["need"] == "High"

def test_nutrients():
    n = nutrients.analyze(150, 5, 100, 0.3, 7.0)
    assert n["deficient"] == ["Nitrogen", "Phosphorus", "Potassium"] and n["organic"]
