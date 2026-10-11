"""Module 5: Rule-based nutrient deficiency analysis.

Thresholds follow commonly used Indian soil-test ratings for sugarcane (kg/ha for N, P, K):
  Available N   : < 280 low, 280-560 medium, > 560 high
  Available P   : < 10 low, 10-25 medium, > 25 high   (Olsen P)
  Available K   : < 120 low, 120-280 medium, > 280 high
  Organic C (%) : < 0.5 low, 0.5-0.75 medium, > 0.75 high
  pH            : ideal 6.5-7.5 for sugarcane
These are advisory defaults and can be tuned in THRESHOLDS.
"""

THRESHOLDS = {
    "nitrogen": {"low": 280, "high": 560, "unit": "kg/ha"},
    "phosphorus": {"low": 10, "high": 25, "unit": "kg/ha"},
    "potassium": {"low": 120, "high": 280, "unit": "kg/ha"},
    "organic_carbon": {"low": 0.5, "high": 0.75, "unit": "%"},
}

FERTILIZER = {
    "nitrogen": "Urea (apply in 2-3 split doses)",
    "phosphorus": "DAP / Single Super Phosphate",
    "potassium": "Muriate of Potash (MOP)",
}


def rate(value, key):
    t = THRESHOLDS[key]
    if value < t["low"]:
        return "Low"
    if value > t["high"]:
        return "High"
    return "Medium"


def analyze(nitrogen, phosphorus, potassium, organic_carbon, ph):
    status = {
        "Nitrogen": rate(nitrogen, "nitrogen"),
        "Phosphorus": rate(phosphorus, "phosphorus"),
        "Potassium": rate(potassium, "potassium"),
        "Organic Carbon": rate(organic_carbon, "organic_carbon"),
    }
    deficient = [k for k in ("Nitrogen", "Phosphorus", "Potassium") if status[k] == "Low"]
    fertilizers = [FERTILIZER[k.lower()] for k in deficient]
    organic = []
    suggestions = []

    if status["Organic Carbon"] == "Low":
        organic.append("Add compost / farmyard manure (8-10 t/ha) or press mud")
    if ph < 6.0:
        suggestions.append("Soil is acidic: apply agricultural lime.")
    elif ph > 8.5:
        suggestions.append("Soil is strongly alkaline: apply gypsum and organic matter.")
    elif ph > 7.5:
        suggestions.append("Soil is mildly alkaline: prefer ammonium-based fertilizers and add organic matter.")
    if not deficient and not organic:
        suggestions.append("Nutrient levels are adequate. Maintain with the regular fertilizer schedule.")
    if any(v == "High" for v in status.values()):
        high = [k for k, v in status.items() if v == "High"]
        suggestions.append(f"{', '.join(high)} already high: avoid additional application.")

    return {
        "status": status,
        "deficient": deficient,
        "fertilizers": fertilizers,
        "organic": organic,
        "suggestions": suggestions,
    }
