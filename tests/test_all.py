# tests/test_all.py
import sys
import os
import types

# ------------------------------------------------------------
# ADD PROJECT ROOT TO PYTHONPATH
# ------------------------------------------------------------
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)


# ------------------------------------------------------------
# STUB external modules to avoid import errors
# ------------------------------------------------------------
def stub(name, attrs=None):
    m = types.ModuleType(name)
    if attrs:
        for k, v in attrs.items():
            setattr(m, k, v)
    sys.modules[name] = m
    return m


# psutil stub
stub("psutil", {
    "cpu_percent": lambda interval=1: 10.0,
    "virtual_memory": lambda: types.SimpleNamespace(percent=50.0),
    "disk_usage": lambda p: types.SimpleNamespace(percent=60.0),
})

# dotenv stub
stub("dotenv", {"load_dotenv": lambda *a, **k: None})

# plyer stub
stub("plyer", {"notification": types.SimpleNamespace(notify=lambda **k: None)})

# pytz stub
stub("pytz", {"timezone": lambda *_: None})

# twilio stub
twilio_rest = types.SimpleNamespace(Client=lambda *a, **k: None)
stub("twilio", {"rest": twilio_rest})
sys.modules["twilio.rest"] = twilio_rest

# mysql connector stub
mysql_stub = types.SimpleNamespace(connect=lambda *a, **k: None)
stub("mysql", {"connector": mysql_stub})
sys.modules["mysql.connector"] = mysql_stub


# ------------------------------------------------------------
# ONLY IMPORT SAFE MODULE: Agent
# ------------------------------------------------------------
import Agent.agent as agent


# ------------------------------------------------------------
# TESTS START
# ------------------------------------------------------------

def test_collect_metrics():
    """Test normal metric collection."""
    res = agent.collect_metrics()

    assert isinstance(res, dict)
    assert "CPU_Usage" in res
    assert "Memory_Usage" in res
    assert "Disk_IO" in res
    assert "Network_Latency" in res
    assert "Error_Rate" in res


def test_auto_load_model_no_files(monkeypatch):
    """If files don't exist, auto_load_model returns (None, None)."""
    monkeypatch.setattr(agent.os.path, "exists", lambda p: False)
    model, scaler = agent.auto_load_model()

    assert model is None
    assert scaler is None


def test_make_prediction(monkeypatch):
    """Prediction logic should add entries into fake DB session."""
    class FakeSession:
        def __init__(self):
            self.added = []

        def add(self, x):
            self.added.append(x)

        def commit(self):
            pass

    fake_db = types.SimpleNamespace(
        session=FakeSession(),
        text=lambda t: t
    )

    monkeypatch.setattr(agent, "db", fake_db)

    admin = types.SimpleNamespace(admin_id=1)
    system = types.SimpleNamespace(system_id=2, system_name="TestSystem")

    metrics = {
        "CPU_Usage": 50,
        "Memory_Usage": 60,
        "Disk_IO": 70,
        "Network_Latency": 10,
        "Error_Rate": 0,
    }

    agent.make_prediction(metrics, admin, system, None, None)

    assert len(fake_db.session.added) > 0
