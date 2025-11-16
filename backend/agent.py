import os
import psutil
import socket
import numpy as np
import time
import requests
from datetime import datetime
import pytz
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import joblib
from plyer import notification

# ======================================================
# 🔹 Load Environment Variables
# ======================================================
load_dotenv()

DB_USER = os.getenv("DB_USER", "cpumetric_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "StrongPassword123")
DB_HOST = os.getenv("DB_HOST", "192.168.0.130")  # backend MySQL host (main system)
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "CPUMETRIC")

# Flask + SQLAlchemy Setup
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = (
    f"mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

IST = pytz.timezone("Asia/Kolkata")

# ======================================================
# 🔹 Backend URL for fetching notifications
# ======================================================
BACKEND_URL = "http://192.168.0.130:5000"  # ✅ Replace with backend Flask server IP


# ======================================================
# 🔹 Database Models
# ======================================================
class Admin(db.Model):
    _tablename_ = "admin"
    admin_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(150), unique=True)
    phone = db.Column(db.String(20))
    password_hash = db.Column(db.String(255))
    created_at = db.Column(db.TIMESTAMP, server_default=db.func.current_timestamp())


class SystemInfo(db.Model):
    _tablename_ = "system_info"
    system_id = db.Column(db.Integer, primary_key=True)
    system_name = db.Column(db.String(100))
    location = db.Column(db.String(150))
    ip_address = db.Column(db.String(50))
    admin_id = db.Column(db.Integer, db.ForeignKey("admin.admin_id"))
    registered_at = db.Column(db.TIMESTAMP, server_default=db.func.current_timestamp())


class SystemMetrics(db.Model):
    _tablename_ = "system_metrics"
    metric_id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    system_id = db.Column(db.Integer, db.ForeignKey("system_info.system_id"), nullable=False)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(IST))
    CPU_Usage = db.Column(db.Float)
    Memory_Usage = db.Column(db.Float)
    Disk_IO = db.Column(db.Float)
    Network_Latency = db.Column(db.Float)
    Error_Rate = db.Column(db.Float)


class PredictionLog(db.Model):
    _tablename_ = "prediction_log"
    prediction_id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    system_id = db.Column(db.Integer, db.ForeignKey("system_info.system_id"), nullable=False)
    downtime_risk = db.Column(db.Boolean, nullable=False)
    probability = db.Column(db.Float)
    estimated_time_to_downtime = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(IST))


class SystemHistory(db.Model):
    _tablename_ = "system_history"
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    system_name = db.Column(db.String(100))
    cpu_usage = db.Column(db.Float)
    memory_usage = db.Column(db.Float)
    disk_io = db.Column(db.Float)
    network_latency = db.Column(db.Float)
    error_rate = db.Column(db.Float)
    status = db.Column(db.String(20))
    downtime_detected = db.Column(db.Boolean, default=False)


# ======================================================
# 🔹 Collect Real-Time Metrics
# ======================================================
def collect_metrics():
    return {
        "CPU_Usage": psutil.cpu_percent(interval=1),
        "Memory_Usage": psutil.virtual_memory().percent,
        "Disk_IO": psutil.disk_usage("/").percent,
        "Network_Latency": np.random.uniform(10, 100),
        "Error_Rate": np.random.uniform(0, 5),
        "timestamp": datetime.now(IST)
    }


# ======================================================
# 🔹 Auto Load ML Model + Scaler
# ======================================================
def auto_load_model():
    backend_dir = os.path.dirname(os.path.abspath(_file_))
    model_path = os.path.join(backend_dir, "models", "model_latest.joblib")
    scaler_path = os.path.join(backend_dir, "models", "scaler_latest.joblib")

    model = scaler = None
    if os.path.exists(model_path) and os.path.exists(scaler_path):
        try:
            model = joblib.load(model_path)
            scaler = joblib.load(scaler_path)
            print("🧠 ML model and scaler loaded successfully.")
        except Exception as e:
            print(f"⚠ Could not load model/scaler: {e}")
    else:
        print("ℹ Model/scaler not found — running metrics-only mode.")
    return model, scaler


# ======================================================
# 🔹 Admin Registration & Login
# ======================================================
def register_admin():
    print("\n🆕 Register a new Admin and System")
    name = input("Enter your Name: ").strip()
    email = input("Enter your Email: ").strip()
    phone = input("Enter your Phone Number: ").strip()
    password = input("Enter Password: ").strip()

    with app.app_context():
        if Admin.query.filter_by(email=email).first():
            print("⚠ Email already exists. Please log in instead.")
            return None, None

        admin = Admin(name=name, email=email, phone=phone, password_hash=generate_password_hash(password))
        db.session.add(admin)
        db.session.commit()

        hostname = socket.gethostname()
        system = SystemInfo(
            system_name=hostname,
            location="Remote Node",
            ip_address=socket.gethostbyname(hostname),
            admin_id=admin.admin_id
        )
        db.session.add(system)
        db.session.commit()

        print(f"✅ Registered successfully! Linked system: {hostname}")
        return admin, system


