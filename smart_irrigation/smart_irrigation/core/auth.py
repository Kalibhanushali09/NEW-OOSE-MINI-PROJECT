"""Modules 1 & 2: Farmer registration and login (salted PBKDF2 password hashing)."""
import hashlib
import hmac
import os
import re

from . import db


def _hash(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 120_000).hex()


def validate_registration(name, mobile, password):
    errors = []
    if not name or len(name.strip()) < 2:
        errors.append("Name must be at least 2 characters.")
    if not re.fullmatch(r"[6-9]\d{9}", (mobile or "").strip()):
        errors.append("Enter a valid 10-digit Indian mobile number (starts with 6-9).")
    if not password or len(password) < 6:
        errors.append("Password must be at least 6 characters.")
    return errors


def register(name, mobile, password, role="farmer"):
    """Returns (ok, message)."""
    errors = validate_registration(name, mobile, password)
    if errors:
        return False, " ".join(errors)
    mobile = mobile.strip()
    if db.query("SELECT 1 FROM farmers WHERE mobile=?", (mobile,)):
        return False, "This mobile number is already registered."
    salt = os.urandom(16)
    db.execute(
        "INSERT INTO farmers(name, mobile, password_hash, salt, role) VALUES (?,?,?,?,?)",
        (name.strip(), mobile, _hash(password, salt), salt.hex(), role),
    )
    return True, "Farmer account created. You can log in now."


def login(mobile, password):
    """Returns farmer dict or None."""
    rows = db.query("SELECT * FROM farmers WHERE mobile=?", ((mobile or "").strip(),))
    if not rows:
        return None
    f = rows[0]
    if hmac.compare_digest(f["password_hash"], _hash(password or "", bytes.fromhex(f["salt"]))):
        return {k: f[k] for k in ("farmer_id", "name", "mobile", "role")}
    return None
