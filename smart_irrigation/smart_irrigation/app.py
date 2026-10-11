"""AI-Based Soil Health and Irrigation Advisory System for Sugarcane Farms (Streamlit)."""
import json

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from core import auth, db, farms, ml, pipeline, weather

st.set_page_config(page_title="Soil Health & Irrigation Advisor", page_icon="🌱", layout="wide")
db.init_db()


@st.cache_resource(show_spinner="Loading prediction models...")
def get_models():
    return ml.load_models()


models = get_models()

st.markdown(
    """
<style>
.block-container {padding-top: 1.5rem;}
.hero {background: linear-gradient(90deg,#2e7d32,#558b2f); color:#fff; padding:1rem 1.5rem; border-radius:10px; margin-bottom:1rem;}
.hero h2 {margin:0; color:#fff;} .hero p {margin:0; opacity:.9;}
</style>""",
    unsafe_allow_html=True,
)


def hero(title, sub=""):
    st.markdown(f'<div class="hero"><h2>{title}</h2><p>{sub}</p></div>', unsafe_allow_html=True)


# ------------------------------------------------------------------ Modules 1 & 2: auth

def auth_page():
    hero("🌱 AI Soil Health & Irrigation Advisory System", "Sugarcane decision-support platform")
    login_tab, reg_tab = st.tabs(["Login", "Register"])
    with login_tab:
        with st.form("login"):
            mobile = st.text_input("Mobile number", max_chars=10)
            pw = st.text_input("Password", type="password")
            if st.form_submit_button("Login", type="primary", width="stretch"):
                if not mobile or not pw:
                    st.error("Enter mobile number and password.")
                else:
                    user = auth.login(mobile, pw)
                    if user:
                        st.session_state.user = user
                        st.rerun()
                    else:
                        st.error("Invalid mobile number or password.")
    with reg_tab:
        with st.form("register"):
            name = st.text_input("Full name")
            mobile = st.text_input("Mobile number (10 digits)", max_chars=10, key="reg_mobile")
            pw = st.text_input("Password (min 6 characters)", type="password", key="reg_pw")
            pw2 = st.text_input("Confirm password", type="password")
            if st.form_submit_button("Create account", width="stretch"):
                if pw != pw2:
                    st.error("Passwords do not match.")
                else:
                    ok, msg = auth.register(name, mobile, pw)
                    (st.success if ok else st.error)(msg)


# ------------------------------------------------------------------ Module 3: farms

def farms_page(user):
    hero("🚜 My Farms", "Register and manage your farms")
    my_farms = farms.list_farms(user["farmer_id"])

    with st.expander("➕ Add a new farm", expanded=not my_farms):
        with st.form("add_farm", clear_on_submit=True):
            c1, c2 = st.columns(2)
            name = c1.text_input("Farm name")
            village = c2.text_input("Village / town")
            area = c1.number_input("Area (acres)", min_value=0.0, value=1.0, step=0.5)
            soil_type = c2.selectbox("Soil type", farms.SOIL_TYPES)
            if st.form_submit_button("Save farm", type="primary"):
                loc = weather.geocode(village) if village.strip() else None
                fid, msg = farms.add_farm(user["farmer_id"], name, village, area, soil_type,
                                          loc[0] if loc else None, loc[1] if loc else None)
                (st.success if fid else st.error)(msg)
                if fid:
                    st.rerun()

    if not my_farms:
        st.info("You have no farms yet. Add one above.")
        return
    st.subheader("Registered farms")
    st.dataframe(pd.DataFrame(my_farms)[["farm_id", "farm_name", "village", "area", "soil_type", "crop_info"]],
                 width="stretch", hide_index=True)

    st.subheader("Edit / delete")
    sel = st.selectbox("Select farm", my_farms, format_func=lambda f: f"{f['farm_name']} ({f['village']})")
    with st.form("edit_farm"):
        c1, c2 = st.columns(2)
        name = c1.text_input("Farm name", sel["farm_name"])
        village = c2.text_input("Village / town", sel["village"])
        area = c1.number_input("Area (acres)", min_value=0.0, value=float(sel["area"]), step=0.5)
        idx = farms.SOIL_TYPES.index(sel["soil_type"]) if sel["soil_type"] in farms.SOIL_TYPES else 0
        soil_type = c2.selectbox("Soil type", farms.SOIL_TYPES, index=idx)
        b1, b2 = st.columns(2)
        save = b1.form_submit_button("Update farm", type="primary")
        delete = b2.form_submit_button("Delete farm (and its history)")
    if save:
        lat, lon = sel["latitude"], sel["longitude"]
        if village.strip() != sel["village"]:
            loc = weather.geocode(village)
            lat, lon = (loc if loc else (None, None))
        ok, msg = farms.update_farm(sel["farm_id"], user["farmer_id"], name, village, area, soil_type, lat, lon)
        (st.success if ok else st.error)(msg)
        if ok:
            st.rerun()
    if delete:
        farms.delete_farm(sel["farm_id"], user["farmer_id"])
        st.rerun()


