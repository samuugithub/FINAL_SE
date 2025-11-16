import os
import time
import threading
import joblib
from datetime import datetime
from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from database.db_config import db, init_db
from database.models import (
    Admin,
    SystemInfo,
    SystemMetrics,
    PredictionLog,
    Notification,
)
from utils.notifier import send_alert

# =======================================================
# 🚀 Flask Setup
# =======================================================
app = Flask(__name__)
CORS(app)
init_db(app)

# =======================================================
# 🧠 Load ML Model & Scaler
# =======================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "models", "model_latest.joblib")
SCALER_PATH = os.path.join(BASE_DIR, "models", "scaler_latest.joblib")

model = joblib.load(MODEL_PATH) if os.path.exists(MODEL_PATH) else None
scaler = joblib.load(SCALER_PATH) if os.path.exists(SCALER_PATH) else None

# =======================================================
# 🩺 Health Check
# =======================================================
@app.route("/")
def home():
    return jsonify({"message": "✅ Backend running and monitoring prediction logs"})

# =======================================================
# 🔹 Register New Admin + System
# =======================================================
@app.route("/api/register", methods=["POST"])
def register_admin():
    try:
        data = request.get_json()
        name = data.get("name")
        email = data.get("email")
        phone = data.get("phone")
        password = data.get("password")
        system_name = data.get("system_name")

        if not all([name, email, phone, password, system_name]):
            return jsonify({"error": "All fields are required"}), 400

        if Admin.query.filter_by(email=email).first():
            return jsonify({"error": "Email already registered"}), 400

        hashed_pw = generate_password_hash(password)
        admin = Admin(name=name, email=email, phone=phone, password_hash=hashed_pw)
        db.session.add(admin)
        db.session.commit()

        system = SystemInfo(
            system_name=system_name,
            ip_address=request.remote_addr,
            location="User Device",
            registered_at=datetime.utcnow(),
            admin_id=admin.admin_id,
        )
        db.session.add(system)
        db.session.commit()

        return jsonify({
            "message": "✅ Registration successful",
            "admin_id": admin.admin_id,
            "system_id": system.system_id,
            "system_name": system.system_name
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# =======================================================
# 🔹 Admin Login
# =======================================================
@app.route("/api/login", methods=["POST"])
def login_admin():
    try:
        data = request.get_json()
        email, password = data.get("email"), data.get("password")

        admin = Admin.query.filter_by(email=email).first()
        if not admin or not check_password_hash(admin.password_hash, password):
            return jsonify({"error": "Invalid credentials"}), 401

        systems = SystemInfo.query.filter_by(admin_id=admin.admin_id).all()
        sys_data = [{"system_id": s.system_id, "system_name": s.system_name} for s in systems]

        return jsonify({
            "admin_id": admin.admin_id,
            "name": admin.name,
            "email": admin.email,
            "systems": sys_data,
            "message": "✅ Login successful"
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =======================================================
# 🔹 Fetch All Systems (for Admin)
# =======================================================
@app.route("/api/systems/<int:admin_id>", methods=["GET"])
def get_systems(admin_id):
    try:
        systems = SystemInfo.query.filter_by(admin_id=admin_id).all()
        return jsonify([
            {
                "system_id": s.system_id,
                "system_name": s.system_name,
                "ip_address": s.ip_address,
                "location": s.location,
                "registered_at": s.registered_at.strftime("%Y-%m-%d %H:%M:%S")
            }
            for s in systems
        ])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =======================================================
# 🔹 Fetch Metrics for a System
# =======================================================
@app.route("/api/metrics/<int:system_id>", methods=["GET"])
def get_metrics(system_id):
    try:
        metrics = SystemMetrics.query.filter_by(system_id=system_id).order_by(
            SystemMetrics.recorded_at.desc()
        ).limit(30).all()

        return jsonify([
            {
                "timestamp": m.recorded_at.strftime("%Y-%m-%d %H:%M:%S"),
                "cpu_usage": m.CPU_Usage,
                "memory_usage": m.Memory_Usage,
                "disk_io": m.Disk_IO,
                "network_latency": m.Network_Latency,
                "error_rate": m.Error_Rate,
            }
            for m in metrics
        ])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =======================================================
# 🔹 Fetch Prediction Logs
# =======================================================
@app.route("/api/predictions/<int:system_id>", methods=["GET"])
def get_predictions(system_id):
    try:
        preds = PredictionLog.query.filter_by(system_id=system_id).order_by(
            PredictionLog.created_at.desc()
        ).limit(30).all()

        return jsonify([
            {
                "prediction_id": p.prediction_id,
                "probability": p.probability,
                "downtime_risk": p.downtime_risk,
                "estimated_time_to_downtime": p.estimated_time_to_downtime,
                "predicted_at": p.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            }
            for p in preds
        ])
    except Exception as e:
        return jsonify({"error": str(e)}), 500
# =======================================================
# 🔹 Public Endpoint for Streamlit (Real-Time Metrics)
# =======================================================
@app.route("/api/predict", methods=["GET"])
def public_predict():
    """Return the most recent system metrics from DB instead of random simulation."""
    try:
        from database.models import SystemMetrics  # ensure correct import

        latest_metric = (
            db.session.query(SystemMetrics)
            .order_by(SystemMetrics.metric_id.desc())
            .first()
        )

        if not latest_metric:
            return jsonify({"error": "No metrics recorded yet"}), 404

        # Safely handle timestamp field (might be named differently)
        ts = None
        if hasattr(latest_metric, "timestamp"):
            ts = latest_metric.timestamp
        elif hasattr(latest_metric, "created_at"):
            ts = latest_metric.created_at
        elif hasattr(latest_metric, "recorded_at"):
            ts = latest_metric.recorded_at

        data = {
            "system_name": f"System {latest_metric.system_id}",
            "CPU_Usage": latest_metric.CPU_Usage,
            "Memory_Usage": latest_metric.Memory_Usage,
            "Disk_IO": latest_metric.Disk_IO,
            "Network_Latency": latest_metric.Network_Latency,
            "Error_Rate": latest_metric.Error_Rate,
            "Prediction": (
                "⚠ Downtime Risk" if latest_metric.Error_Rate > 3 else "✅ Normal Operation"
            ),
            "Risk_Probability": f"{min(latest_metric.Error_Rate * 20, 99.9):.2f}%",
            "Timestamp": ts.strftime("%Y-%m-%d %H:%M:%S") if ts else "N/A",
        }

        return jsonify(data), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =======================================================
# 🔹 Agent Fetch Unread Notifications
# =======================================================
@app.route("/api/notifications/<int:system_id>", methods=["GET"])
def fetch_notifications(system_id):
    """Agent polls this endpoint to get unread notifications."""
    try:
        unread = Notification.query.filter_by(system_id=system_id, status="Unread").all()

        notif_data = [
            {
                "notification_id": n.notification_id,
                "message": n.message,
                "risk_level": n.risk_level,
                "sent_time": n.sent_time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            for n in unread
        ]

        # Mark them as read
        for n in unread:
            n.status = "Read"
        db.session.commit()

        return jsonify({"notifications": notif_data}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# =======================================================
# 🔹 Watch Prediction Log for New Entries
# =======================================================
def watch_predictions():
    """Watches for new prediction_log rows and adds notifications automatically."""
    print("👀 Watching prediction_log for new entries...")
    last_seen_id = 0

    while True:
        try:
            with app.app_context():
                new_logs = PredictionLog.query.filter(
                    PredictionLog.prediction_id > last_seen_id
                ).order_by(PredictionLog.prediction_id.asc()).all()

                for log in new_logs:
                    system = SystemInfo.query.get(log.system_id)
                    if not system:
                        continue

                    prob = log.probability or 0.0

                    if prob >= 75:
                        risk_level = "High" if prob >= 85 else "Medium"
                        msg = (
                            f"⚠ {risk_level} Downtime Risk Detected for {system.system_name} "
                            f"({prob:.2f}%)"
                        )

                        exists = Notification.query.filter_by(
                            system_id=system.system_id, message=msg
                        ).first()

                        if not exists:
                            notif = Notification(
                                admin_id=system.admin_id,
                                system_id=system.system_id,
                                message=msg,
                                risk_level=risk_level,
                                status="Unread",
                            )
                            db.session.add(notif)
                            db.session.commit()

                            print(f"🚨 New Notification for {system.system_name} ({risk_level} Risk)")

                            try:
                                send_alert(system.system_id, msg)
                            except Exception:
                                pass

                    last_seen_id = log.prediction_id

        except Exception as e:
            print(f"⚠ Watcher Error: {e}")

        time.sleep(8)


# =======================================================
# 🚀 Run Flask Server
# =======================================================
if __name__ == "__main__":
    print("🧠 Registered Routes:")
    for rule in app.url_map.iter_rules():
        print(f"➡ {rule}")

    print("\n✅ Flask backend running at: http://0.0.0.0:5000\n")

    watcher_thread = threading.Thread(target=watch_predictions, daemon=True)
    watcher_thread.start()

    app.run(host="0.0.0.0", port=5000, debug=True)
