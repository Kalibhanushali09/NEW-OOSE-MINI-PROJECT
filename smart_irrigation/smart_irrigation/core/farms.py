"""Module 3: Farm registration and management."""
from . import db

SOIL_TYPES = ["Black (Regur)", "Red", "Alluvial", "Laterite", "Sandy loam", "Clay loam"]


def validate_farm(name, village, area):
    errors = []
    if not name or not name.strip():
        errors.append("Farm name is required.")
    if not village or not village.strip():
        errors.append("Village is required.")
    if area is None or area <= 0:
        errors.append("Area must be greater than zero.")
    return errors


def add_farm(farmer_id, name, village, area, soil_type, lat=None, lon=None, crop="Sugarcane"):
    errs = validate_farm(name, village, area)
    if errs:
        return None, " ".join(errs)
    fid = db.execute(
        "INSERT INTO farms(farmer_id, farm_name, village, area, soil_type, latitude, longitude, crop_info) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (farmer_id, name.strip(), village.strip(), area, soil_type, lat, lon, crop),
    )
    return fid, "Farm added successfully."


def update_farm(farm_id, farmer_id, name, village, area, soil_type, lat=None, lon=None):
    errs = validate_farm(name, village, area)
    if errs:
        return False, " ".join(errs)
    db.execute(
        "UPDATE farms SET farm_name=?, village=?, area=?, soil_type=?, latitude=?, longitude=? "
        "WHERE farm_id=? AND farmer_id=?",
        (name.strip(), village.strip(), area, soil_type, lat, lon, farm_id, farmer_id),
    )
    return True, "Farm updated."


def delete_farm(farm_id, farmer_id):
    own = db.query("SELECT 1 FROM farms WHERE farm_id=? AND farmer_id=?", (farm_id, farmer_id))
    if not own:
        return False
    db.execute("DELETE FROM predictions WHERE farm_id=?", (farm_id,))
    db.execute("DELETE FROM weather WHERE farm_id=?", (farm_id,))
    db.execute("DELETE FROM soil_tests WHERE farm_id=?", (farm_id,))
    db.execute("DELETE FROM farms WHERE farm_id=?", (farm_id,))
    return True


def list_farms(farmer_id):
    return db.query("SELECT * FROM farms WHERE farmer_id=? ORDER BY farm_id", (farmer_id,))