# ------------------------------------------------------------------ Modules 4-7: analysis

def analysis_page(user):
    hero("🔬 Soil & Irrigation Analysis", "Enter soil test values, fetch weather and get recommendations")
    my_farms = farms.list_farms(user["farmer_id"])
    if not my_farms:
        st.warning("Add a farm first (My Farms page).")
        return
    farm = st.selectbox("Farm", my_farms, format_func=lambda f: f"{f['farm_name']} ({f['village']})")

    # ---- weather
    st.subheader("1. Weather")
    wkey = f"weather_{farm['farm_id']}"
    c1, c2 = st.columns([1, 3])
    if c1.button("🌦️ Fetch live weather"):
        with st.spinner("Contacting weather service..."):
            data, err = weather.fetch_weather(farm["latitude"], farm["longitude"])
        if err:
            st.warning(err)
        else:
            st.session_state[wkey] = data
            st.success("Weather updated.")
    w = st.session_state.get(wkey, {"temperature": 32.0, "humidity": 60.0, "rainfall": 0.0, "wind_speed": 8.0,
                                    "source": "manual"})
    c2.caption(f"Source: {w.get('source', 'manual')} (you can adjust the values)")
    wc = st.columns(4)
    temp = wc[0].number_input("Temperature (°C)", -5.0, 55.0, float(w["temperature"]), key=f"t{wkey}{w['temperature']}")
    hum = wc[1].number_input("Humidity (%)", 0.0, 100.0, float(w["humidity"]), key=f"h{wkey}{w['humidity']}")
    rain = wc[2].number_input("Rain forecast, next 3 days (mm)", 0.0, 500.0, float(w["rainfall"]),
                              key=f"r{wkey}{w['rainfall']}")
    wind = wc[3].number_input("Wind speed (km/h)", 0.0, 120.0, float(w["wind_speed"]), key=f"w{wkey}{w['wind_speed']}")

    # ---- soil
    st.subheader("2. Soil test values")
    with st.form("soil_form"):
        a = st.columns(4)
        ec = a[0].number_input("Electrical Conductivity EC (dS/m)", 0.0, 30.0, 3.2, 0.1)
        ph = a[1].number_input("Soil pH", 3.0, 11.0, 7.4, 0.1)
        moist = a[2].number_input("Soil moisture (%)", 0.0, 60.0, 24.0, 0.5)
        oc = a[3].number_input("Organic carbon (%)", 0.0, 5.0, 0.6, 0.05)
        b = st.columns(4)
        n = b[0].number_input("Nitrogen (kg/ha)", 0.0, 1500.0, 280.0, 10.0)
        p = b[1].number_input("Phosphorus (kg/ha)", 0.0, 200.0, 35.0, 1.0)
        k = b[2].number_input("Potassium (kg/ha)", 0.0, 1500.0, 220.0, 10.0)
        age = b[3].number_input("Crop age (days)", 0, 450, 115, 5)
        go_btn = st.form_submit_button("Analyze Soil & Predict Irrigation", type="primary", width="stretch")

    if go_btn:
        vals = dict(ec=ec, ph=ph, moisture=moist, nitrogen=n, phosphorus=p, potassium=k, organic_carbon=oc,
                    crop_age=age)
        errs = pipeline.validate_inputs(vals)
        if errs:
            for e in errs:
                st.error(e)
            return
        weather_in = dict(temperature=temp, humidity=hum, rainfall=rain, wind_speed=wind, source=w.get("source", "manual"))
        try:
            with st.spinner("Running models..."):
                st.session_state.result = (farm["farm_id"], pipeline.run(models, farm["farm_id"], vals, weather_in),
                                           weather_in)
        except Exception as e:
            st.error(f"Prediction failed ({type(e).__name__}). Please retry.")
            if st.button("Retry"):
                st.rerun()
            return

    res = st.session_state.get("result")
    if res and res[0] == farm["farm_id"]:
        show_result(res[1], res[2])