def login_admin():
    print("\n🔑 Admin Login")
    email = input("Enter your Email: ").strip()
    password = input("Enter Password: ").strip()

    with app.app_context():
        admin = Admin.query.filter_by(email=email).first()
        if not admin or not check_password_hash(admin.password_hash, password):
            print("❌ Invalid credentials.")
            return None, None

        hostname = socket.gethostname()
        system = SystemInfo.query.filter_by(system_name=hostname, admin_id=admin.admin_id).first()
        if not system:
            system = SystemInfo(
                system_name=hostname,
                location="Remote Node",
                ip_address=socket.gethostbyname(hostname),
                admin_id=admin.admin_id
            )
            db.session.add(system)
            db.session.commit()
            print(f"🖥 New system registered: {hostname}")
        else:
            print(f"✅ Logged in as {admin.name} ({admin.email})")

        return admin, system


# ======================================================
# 🔹 Make Prediction + Log Notifications
# ======================================================
def make_prediction(metrics, admin, system, model, scaler):
    with app.app_context():
        try:
            if model and scaler:
                features = [
                    metrics["CPU_Usage"], metrics["Memory_Usage"], metrics["Disk_IO"],
                    metrics["Network_Latency"], metrics["Error_Rate"]
                ] + [0.0] * 15
                scaled = scaler.transform([features])
                pred = int(model.predict(scaled)[0])
                prob = float(model.predict_proba(scaled)[0][1] * 100)
            else:
                pred, prob = 0, 50.0
        except Exception as e:
            print(f"⚠ ML Prediction failed: {e}")
            pred, prob = 0, 50.0

        # ✅ Determine risk purely by probability
        if prob >= 85:
            risk_level = "High"
        elif prob >= 75:
            risk_level = "Medium"
        else:
            risk_level = "Low"

        # ✅ Always log metrics and predictions
        db.session.add(SystemMetrics(
            system_id=system.system_id,
            CPU_Usage=metrics["CPU_Usage"],
            Memory_Usage=metrics["Memory_Usage"],
            Disk_IO=metrics["Disk_IO"],
            Network_Latency=metrics["Network_Latency"],
            Error_Rate=metrics["Error_Rate"]
        ))

        db.session.add(PredictionLog(
            system_id=system.system_id,
            downtime_risk=pred,
            probability=prob,
            estimated_time_to_downtime=15 if pred == 1 else None
        ))

        # ✅ Only create notification if probability crosses 75%
        if prob >= 75:
            msg = (
                f"⚠ {risk_level} Downtime Risk Detected for {system.system_name} "
                f"({prob:.2f}%). CPU={metrics['CPU_Usage']}%, MEM={metrics['Memory_Usage']}%"
            )
            db.session.execute(
                db.text("""
                    INSERT INTO notifications (admin_id, system_id, message, risk_level, status)
                    VALUES (:admin_id, :system_id, :message, :risk_level, 'Unread')
                """),
                {"admin_id": admin.admin_id, "system_id": system.system_id,
                 "message": msg, "risk_level": risk_level}
            )
            print(f"🚨 Notification logged → {msg}")
        else:
            print(f"✅ No alert (Risk={prob:.2f}%) — Below threshold")

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"❌ Commit failed: {e}")

        print(f"🕒 {metrics['timestamp'].strftime('%Y-%m-%d %H:%M:%S')} | "
              f"CPU={metrics['CPU_Usage']}% | MEM={metrics['Memory_Usage']}% | "
              f"Risk={prob:.2f}% | Level={risk_level}")
# ======================================================
# 🔹 Check Backend for New Notifications
# ======================================================
def check_new_notifications(system_id):
    try:
        res = requests.get(f"{BACKEND_URL}/api/notifications/{system_id}", timeout=5)
        if res.status_code == 200:
            data = res.json().get("notifications", [])
            for n in data:
                notification.notify(
                    title=f"🚨 {n['risk_level']} Risk Alert",
                    message=n["message"],
                    timeout=8
                )
                print(f"💻 System Alert Displayed: {n['message']}")
    except Exception as e:
        print(f"⚠ Notification fetch failed: {e}")


# ======================================================
# 🔹 Main Loop
# ======================================================
if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    choice = input("\nDo you already have an account? (y/n): ").strip().lower()
    admin, system = login_admin() if choice == "y" else register_admin()

    if not admin or not system:
        print("❌ Exiting: could not authenticate or register.")
        exit()

    model, scaler = auto_load_model()
    print(f"\n🚀 Starting metric collection for system: {system.system_name}\n")

    while True:
        metrics = collect_metrics()
        make_prediction(metrics, admin, system, model, scaler)
        check_new_notifications(system.system_id)
        print("⏳ Waiting 60 seconds...\n")
        time.sleep(60)