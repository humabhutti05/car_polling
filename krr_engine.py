# krr_engine.py  — Knowledge Representation & Reasoning Engine
# Production Rules:
#   R1: Jaccard(A,B) >= 0.95  → PERFECT match
#   R2: Jaccard(A,B) >= 0.70  → PARTIAL match
#   R3: Jaccard(A,B) <  0.70  → REJECT
#   R4: Time gap <= 30 min    → time compatible
#   R5: seats > 0             → seat available
#   R6: driver accepts        → CONFIRMED
#   R7: seats == 0            → FULL
#   R8: gender preference clash → BLOCK
#   R9: time gap > 30 min     → penalise score by 0.20

from datetime import datetime

# ── Jaccard Similarity Formula ─────────────────────────────────────────────
def jaccard_similarity(set_a: set, set_b: set) -> float:
    """
    J(A,B) = |A ∩ B| / |A ∪ B|
    Returns float 0.0 – 1.0
    """
    if not set_a and not set_b:
        return 1.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0

def route_to_set(start: str, end: str, waypoints: str) -> set:
    """Convert a route into a set of location tokens for Jaccard."""
    tokens = {start.strip().lower(), end.strip().lower()}
    if waypoints and waypoints.strip():
        for w in waypoints.split(','):
            tokens.add(w.strip().lower())
    return tokens

def parse_time(t: str) -> datetime:
    try:
        return datetime.strptime(t.strip(), "%H:%M")
    except Exception:
        return datetime.strptime("00:00", "%H:%M")

def time_gap_minutes(t1: str, t2: str) -> int:
    a = parse_time(t1)
    b = parse_time(t2)
    return abs(int((b - a).total_seconds() / 60))

# ── Production Rules ────────────────────────────────────────────────────────
def apply_rules(driver: dict, passenger: dict) -> dict:
    """
    Apply all KRR production rules.
    Returns a result dict with score, rule_fired, status, explanation.
    """
    result = {
        "driver_id": driver["user_id"],
        "driver_name": driver["name"],
        "passenger_id": passenger["user_id"],
        "passenger_name": passenger["name"],
        "jaccard_score": 0.0,
        "time_gap_min": 0,
        "rule_fired": "",
        "status": "UNKNOWN",
        "explanation": [],
        "seats_available": int(driver.get("available_seats", 0)),
    }

    # Build route sets
    d_set = route_to_set(driver["start_location"], driver["end_location"], driver.get("waypoints", ""))
    p_set = route_to_set(passenger["start_location"], passenger["end_location"], passenger.get("waypoints", ""))

    # ── R8: Gender preference constraint ───────────────────────────────────
    pref = passenger.get("preference", "any").strip().lower()
    d_gender = driver.get("gender", "any").strip().lower()
    if pref == "female-only" and d_gender != "female":
        result["rule_fired"] = "R8"
        result["status"] = "BLOCKED"
        result["explanation"].append("R8 fired: Passenger prefers female-only driver — gender mismatch blocked.")
        return result

    # ── R1/R2/R3: Jaccard route similarity ────────────────────────────────
    score = jaccard_similarity(d_set, p_set)
    result["jaccard_score"] = round(score, 4)
    result["explanation"].append(
        f"Jaccard J(A,B) = |A∩B|/|A∪B| = {len(d_set & p_set)}/{len(d_set | p_set)} = {score:.4f}"
    )

    # ── R3: Reject if < 0.70 ──────────────────────────────────────────────
    if score < 0.70:
        result["rule_fired"] = "R3"
        result["status"] = "REJECTED"
        result["explanation"].append(f"R3 fired: score {score:.2f} < 0.70 threshold → no match.")
        return result

    # ── R4/R9: Time window check ───────────────────────────────────────────
    gap = time_gap_minutes(driver["departure_time"], passenger["departure_time"])
    result["time_gap_min"] = gap

    if gap > 30:
        score -= 0.20
        score = max(0.0, round(score, 4))
        result["jaccard_score"] = score
        result["explanation"].append(
            f"R9 fired: time gap {gap} min > 30 min → score penalised by 0.20 → new score {score:.4f}"
        )
    else:
        result["explanation"].append(f"R4 satisfied: time gap {gap} min ≤ 30 min → time compatible.")

    # Re-check threshold after penalty
    if score < 0.70:
        result["rule_fired"] = "R3+R9"
        result["status"] = "REJECTED"
        result["explanation"].append("After R9 penalty score dropped below 0.70 → rejected.")
        return result

    # ── R7: Seat availability ──────────────────────────────────────────────
    seats = int(driver.get("available_seats", 0))
    if seats <= 0:
        result["rule_fired"] = "R7"
        result["status"] = "FULL"
        result["explanation"].append("R7 fired: driver has 0 seats available → ride FULL.")
        return result

    result["explanation"].append(f"R5 satisfied: {seats} seat(s) available.")

    # ── R1 vs R2: Classify match quality ─────────────────────────────────
    if score >= 0.95:
        result["rule_fired"] = "R1"
        result["status"] = "PERFECT_MATCH"
        result["explanation"].append(f"R1 fired: score {score:.2f} ≥ 0.95 → PERFECT match.")
    else:
        result["rule_fired"] = "R2"
        result["status"] = "PARTIAL_MATCH"
        result["explanation"].append(f"R2 fired: score {score:.2f} ≥ 0.70 → PARTIAL match.")

    return result

# ── Forward Chaining Engine ─────────────────────────────────────────────────
def forward_chain(drivers: list, passengers: list) -> list:
    """
    Run forward chaining: for every (driver, passenger) pair, apply all rules.
    Returns list of match results sorted by jaccard_score descending.
    """
    matches = []
    for d in drivers:
        for p in passengers:
            res = apply_rules(d, p)
            matches.append(res)
    # Sort: PERFECT first, then PARTIAL, then rest
    priority = {"PERFECT_MATCH": 0, "PARTIAL_MATCH": 1, "REJECTED": 2, "FULL": 3, "BLOCKED": 4, "UNKNOWN": 5}
    matches.sort(key=lambda x: (priority.get(x["status"], 9), -x["jaccard_score"]))
    return matches
