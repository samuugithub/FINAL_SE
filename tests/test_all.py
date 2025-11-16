# tests/test_all.py
import sys
import os
import types
import pytest

# ------------------------------------------------------------
# ADD PROJECT ROOT TO PATH
# ------------------------------------------------------------
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT_DIR)

print("PYTHONPATH:", ROOT_DIR)


# ------------------------------------------------------------
# STUB ALL EXTERNAL PACKAGES BEFORE IMPORTING PROJECT MODULES
# ------------------------------------------------------------

def stub_module(name, obj=None):
    """Register a stub module in sys.modules"""
    m = types.ModuleType(name)
    if obj:
        for k, v in obj.items():
            setattr(m, k, v)
    sys.modules[name] = m
    return m

# --- psutil ---
if "psutil" not in sys.modules:
    stub_module("psutil", {
        "cpu_percent": lambda interval=1: 0.0,
        "virtual_memory": lambda: types.SimpleNamespace(percent=0.0),
        "disk_usage": lambda p: types.SimpleNamespace(percent=0.0)
    })

# --- dotenv ---
if "dotenv" not in sys.modules:
    stub_module("dotenv", {"load_dotenv": lambda *a, **k: None})

# --- plyer ---
if "plyer" not in sys.modules:
    stub_module("plyer", {"notification": types.SimpleNamespace(notify=lambda **k: None)})

# --- pytz ---
if "pytz" not in sys.modules:
    stub_module("pytz", {"timezone": lambda x: None})

# --- twilio ---
if "twilio" not in sys.modules:
    rest = types.SimpleNamespace(Client=lambda *a, **k: None)
    t = stub_module("twilio", {"rest": rest})
    sys.modules["twilio.rest"] = rest

# --- mysql.connector ---
if "mysql" not in sys.modules:
    mysql_mod = stub_module("mysql")
    mysql_connector = types.SimpleNamespace(connect=lambda *a, **k: None)
    sys.modules["mysql.connector"] = mysql_connector
    mysql_mod.connector = mysql_connector

# --- flask_sqlalchemy ---
if "flask_sqlalchemy" not in sys.modules:
    class FakeDB:
        def __init__(self, *a, **k):
            self.Column = lambda *a, **k: None
            self.Integer = int
            self.String = str
            self.Float = float
            self.Boolean = bool
            self.Text = str
            self.ForeignKey = lambda *a, **k: None
            self.TIMESTAMP = None
            self.func = types.SimpleNamespace(current_timestamp=lambda: None)
            self.relationship = lambda *a, **k: None
            self.Model = type("Model", (), {})
            self.session = types.SimpleNamespace(
                add=lambda *a, **k: None,
                commit=lambda: None,
                execute=lambda *a, **k: None
            )
            self.text = lambda t: t

    stub_module("flask_sqlalchemy", {"SQLAlchemy": FakeDB})

# --- flask (fallback only if missing) ---
try:
    import flask
except Exception:
    stub_module("flask", {
        "Flask": lambda *a, **k: types.SimpleNamespace(
            route=lambda *a, **k: (lambda f: f),
            url_map=types.SimpleNamespace(iter_rules=lambda: []),
            run=lambda *a, **k: None
        )
    })

# ------------------------------------------------------------
# NOW SAFE TO IMPORT PROJECT MODULES
# ------------------------------------------------------------
import Agent.agent as agent
import backend.app as app_mod
import backend.train_model as train_mod
from backend.database import models as db_models
from backend.utils import notifier as notifier_mod


# ------------------------------------------------------------
# TESTS BEGIN BELOW
# ------------------------------------------------------------

def test_collect_metrics_structure(monkeypatch):
    monkeypatch.setattr(agent.psutil, "cpu_percent", lambda interval=1: 12.5)
    monkeypatch.setattr(agent.psutil, "virtual_memory", lambda: types.SimpleNamespace(percent=45.0))
    monkeypatch.setattr(agent.psutil, "disk_usage", lambda path: types.SimpleNamespace(percent=70.0))

    if hasattr(agent, "np") and hasattr(agent.np, "random"):
        monkeypatch.setattr(agent.np.random, "uniform", lambda a, b: 2.5)

    res = agent.collect_metrics()
    assert isinstance(res, dict)
    for key in ["CPU_Usage", "Memory_Usage", "Disk_IO", "Network_Latency", "Error_Rate", "timestamp"]:
        assert key in res


def test_auto_load_model_no_files(monkeypatch):
    monkeypatch.setattr(agent.os.path, "exists", lambda p: False)
    model, scaler = agent.auto_load_model()
    assert model is None and scaler is None


class FakeSession:
    def __init__(self):
        self.added = []
    def add(self, obj):
        self.added.append(obj)
    def commit(self):
        pass
    def execute(self, text, params=None):
        pass


class DummyModel:
    def predict(self, X): return [1]
    def predict_proba(self, X): return [[0.1, 0.9]]


class DummyScaler:
    def transform(self, X): return X


class DummyAdmin:
    admin_id = 1


class DummySystem:
    system_id = 2
    system_name = "TestSystem"


def test_make_prediction_no_model(monkeypatch):
    fake_db = types.SimpleNamespace(session=FakeSession(), text=lambda t: t)
    monkeypatch.setattr(agent, "db", fake_db)

    metrics = {
        "CPU_Usage": 10, "Memory_Usage": 20, "Disk_IO": 5,
        "Network_Latency": 30, "Error_Rate": 0
    }

    agent.make_prediction(metrics, DummyAdmin(), DummySystem(), None, None)
    assert len(fake_db.session.added) >= 2


def test_make_prediction_with_model(monkeypatch):
    fake_db = types.SimpleNamespace(session=FakeSession(), text=lambda t: t)
    monkeypatch.setattr(agent, "db", fake_db)

    metrics = {
        "CPU_Usage": 90, "Memory_Usage": 85, "Disk_IO": 80,
        "Network_Latency": 5, "Error_Rate": 1
    }

    agent.make_prediction(metrics, DummyAdmin(), DummySystem(), DummyModel(), DummyScaler())
    assert len(fake_db.session.added) >= 2


def test_app_module_has_flask_app():
    assert hasattr(app_mod, "app")
    assert hasattr(app_mod.app, "url_map")
    assert isinstance(list(app_mod.app.url_map.iter_rules()), list)


def test_train_model_functions_exist():
    assert hasattr(train_mod, "prepare_data")
    assert hasattr(train_mod, "main")


def test_database_models_have_fields():
    assert hasattr(db_models.Admin, "email")
    assert hasattr(db_models.SystemInfo, "system_name")
    assert hasattr(db_models.SystemMetrics, "CPU_Usage")


def test_notifier_module_exports_functions():
    assert hasattr(notifier_mod, "get_connection")
    assert hasattr(notifier_mod, "send_email") or hasattr(notifier_mod, "send_alert")