def show_result(r, w):
    soil, nut, irr, rec = r["soil"], r["nutrients"], r["irrigation"], r["rec"]
    st.divider()
    st.subheader("Results")
    for level, msg in rec["alerts"]:
        {"error": st.error, "warning": st.warning, "info": st.info}[level](msg)

    m = st.columns(4)
    m[0].metric("Soil health score", f"{soil['score']:.0f} / 100")
    m[1].metric("Salinity level", soil["salinity"])
    m[2].metric("Next irrigation", f"In {irr['days']} day(s)", rec["next_irrigation_date"], delta_color="off")
    m[3].metric("Irrigation duration", f"{irr['duration_hours']} hours")

    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=soil["score"], title={"text": "Soil health"},
        gauge={"axis": {"range": [0, 100]}, "bar": {"color": "#2e7d32"},
               "steps": [{"range": [0, 40], "color": "#ffcdd2"}, {"range": [40, 70], "color": "#fff9c4"},
                         {"range": [70, 100], "color": "#c8e6c9"}]}))
    fig.update_layout(height=250, margin=dict(t=40, b=10, l=10, r=10))
    g, t = st.columns([1, 2])
    g.plotly_chart(fig, width="stretch")
    t.table(pd.DataFrame({
        "Parameter": ["Soil suitability", "Irrigation need", "Deficient nutrients", "Fertilizer"],
        "Prediction": [soil["suitability"], f"{irr['need']} (confidence {max(irr['need_proba'].values()):.0%})",
                       ", ".join(nut["deficient"]) or "None", "; ".join(nut["fertilizers"]) or "None needed"]}))

    st.markdown("#### Recommendations")
    for t_ in rec["recommendations"]:
        st.markdown(f"- ✅ {t_}")

    with st.expander("Nutrient status detail"):
        st.dataframe(pd.DataFrame({"Nutrient": list(nut["status"]), "Level": list(nut["status"].values())}),
                     hide_index=True, width="stretch")
    st.caption("Result saved to your prediction history.")


# ------------------------------------------------------------------ Module 8: history + dashboard

def dashboard_page(user):
    hero(f"📊 Dashboard — welcome, {user['name']}", "Latest status across your farms")
    my_farms = farms.list_farms(user["farmer_id"])
    hist = pipeline.history(farmer_id=user["farmer_id"])
    if not my_farms:
        st.info("Start by adding a farm in **My Farms**, then run an analysis.")
        return
    if hist.empty:
        st.info("No predictions yet. Go to **Analysis** to run your first soil test.")
        return
    latest = hist.sort_values("prediction_id").groupby("farm_id").tail(1)
    for _, row in latest.iterrows():
        with st.container(border=True):
            st.markdown(f"**{row['farm_name']}** — last analysed {row['prediction_date']}")
            c = st.columns(4)
            c[0].metric("Soil health", f"{row['soil_health_score']:.0f}/100")
            c[1].metric("Salinity", row["salinity_level"])
            c[2].metric("Next irrigation", row["next_irrigation_date"])
            c[3].metric("Duration", f"{row['irrigation_duration_hours']} h")
            recs = json.loads(row["recommendation"]) if row["recommendation"] else []
            if recs:
                st.caption("Top recommendation: " + recs[0])
    if len(hist) > 1:
        d = hist.sort_values("prediction_id")
        st.plotly_chart(px.line(d, x="prediction_date", y="soil_health_score", color="farm_name", markers=True,
                                title="Soil health score over time"), width="stretch")


