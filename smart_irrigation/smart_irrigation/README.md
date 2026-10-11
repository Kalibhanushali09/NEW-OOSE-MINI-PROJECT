# AI-Based Soil Health & Irrigation Advisory System (Streamlit)

Sugarcane decision-support app covering the 8 SRS modules: registration, login, farm management,
soil health & salinity prediction, nutrient deficiency analysis, irrigation prediction (+ live weather),
recommendation engine, and prediction history.

## Run locally
    pip install -r requirements.txt
    streamlit run app.py
Models auto-train on first launch (a few seconds) and are cached in `models/`.

## Deploy on Streamlit Community Cloud
1. Push this folder to a GitHub repo (app file: `app.py`).
2. share.streamlit.io -> New app -> pick repo/branch -> main file `app.py` -> Deploy.

## Notes
- Storage is SQLite (`irrigation.db`). On Streamlit Community Cloud the filesystem is **ephemeral**: accounts and
  history reset when the app restarts/redeploys. For permanent storage swap `core/db.py` for a hosted database.
- Weather: Open-Meteo (free, no key). If unreachable, enter weather manually.
- ML models are trained on a **synthetic** dataset built from agronomic rules (see `core/ml.py`). Replace
  `generate_*_data` with your real CSV and run `python -m core.ml` to retrain.
- Tests: `pip install pytest && python -m pytest tests`

## Layout
    app.py            UI (login, farms, analysis, dashboard, history, about)
    core/db.py        SQLite tables (farmers, farms, soil_tests, weather, predictions)
    core/auth.py      Modules 1-2      core/farms.py     Module 3
    core/ml.py        Modules 4 & 6    core/nutrients.py Module 5
    core/recommend.py Module 7         core/pipeline.py  glue + Module 8 history
    core/weather.py   Open-Meteo client
