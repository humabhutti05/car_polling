# Car Pooling System — KRR (Knowledge Representation & Reasoning)

## Production Rules & Formulas

### Jaccard Similarity (Route Matching)
```
J(A, B) = |A ∩ B| / |A ∪ B|

Where:
  A = set of tokens from Driver's route   (start, end, waypoints)
  B = set of tokens from Passenger's route
  Result: 0.0 (no overlap) to 1.0 (identical)
```

### Time Gap Formula
```
gap = |departure_time_driver − departure_time_passenger|  (minutes)
```

### All 9 Production Rules
| Rule | IF                                 | THEN                          |
|------|------------------------------------|-------------------------------|
| R1   | J(A,B) ≥ 0.95                      | PERFECT_MATCH                 |
| R2   | 0.70 ≤ J(A,B) < 0.95              | PARTIAL_MATCH                 |
| R3   | J(A,B) < 0.70                      | REJECT                        |
| R4   | gap ≤ 30 min                       | Time compatible               |
| R5   | availableSeats > 0                 | Seat OK → create Request      |
| R6   | driver.acceptsRequest = TRUE       | Ride CONFIRMED, seats −= 1   |
| R7   | availableSeats = 0                 | FULL                          |
| R8   | passenger.preference=female-only AND driver.gender≠female | BLOCKED |
| R9   | gap > 30 min                       | score −= 0.20 (penalty)       |

---

## How to Run

### Requirements
```
Python 3.8+
Flask
Pandas
```

### Install
```bash
pip install flask pandas
```

### Run
```bash
cd carpooling_krr
python app.py
```

Open browser: http://localhost:5050

---

## File Structure
```
carpooling_krr/
├── app.py            ← Flask web server
├── krr_engine.py     ← KRR rules engine (Jaccard + all 9 rules)
├── dataset.csv       ← Kaggle-style dataset (20 Karachi users)
├── requirements.txt  ← Dependencies
└── templates/
    └── index.html    ← Full web UI
```

---

## Dataset (Kaggle-style)
- 20 users (10 drivers, 10 passengers)
- Karachi city routes
- Fields: user_id, name, role, start_location, end_location, departure_time, available_seats, waypoints, gender, preference

## Kaggle Dataset Reference
This dataset is modeled after:
https://www.kaggle.com/datasets/khaledelsayedali/carpooling-route-dataset

---

## KRR Concepts Used
- **Ontology**: User → Driver / Passenger, Route, Location, Ride, Request
- **Knowledge Base**: dataset.csv + in-memory facts
- **Inference Engine**: Forward Chaining (all pairs) + rule application
- **Production Rules**: 9 IF-THEN rules
- **Jaccard Similarity**: Route overlap formula
