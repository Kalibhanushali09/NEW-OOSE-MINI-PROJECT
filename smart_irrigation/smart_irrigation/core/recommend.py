"""Module 7: Recommendation engine - merges soil, nutrient, irrigation and weather outputs."""
from datetime import date, timedelta


def build(soil, nutrients, irrigation, weather, soil_inputs):
    recs = []  # (priority, text); lower number = more urgent
    sal = soil["salinity"]
    days = irrigation["days"]
    rain = weather["rainfall"]

    # --- irrigation timing
    if irrigation["need"] == "High" and rain < 5:
        recs.append((1, "Irrigate immediately - soil moisture is near the trigger level."))
    elif rain >= 10 and days <= 3:
        recs.append((1, f"Delay irrigation - about {rain:.0f} mm rain is forecast in the next 3 days."))
    elif days <= 1:
        recs.append((1, "Irrigate today or tomorrow."))
    else:
        recs.append((2, f"Next irrigation in {days} day(s) for about {irrigation['duration_hours']} hours."))

    # --- salinity
    if sal == "Slightly Saline":
        recs += [(3, "Apply gypsum after next harvest."), (4, "Monitor EC after rainfall or irrigation.")]
    elif sal == "Moderately Saline":
        recs += [(2, "Apply gypsum (about 2.5-5 t/ha) and improve field drainage."),
                 (3, "Add a leaching irrigation before the next crop cycle."),
                 (4, "Retest soil in 30 days.")]
    elif sal in ("Highly Saline", "Unsuitable for Sugarcane"):
        recs += [(1, "Reclaim soil first: gypsum, sub-surface drainage and leaching irrigation."),
                 (2, "Consider salt-tolerant varieties or a different crop until EC drops."),
                 (3, "Retest soil in 2-3 weeks.")]
    else:
        recs.append((5, "Soil salinity is within safe limits."))

    # --- nutrients
    for fert in nutrients["fertilizers"]:
        recs.append((3, f"Apply {fert}."))
    for o in nutrients["organic"]:
        recs.append((4, o + "."))
    for s in nutrients["suggestions"]:
        recs.append((4, s))
    high_ec_and_n = soil_inputs["ec"] > 4 and nutrients["status"]["Nitrogen"] != "Low"
    if high_ec_and_n:
        recs.append((3, "Reduce fertilizer application - high EC means extra salts from fertilizer will hurt the crop."))

    recs.sort(key=lambda x: x[0])
    seen, out = set(), []
    for _, t in recs:
        if t not in seen:
            seen.add(t)
            out.append(t)

    alerts = []
    if sal in ("Highly Saline", "Unsuitable for Sugarcane"):
        alerts.append(("error", f"Critical: soil is {sal.lower()}."))
    elif sal == "Moderately Saline":
        alerts.append(("warning", "Soil is moderately saline."))
    if irrigation["need"] == "High" and rain < 5:
        alerts.append(("warning", "Irrigation is due now."))
    if rain >= 20:
        alerts.append(("info", f"Heavy rain forecast ({rain:.0f} mm in 3 days). Check drainage."))
    if soil["score"] < 50:
        alerts.append(("error", "Soil health score below 50."))

    return {
        "recommendations": out,
        "alerts": alerts,
        "next_irrigation_date": (date.today() + timedelta(days=days)).isoformat(),
    }