def history_page(user):
    hero("🗂️ Prediction History", "Review and compare previous soil tests")
    hist = pipeline.history(farmer_id=user["farmer_id"])
    if hist.empty:
        st.info("No history yet.")
        return
    names = ["All farms"] + sorted(hist["farm_name"].unique())
    pick = st.selectbox("Farm", names)
    if pick != "All farms":
        hist = hist[hist["farm_name"] == pick]
    show = hist[["prediction_date", "farm_name", "soil_health_score", "salinity_level", "ec", "ph", "moisture",
                 "nitrogen", "phosphorus", "potassium", "organic_carbon", "nutrient_deficiency",
                 "next_irrigation_date", "irrigation_duration_hours"]]
    st.dataframe(show, width="stretch", hide_index=True)
    st.download_button("⬇️ Download CSV", show.to_csv(index=False), "prediction_history.csv", "text/csv")

    if len(hist) >= 2:
        st.subheader("Compare soil tests")
        ordered = hist.sort_values("prediction_id")
        opts = {f"#{r.prediction_id} · {r.prediction_date} · {r.farm_name}": r.prediction_id for r in ordered.itertuples()}
        c1, c2 = st.columns(2)
        a = c1.selectbox("Earlier test", list(opts), index=0)
        b = c2.selectbox("Later test", list(opts), index=len(opts) - 1)
        ra = hist[hist.prediction_id == opts[a]].iloc[0]
        rb = hist[hist.prediction_id == opts[b]].iloc[0]
        fields = ["soil_health_score", "ec", "ph", "moisture", "nitrogen", "phosphorus", "potassium", "organic_carbon"]
        cmp = pd.DataFrame({"Parameter": fields, "Earlier": [ra[f] for f in fields], "Later": [rb[f] for f in fields]})
        cmp["Change"] = (cmp["Later"] - cmp["Earlier"]).round(2)
        st.dataframe(cmp, hide_index=True, width="stretch")
        long = cmp.melt(id_vars="Parameter", value_vars=["Earlier", "Later"])
        st.plotly_chart(px.bar(long[long.Parameter.isin(["ec", "ph", "moisture", "organic_carbon"])], x="Parameter",
                               y="value", color="variable", barmode="group"), width="stretch")


def about_page():
    hero("ℹ️ About & Model Info", "How the system works")
    st.markdown("""
**Pipeline:** soil test → *Soil Health & Salinity model* → *Nutrient rules* → weather → *Irrigation model* → *Recommendation engine*.

| Module | Technique |
|---|---|
| Salinity class | Random Forest classifier |
| Soil health score | Random Forest regressor |
| Nutrient deficiency | Rule-based thresholds (Indian soil-test ratings) |
| Irrigation need (Low/Medium/High) | Gaussian Naïve Bayes |
| Days to next irrigation / duration | Random Forest regressors |
| Recommendations | Rule engine combining all outputs |
""")
    st.warning("Models are trained on a **synthetic dataset** generated from agronomic water-balance and salinity "
               "rules (no real field dataset is bundled). Treat outputs as advisory; retrain with real data via "
               "`python -m core.ml` for production use.")
    st.json(models["metrics"])


# ------------------------------------------------------------------ router

def main():
    user = st.session_state.get("user")
    if not user:
        auth_page()
        return
    with st.sidebar:
        st.markdown(f"### 🌱 {user['name']}")
        st.caption(f"📱 {user['mobile']}")
        page = st.radio("Navigate", ["Dashboard", "My Farms", "Analysis", "History", "About"], label_visibility="collapsed")
        if st.button("Logout", width="stretch"):
            st.session_state.clear()
            st.rerun()
    {"Dashboard": lambda: dashboard_page(user), "My Farms": lambda: farms_page(user),
     "Analysis": lambda: analysis_page(user), "History": lambda: history_page(user),
     "About": about_page}[page]()


main()
