import os, tempfile, sys
os.environ["IRRIGATION_DB"] = os.path.join(tempfile.mkdtemp(), "app.db")
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from streamlit.testing.v1 import AppTest

def test_full_flow():
    at = AppTest.from_file(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py"), default_timeout=60).run()
    assert not at.exception
    # register
    at.tabs[1].text_input[0].set_value("Kali B"); at.tabs[1].text_input[1].set_value("9123456780")
    at.tabs[1].text_input[2].set_value("secret1"); at.tabs[1].text_input[3].set_value("secret1")
    at.tabs[1].button[0].click().run()
    assert any("created" in s.value for s in at.success), [e.value for e in at.error]
    # login
    at.tabs[0].text_input[0].set_value("9123456780"); at.tabs[0].text_input[1].set_value("secret1")
    at.tabs[0].button[0].click().run()
    assert not at.exception and at.session_state["user"]["name"] == "Kali B"
    # add farm
    at.sidebar.radio[0].set_value("My Farms").run()
    at.text_input[0].set_value("Plot 1"); at.text_input[1].set_value("Kolhapur")
    at.button[0].click().run()
    assert not at.exception
    # analysis
    at.sidebar.radio[0].set_value("Analysis").run()
    assert not at.exception, at.exception
    btn = [b for b in at.button if "Analyze" in b.label][0]
    btn.click().run()
    assert not at.exception
    assert any(m.label == "Soil health score" for m in at.metric)
    for p in ("Dashboard", "History", "About"):
        at.sidebar.radio[0].set_value(p).run()
        assert not at.exception, (p, at.exception)
