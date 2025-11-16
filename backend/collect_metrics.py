import psutil
import socket
import joblib
import numpy as np
import os
from datetime import datetime
import pytz
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
# NOTE: Removed 'from models import db, SystemHistory' as models are defined below
# The original code had redundant import of db and SystemHistory, which are defined later.

# ======================================================
# 🔹 Flask App Setup
# ======================================================
app = Flask(__name__)
# NOTE: Using a hardcoded URI for demonstration. In production, this should be secured.
app.config["SQLALCHEMY_DATABASE_URI"] = "mysql+mysqlconnector://root:006655%40Chitra@localhost/CPUMETRIC"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# ======================================================
# 🔹 Timezone Setup (IST)
# ======================================================
IST = pytz.timezone("Asia/Kolkata")

# ======================================================
# 🔹 Database Models
# ======================================================
class Admin(db.Model):
    __tablename__ = "Admin"
    admin_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    phone = db.Column(db.String(20))
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.TIMESTAMP, server_default=db.func.current_timestamp())


class SystemInfo(db.Model):
    __tablename__ = "System_Info"
    system_id = db.Column(db.Integer, primary_key=True)
    system_name = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(150))
    ip_address = db.Column(db.String(50))
    admin_id = db.Column(db.Integer, db.ForeignKey("Admin.admin_id"))
    registered_at = db.Column(db.TIMESTAMP, server_default=db.func.current_timestamp())


class SystemMetrics(db.Model):
    __tablename__ = "System_Metrics"
    metric_id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    system_id = db.Column(db.Integer, db.ForeignKey("System_Info.system_id"), nullable=False)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(IST))
    CPU_Usage = db.Column(db.Float)
    Memory_Usage = db.Column(db.Float)
    Disk_IO = db.Column(db.Float)
    Network_Latency = db.Column(db.Float)
    Error_Rate = db.Column(db.Float)


class PredictionLog(db.Model):
    __tablename__ = "Prediction_Log"
    prediction_id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    system_id = db.Column(db.Integer, db.ForeignKey("System_Info.system_id"), nullable=False)
    predicted_at = db.Column(db.TIMESTAMP, server_default=db.func.current_timestamp())
    downtime_risk = db.Column(db.Boolean, nullable=False)
    probability = db.Column(db.Float)
    estimated_time_to_downtime = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(IST))

class SystemHistory(db.Model):
    __tablename__ = 'system_history'

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    system_name = db.Column(db.String(100), nullable=False)
    cpu_usage = db.Column(db.Float, nullable=False)
    memory_usage = db.Column(db.Float, nullable=False)
    disk_io = db.Column(db.Float, nullable=False)
    network_latency = db.Column(db.Float, nullable=False)
    error_rate = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), nullable=False)
    downtime_detected = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f"<SystemHistory {self.system_name} {self.timestamp}>"

# ======================================================
# 🔹 Collect Real-Time Metrics
# ======================================================
def collect_metrics():
    """Collects real-time system usage metrics using psutil."""
    # NOTE: Disk_IO is tracked as MB read/sec since last call, adjusted for 1s interval.
    # In a real system, you might want to track cumulative, or use a difference between two calls.
    return {
        "CPU_Usage": psutil.cpu_percent(interval=1),
        "Memory_Usage": psutil.virtual_memory().percent,
        "Disk_IO": psutil.disk_io_counters().read_bytes / (1024 * 1024),  # MB read (approx)
        "Network_Latency": np.random.uniform(1, 10),  # Simulated latency in ms
        "Error_Rate": np.random.uniform(0, 0.05),  # Simulated error rate
        "timestamp": datetime.now(IST)
    }


# ======================================================
# 🔹 Run Prediction + Save Results
# ======================================================
MODEL_PATH = "model.pkl"
SCALER_PATH = "scaler.pkl"

