# app.py — Car Pooling KRR System (Flask)
import pandas as pd
from flask import Flask, render_template, request, jsonify
from krr_engine import forward_chain, apply_rules, route_to_set, jaccard_similarity, time_gap_minutes
import json, os
from datetime import datetime

app = Flask(__name__, static_url_path='', static_folder='static')
app.secret_key = "sawaari_super_secret_key_123"
DATASET_PATH = os.path.join(os.path.dirname(__file__), "dataset.csv")
RIDES_PATH = os.path.join(os.path.dirname(__file__), "rides.csv")

# ── Load dataset ────────────────────────────────────────────────────────────
def load_data():
    df = pd.read_csv(DATASET_PATH)
    df.fillna("", inplace=True)
    # Ensure all required columns exist
    if 'password' not in df.columns: df['password'] = '123456'
    df["available_seats"] = pd.to_numeric(df["available_seats"], errors='coerce').fillna(0).astype(int)
    return df.to_dict(orient="records")

# In-memory knowledge base (sessions only)
knowledge_base = load_data()

from flask import session, redirect, url_for

@app.route("/")
def index():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    return render_template("index.html", user=session.get('user_name'))

@app.route("/login")
def login_page():
    return render_template("login.html")

@app.route("/api/login", methods=["POST"])
def login_api():
    data = request.json
    users = load_data()
    user = next((u for u in users if u['name'] == data['name'] and str(u['password']) == str(data['password'])), None)
    
    if user:
        session['user_id'] = user['user_id']
        session['user_name'] = user['name']
        session['role'] = user['role']
        return jsonify({"success": True, "user": user})
    return jsonify({"success": False, "message": "Invalid credentials"})

@app.route("/api/signup", methods=["POST"])
def signup_api():
    data = request.json
    users = load_data()
    
    if any(u['name'] == data['name'] for u in users):
        return jsonify({"success": False, "message": "User already exists"})
        
    uid = f"U{len(users)+1:03d}"
    data["user_id"] = uid
    if "available_seats" not in data: data["available_seats"] = 0
    
    try:
        cols = ["user_id", "name", "role", "start_location", "end_location", "departure_time", "available_seats", "waypoints", "gender", "preference", "password"]
        # Ensure all cols are in data
        for c in cols: 
            if c not in data: data[c] = ""
            
        new_row = pd.DataFrame([data])[cols]
        new_row.to_csv(DATASET_PATH, mode='a', header=False, index=False)
        
        session['user_id'] = uid
        session['user_name'] = data['name']
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('login_page'))

@app.route("/admin")
def admin():
    return render_template("admin.html")

@app.route("/api/users")
def get_users():
    return jsonify(knowledge_base)

@app.route("/api/match", methods=["POST"])
def match():
    data = request.json
    role = data.get("role")
    start = data.get("start_location", "").strip()
    end   = data.get("end_location", "").strip()
    dep   = data.get("departure_time", "08:00").strip()
    wayp  = data.get("waypoints", "").strip()
    gender = data.get("gender", "male").strip()
    pref   = data.get("preference", "any").strip()
    seats  = int(data.get("available_seats", 0))
    name   = data.get("name", "You").strip()

    user = {
        "user_id": "QUERY",
        "name": name,
        "role": role,
        "start_location": start,
        "end_location": end,
        "departure_time": dep,
        "waypoints": wayp,
        "gender": gender,
        "preference": pref,
        "available_seats": seats,
    }

    if role == "passenger":
        drivers = [u for u in knowledge_base if u["role"] == "driver"]
        results = []
        for d in drivers:
            res = apply_rules(d, user)
            results.append(res)
    else:
        passengers = [u for u in knowledge_base if u["role"] == "passenger"]
        results = []
        for p in passengers:
            res = apply_rules(user, p)
            results.append(res)

    # Sort
    priority = {"PERFECT_MATCH": 0, "PARTIAL_MATCH": 1, "REJECTED": 2, "FULL": 3, "BLOCKED": 4}
    results.sort(key=lambda x: (priority.get(x["status"], 9), -x["jaccard_score"]))
    return jsonify(results)

@app.route("/api/full_match")
def full_match():
    """Run forward chaining on all driver-passenger pairs in dataset."""
    drivers    = [u for u in knowledge_base if u["role"] == "driver"]
    passengers = [u for u in knowledge_base if u["role"] == "passenger"]
    results = forward_chain(drivers, passengers)
    return jsonify(results)

@app.route("/api/add_user", methods=["POST"])
def add_user():
    data = request.json
    # Check if user already exists (by name and role for simplicity)
    existing = [u for u in knowledge_base if u["name"] == data["name"] and u["role"] == data["role"]]
    if existing:
        return jsonify({"success": True, "user_id": existing[0]["user_id"], "note": "Existing user used"})

    uid = f"U{len(knowledge_base)+1:03d}"
    data["user_id"] = uid
    knowledge_base.append(data)
    
    # Persist to CSV with correct column order
    try:
        cols = ["user_id", "name", "role", "start_location", "end_location", "departure_time", "available_seats", "waypoints", "gender", "preference", "password"]
        new_row = pd.DataFrame([data])[cols]
        new_row.to_csv(DATASET_PATH, mode='a', header=False, index=False)
    except Exception as e:
        print(f"Error saving to CSV: {e}")
        
    return jsonify({"success": True, "user_id": uid})

@app.route("/api/book", methods=["POST"])
def book_ride():
    data = request.json
    ride_id = f"R{len(pd.read_csv(RIDES_PATH))+1:03d}"
    
    # Calculate mock fare and profit (10%)
    fare = 500 # Default
    profit = fare * 0.1
    
    new_ride = {
        "ride_id": ride_id,
        "driver_id": data.get("driver_id"),
        "driver_name": data.get("driver_name"),
        "passenger_id": data.get("passenger_id", "GUEST"),
        "passenger_name": data.get("passenger_name", "Guest"),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "fare": fare,
        "profit": profit
    }
    
    try:
        pd.DataFrame([new_ride]).to_csv(RIDES_PATH, mode='a', header=False, index=False)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})
        
    return jsonify({"success": True, "ride_id": ride_id})

@app.route("/api/admin/history")
def admin_history():
    df = pd.read_csv(RIDES_PATH)
    return jsonify(df.to_dict(orient="records"))

@app.route("/api/admin/stats")
def admin_stats():
    df = pd.read_csv(RIDES_PATH)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Group by month and sort chronologically
    df['month_num'] = df['timestamp'].dt.month
    df['month_name'] = df['timestamp'].dt.strftime('%b')
    
    monthly = df.groupby(['month_num', 'month_name']).agg({'ride_id': 'count', 'profit': 'sum'}).reset_index()
    monthly = monthly.sort_values('month_num')
    
    return jsonify({
        "months": monthly['month_name'].tolist(),
        "rides": [int(x) for x in monthly['ride_id'].tolist()],
        "profits": [float(x) for x in monthly['profit'].tolist()],
        "total_rides": int(len(df)),
        "total_profit": float(df['profit'].sum())
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port)
