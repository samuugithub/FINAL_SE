import types
import pytest

# Import modules under test
import Agent.agent as agent
import backend.app as app_mod
import backend.train_model as train_mod
from backend.database import models as db_models
from backend.utils import notifier as notifier_mod


# ------------------------------------------------------------
# 🔹 Test collect_metrics()
# ------------------------------------------------------------
def test_collect_metrics_structure(monkeypatch):
    # make psutil and numpy predictable
    monkeypatch.setattr(agent.psutil, "cpu_percent", lambda interval=1: 12.5)
    monkeypatch.setattr(agent.psutil, "virtual_memory", lambda: types.SimpleNamespace(percent=45.0))
    monkeypatch.setattr(agent.psutil, "disk_usage", lambda path: types.SimpleNamespace(percent=70.0))
    monkeypatch.setattr(agent.np.random, "uniform", lambda a, b: 2.5)

    res = agent.collect_metrics()

    assert isinstance(res, dict)
    expected_keys = [
        "CPU_Usage",
        "Memory_Usage",
        "Disk_IO",
        "Network_Latency",
        "Error_Rate",
        "timestamp",
    ]

    for key in expected_keys:
        assert key in res


# ------------------------------------------------------------
# 🔹 Test auto_load_model() when model files don't exist
# ------------------------------------------------------------
def test_auto_load_model_no_files(monkeypatch):
    # mock "os.path.exists" so files do NOT exist
    monkeypatch.setattr(agent.os.path, "exists", lambda p: False)
    model, scaler = agent.auto_load_model()

    assert model is None
    assert scaler is None


# ------------------------------------------------------------
# Helpers for DB mocking
# ------------------------------------------------------------
class FakeSession:
    def __init__(self):
        self.added = []
        self.executed = []

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        pass

    def execute(self, text, params=None):
        self.executed.append((text, params))


class DummyModel:
    def predict(self, X):
        return [1]  # always predict "risk"

    def predict_proba(self, X):
        return [[0.1, 0.9]]  # 90% risk


class DummyScaler:
    def transform(self, X):
        return X


class DummyAdmin:
    def __init__(self):
        self.admin_id = 1


class DummySystem:
    def __init__(self):
        self.system_id = 2
        self.system_name = "TestSystem"


# ------------------------------------------------------------
# 🔹 Test make_prediction() without model (fallback path)
# ------------------------------------------------------------
def test_make_prediction_no_model(monkeypatch):
    fake_db = types.SimpleNamespace(
        session=FakeSession(),
        text=lambda t: t,
    )
    monkeypatch.setattr(agent, "db", fake_db)

    admin = DummyAdmin()
    system = DummySystem()

    metrics = {
        "CPU_Usage": 10,
        "Memory_Usage": 20,
        "Disk_IO": 5,
        "Network_Latency": 30,
        "Error_Rate": 0,
    }

    agent.make_prediction(metrics, admin, system, None, None)

    # Should create SystemMetrics + PredictionLog
    assert len(fake_db.session.added) >= 2


# ------------------------------------------------------------
# 🔹 Test make_prediction() with a dummy ML model
# ------------------------------------------------------------
def test_make_prediction_with_model(monkeypatch):
    fake_db = types.SimpleNamespace(
        session=FakeSession(),
        text=lambda t: t,
    )
    monkeypatch.setattr(agent, "db", fake_db)

    admin = DummyAdmin()
    system = DummySystem()

    metrics = {
        "CPU_Usage": 90,
        "Memory_Usage": 85,
        "Disk_IO": 80,
        "Network_Latency": 5,
        "Error_Rate": 1,
    }

    model = DummyModel()
    scaler = DummyScaler()

    agent.make_prediction(metrics, admin, system, model, scaler)

    # Should add the metric + prediction logs
    assert len(fake_db.session.added) >= 2


# ------------------------------------------------------------
# 🔹 Test Flask app configuration
# ------------------------------------------------------------
def test_app_module_has_flask_app():
    assert hasattr(app_mod, "app")
    assert hasattr(app_mod.app, "url_map")

    routes = [r.rule for r in app_mod.app.url_map.iter_rules()]
    assert any(r.startswith("/api/") for r in routes)


# ------------------------------------------------------------
# 🔹 Test ML training script basics
# ------------------------------------------------------------
def test_train_model_functions_exist():
    assert hasattr(train_mod, "prepare_data")
    assert hasattr(train_mod, "main")


# ------------------------------------------------------------
# 🔹 Test database model fields
# ------------------------------------------------------------
def test_database_models_have_fields():
    assert hasattr(db_models.Admin, "email")
    assert hasattr(db_models.SystemInfo, "system_name")
    assert hasattr(db_models.SystemMetrics, "CPU_Usage")


# ------------------------------------------------------------
# 🔹 Test notifier module exports functions
# ------------------------------------------------------------
def test_notifier_module_exports_functions():
    assert hasattr(notifier_mod, "get_connection")
    assert hasattr(notifier_mod, "send_email") or hasattr(
        notifier_mod, "send_alert"
    )