def make_prediction(metrics):
    """
    Loads model and scaler, makes a prediction on current metrics, 
    and saves metrics, prediction, and history to the database.
    """
    with app.app_context():
        # Check model/scaler availability
        if not (os.path.exists(MODEL_PATH) and os.path.exists(SCALER_PATH)):
            print("⚠️ Model or Scaler not found. Please ensure both files exist.")
            print("  Skipping prediction and logging, but database setup is complete.")
            return

        try:
            model = joblib.load(MODEL_PATH)
            scaler = joblib.load(SCALER_PATH)
        except Exception as e:
            print(f"❌ Error loading model or scaler: {e}")
            return


        # Prepare features for model (Assuming model expects 20 features for consistency)
        features = [
            metrics["CPU_Usage"],
            metrics["Memory_Usage"],
            metrics["Disk_IO"],
            metrics["Network_Latency"],
            metrics["Error_Rate"]
        ]
        # Pad features to meet the expected 20 feature input of a mock model
        while len(features) < 20:
            features.append(0.0)

        scaled = scaler.transform([features])
        prediction_value = model.predict(scaled)[0]
        probability_value = (
            model.predict_proba(scaled)[0][1] * 100
            if hasattr(model, "predict_proba")
            else None
        )

        print("\n🕒 Prediction Time (IST):", metrics["timestamp"].strftime("%Y-%m-%d %H:%M:%S %Z%z"))
        print("=" * 36)
        print(f"🔍 Prediction: {'⚠️ Downtime Risk' if prediction_value == 1 else '✅ Normal'}")
        if probability_value is not None:
            print(f"📊 Probability: {probability_value:.2f}%")
        print("=" * 36)

        # === Ensure at least one Admin exists ===
        admin = Admin.query.first()
        if not admin:
            print("⚙️ No admin found. Creating default admin...")
            admin = Admin(
                name="Super Admin",
                email="admin@example.com",
                phone="9999999999",
                password_hash="default123"
            )
            db.session.add(admin)
            db.session.commit()

        # === Ensure at least one System exists ===
        system = SystemInfo.query.first()
        if not system:
            print("⚙️ No system found. Creating default system...")
            system = SystemInfo(
                system_name=socket.gethostname(),
                location="Bangalore",
                ip_address=socket.gethostbyname(socket.gethostname()),
                admin_id=admin.admin_id
            )
            db.session.add(system)
            db.session.commit()

        # === Save metrics into System_Metrics ===
        try:
            metric_entry = SystemMetrics(
                system_id=system.system_id,
                CPU_Usage=metrics["CPU_Usage"],
                Memory_Usage=metrics["Memory_Usage"],
                Disk_IO=metrics["Disk_IO"],
                Network_Latency=metrics["Network_Latency"],
                Error_Rate=metrics["Error_Rate"],
                timestamp=metrics["timestamp"]
            )
            db.session.add(metric_entry)
            db.session.commit()
            print("📊 Metrics stored successfully!")
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error storing metrics: {e}")


        # === Save prediction into Prediction_Log ===
        try:
            log_entry = PredictionLog(
                system_id=system.system_id,
                downtime_risk=int(prediction_value),
                probability=float(probability_value) if probability_value is not None else None,
                estimated_time_to_downtime=None if prediction_value == 0 else 15,
                created_at=datetime.now(IST)
            )
            db.session.add(log_entry)
            db.session.commit()
            print("💾 Prediction stored successfully!")
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error storing prediction: {e}")

        # === Log into System_History (FIXED INDENTATION and column name) ===
        try:
            history_entry = SystemHistory(
                system_name=system.system_name,
                cpu_usage=metrics["CPU_Usage"],
                memory_usage=metrics["Memory_Usage"],
                disk_io=metrics["Disk_IO"],
                network_latency=metrics["Network_Latency"],
                error_rate=metrics["Error_Rate"],
                status="Critical" if prediction_value == 1 else "Normal",
                downtime_detected=bool(prediction_value),
                timestamp=datetime.now(IST) # Use 'timestamp' based on the SystemHistory model
            )
            db.session.add(history_entry)
            db.session.commit()
            print("🧾 System history logged successfully!")
        except Exception as e:
            db.session.rollback()
            print(f"⚠️ Error storing system history: {e}")


# ======================================================
# 🔹 Main Entry Point
# ======================================================
import time

if __name__ == "__main__":
    with app.app_context():
        # Create all tables if they do not exist
        db.create_all()
        print("📚 Database tables checked/created.")

    print("🚀 Starting Continuous Real-Time System Metric Collection...")
    print("NOTE: You must have 'model.pkl' and 'scaler.pkl' in the same directory for predictions to run.")

    while True:
        metrics = collect_metrics()
        make_prediction(metrics)
        print("⏳ Waiting 60 seconds before next check...\n")
        time.sleep(60)  # Run every 60 seconds
