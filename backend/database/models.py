from datetime import datetime
from .db_config import db


# 👤 Admin Table
class Admin(db.Model):
    __tablename__ = "admin"

    admin_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    phone = db.Column(db.String(20))
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.TIMESTAMP, server_default=db.func.current_timestamp())

    systems = db.relationship("SystemInfo", back_populates="admin")
    notifications = db.relationship("Notification", back_populates="admin", cascade="all, delete")



# 💻 System Information
class SystemInfo(db.Model):
    __tablename__ = "system_info"

    system_id = db.Column(db.Integer, primary_key=True)
    system_name = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(150))
    ip_address = db.Column(db.String(50))
    admin_id = db.Column(db.Integer, db.ForeignKey("admin.admin_id"))
    registered_at = db.Column(db.TIMESTAMP, server_default=db.func.current_timestamp())

    # Relationships
    admin = db.relationship("Admin", back_populates="systems")
    metrics = db.relationship("SystemMetrics", back_populates="system", cascade="all, delete")
    predictions = db.relationship("PredictionLog", back_populates="system", cascade="all, delete")


# 📊 Real-Time Metrics
class SystemMetrics(db.Model):
    __tablename__ = "system_metrics"

    metric_id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    system_id = db.Column(db.Integer, db.ForeignKey("system_info.system_id"), nullable=False)

    CPU_Usage = db.Column(db.Float, nullable=False)
    Memory_Usage = db.Column(db.Float, nullable=False)
    Disk_IO = db.Column(db.BigInteger, nullable=False)
    Network_Latency = db.Column(db.Float, nullable=False)
    Error_Rate = db.Column(db.Float, nullable=False)

    recorded_at = db.Column("timestamp", db.DateTime, default=datetime.utcnow)

    system = db.relationship("SystemInfo", back_populates="metrics")


# 🤖 Prediction Log
class PredictionLog(db.Model):
    __tablename__ = "prediction_log"

    prediction_id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    system_id = db.Column(db.Integer, db.ForeignKey("system_info.system_id"), nullable=False)
    predicted_at = db.Column(db.TIMESTAMP, server_default=db.func.current_timestamp())

    downtime_risk = db.Column(db.Boolean, nullable=False)
    probability = db.Column(db.Float)
    estimated_time_to_downtime = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    system = db.relationship("SystemInfo", back_populates="predictions")

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
    
# 🔔 Notifications Table
class Notification(db.Model):
    __tablename__ = "notifications"

    notification_id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    admin_id = db.Column(db.Integer, db.ForeignKey("admin.admin_id"), nullable=False)
    system_id = db.Column(db.Integer, db.ForeignKey("system_info.system_id"), nullable=False)
    message = db.Column(db.Text, nullable=False)
    risk_level = db.Column(db.Enum('Low', 'Medium', 'High'), default='Low')
    sent_time = db.Column(db.TIMESTAMP, server_default=db.func.current_timestamp())
    status = db.Column(db.Enum('Unread', 'Read'), default='Unread')

    # Optional relationships
    admin = db.relationship("Admin", back_populates="notifications", lazy=True)
    system = db.relationship("SystemInfo", lazy=True)

    def __repr__(self):
        return f"<Notification {self.notification_id} - {self.message[:30]}>"
