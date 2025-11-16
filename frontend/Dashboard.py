import streamlit as st
import pandas as pd
import requests
import time

# ======================================================
# ⚙️ Configuration
# ======================================================
API_BASE = "http://192.168.0.130:5000"  # 👈 backend Flask IP
LOGIN_API = f"{API_BASE}/api/login"
REGISTER_API = f"{API_BASE}/api/register"
PREDICT_API = f"{API_BASE}/api/predict"  # fixed endpoint
NOTIFICATIONS_API = f"{API_BASE}/api/notifications"
REFRESH_INTERVAL = 10  # seconds


# ======================================================
# 🧩 Initialize Session State
# ======================================================
def init_session():
    defaults = {
        "is_logged_in": False,
        "admin_id": None,
        "admin_name": None,
        "auto_refresh": True,
        "show_register": False,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


# ======================================================
# 🔹 Helper: Fetch Data from Backend
# ======================================================
def fetch_json(url, method="GET", payload=None):
    try:
        if method == "POST":
            res = requests.post(url, json=payload, timeout=10)
        else:
            res = requests.get(url, timeout=10)

        if res.status_code == 200:
            return res.json()
        else:
            st.warning(f"⚠️ API error: {res.status_code}")
            return None
    except Exception as e:
        st.error(f"❌ Connection error: {e}")
        return None


# ======================================================
# 🧾 Registration Page
# ======================================================
def admin_register():
    st.title("🆕 Admin Registration")
    name = st.text_input("Name")
    email = st.text_input("Email")
    phone = st.text_input("Phone")
    password = st.text_input("Password", type="password")
    system_name = st.text_input("System Name")

    if st.button("Register"):
        if not all([name, email, phone, password, system_name]):
            st.error("Please fill all fields.")
            return

        payload = {
            "name": name,
            "email": email,
            "phone": phone,
            "password": password,
            "system_name": system_name,
        }
        res = fetch_json(REGISTER_API, "POST", payload)
        if res and "message" in res:
            st.success("✅ Registration successful! You can now log in.")
            st.session_state.show_register = False
            time.sleep(1)
            st.rerun()
        else:
            st.error("❌ Registration failed. Try again.")


# ======================================================
# 🔐 Login Page
# ======================================================
def admin_login():
    st.title("🔑 Admin Login")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button("Login"):
            if not email or not password:
                st.warning("Please enter both email and password.")
                return
            res = fetch_json(LOGIN_API, "POST", {"email": email, "password": password})
            if res and "admin_id" in res:
                st.session_state.is_logged_in = True
                st.session_state.admin_id = res["admin_id"]
                st.session_state.admin_name = res["name"]
                st.success("✅ Login successful!")
                time.sleep(1)
                st.rerun()
            else:
                st.error("❌ Invalid email or password.")

    with c2:
        if st.button("Register Instead"):
            st.session_state.show_register = True
            st.rerun()


# ======================================================
# 🧠 Admin Dashboard
# ======================================================
def admin_dashboard():
    st.title(f"👋 Welcome, {st.session_state.admin_name}")
    st.subheader("📡 Real-Time System Monitoring")

    # Fetch prediction data from backend
    pred_data = fetch_json(PREDICT_API)
    if not pred_data:
        st.warning("Backend not responding or system inactive.")
        return

    # === Metrics Display ===
    c1, c2, c3 = st.columns(3)
    c1.metric("💻 CPU Usage", f"{pred_data['CPU_Usage']}%")
    c2.metric("🧠 Memory Usage", f"{pred_data['Memory_Usage']}%")
    c3.metric("💾 Disk I/O", f"{pred_data['Disk_IO']}%")

    c4, c5 = st.columns(2)
    c4.metric("📡 Network Latency", f"{pred_data['Network_Latency']} ms")
    c5.metric("❌ Error Rate", f"{pred_data['Error_Rate']:.2f}")

    risk_color = "🔴" if "⚠" in pred_data["Prediction"] else "🟢"
    st.markdown(f"### Current Status: {risk_color} {pred_data['Prediction']}")
    st.markdown(f"**Risk Probability:** {pred_data['Risk_Probability']}")

    st.markdown("---")

    # === Notification Fetch ===
    st.subheader("📢 Recent Notifications")
    notif_data = fetch_json(f"{NOTIFICATIONS_API}/1")  # admin ID placeholder
    if notif_data and notif_data.get("notifications"):
        for n in notif_data["notifications"][-10:][::-1]:
            risk = n["risk_level"]
            color = "red" if risk == "High" else "orange" if risk == "Medium" else "green"
            st.markdown(
                f"""
                <div style="border-left:6px solid {color};padding:8px 12px;margin-bottom:6px;border-radius:6px;">
                    <b style='color:{color};'>{n['message']}</b><br>
                    <small>🕒 {n['sent_time']}</small>
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.info("✅ No new notifications.")

    st.markdown("---")
    st.info(f"🔄 Auto-refresh every {REFRESH_INTERVAL}s")
    if st.session_state.auto_refresh:
        time.sleep(REFRESH_INTERVAL)
        st.rerun()


# ======================================================
# 🚀 Main Function
# ======================================================
def main():
    st.set_page_config(page_title="Predictive Maintenance Dashboard", layout="wide")
    init_session()

    with st.sidebar:
        st.title("🧭 Navigation")
        st.session_state.auto_refresh = st.checkbox("Auto Refresh", True)

        if st.session_state.is_logged_in:
            st.success(f"Logged in as {st.session_state.admin_name}")
            if st.button("Logout"):
                for key in ["is_logged_in", "admin_id", "admin_name"]:
                    st.session_state[key] = None
                st.session_state.is_logged_in = False
                st.success("👋 Logged out successfully!")
                time.sleep(0.8)
                st.rerun()
        else:
            if st.session_state.show_register:
                admin_register()
            else:
                admin_login()

    if st.session_state.is_logged_in:
        admin_dashboard()
    else:
        if not st.session_state.show_register:
            st.title("🧠 Predictive Maintenance Dashboard")
            st.markdown("Monitor CPU, Memory, Disk, and Predict System Failures in Real-Time 🚀")
            st.info("Login or Register to continue.")


# ======================================================
# 🏁 Entry Point
# ======================================================
if __name__ == "__main__":
    main()
