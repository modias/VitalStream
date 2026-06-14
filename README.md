# VitalStream 
# VitalStream

Real-time ICU patient monitoring system that streams patient vital signs through Apache Kafka, computes clinical risk scores using Apache Spark, stores results in PostgreSQL, and displays a live ward dashboard with a FastAPI backend and Streamlit frontend.

---

## What Is This Project?

VitalStream simulates a hospital ICU monitoring pipeline. Vital signs (heart rate, respiratory rate, SpO₂, blood pressure, temperature) are read from a CSV file, pushed into Kafka in real time, processed by Spark to calculate **NEWS2** (National Early Warning Score 2) scores every 5 minutes, saved to a PostgreSQL database, and shown on a live Streamlit dashboard that nurses or clinicians can use to monitor patients.

The system supports **Demo mode** so you can run the dashboard with mock data without starting the full pipeline.

---

## How Does It Work?

### Step 1 — Data Source (CSV)

Vital signs live in a CSV file at `data/vitals_clean.csv` (this folder is gitignored). Each row contains:

- `patient_id` — patient identifier
- `timestamp` — when the reading was taken
- `vital_sign` — one of: `heart_rate`, `respiratory_rate`, `spo2`, `systolic_bp`, `temperature`
- `value` — numeric reading

### Step 2 — Kafka Producer

The producer (`producer/kafka_producer.py`) reads the CSV row by row and publishes each vital sign as a JSON message to the Kafka topic `vitals`. Messages are keyed by `patient_id` so all vitals for the same patient go to the same partition.

Default speed: one row every 0.05 seconds (~20 messages/sec). Use `--loop` to restart from the top of the CSV for continuous demos.



### Step 3 — Apache Kafka

Kafka (via Docker) receives and buffers the streaming messages. Zookeeper manages Kafka cluster state. The topic `vitals` holds all incoming vital sign events until Spark consumes them.

### Step 4 — Spark Processor (NEWS2 Scoring)

The Spark Structured Streaming job (`processor/spark_processor.py`) does the following:

1. Reads messages from the `vitals` Kafka topic
2. Parses JSON into structured columns
3. Groups vitals by **patient** and **5-minute time window**
4. Pivots each vital sign into its own column (heart rate, respiratory rate, etc.)
5. Scores each vital using the **NEWS2** clinical scoring rules
6. Sums individual scores into a total `news2_score`
7. Assigns a `risk_level`:
   - **LOW** — score ≤ 4
   - **MEDIUM** — score 5–6
   - **HIGH** — score ≥ 7
8. Writes each scored window to PostgreSQL table `vitals_scores`


Requires **Java 17**. The helper script sets `JAVA_HOME` automatically.

### Step 5 — PostgreSQL Database

PostgreSQL stores scored results in the `vitals_scores` table:

| Column | Type | Description |
|--------|------|-------------|
| patient_id | INTEGER | Patient ID |
| window_start | TIMESTAMP | Start of the 5-minute window |
| news2_score | INTEGER | Total NEWS2 score |
| risk_level | TEXT | LOW, MEDIUM, or HIGH |
| heart_rate | DOUBLE | Heart rate (bpm) |
| respiratory_rate | DOUBLE | Respiratory rate (/min) |
| spo2 | DOUBLE | Oxygen saturation (%) |
| systolic_bp | DOUBLE | Systolic blood pressure (mmHg) |
| temperature | DOUBLE | Body temperature (°C) |
| created_at | TIMESTAMP | When the row was inserted |


### Step 6 — FastAPI Backend

The backend (`backend/main.py`) exposes a REST API that reads from PostgreSQL and serves data to the dashboard.

Start it with:

```bash
uvicorn backend.main:app --reload --port 8000
```


### Step 7 — Streamlit Dashboard

The dashboard (`streamlit/app.py`) connects to the FastAPI backend and displays:

- **Ward View** — grid of patient cards showing NEWS2 score and risk level (color-coded: green = LOW, yellow = MEDIUM, red = HIGH with pulsing border)
- **Patient Detail** — click "View Details" to see 6-hour vitals history with interactive Altair charts
- **Problem Detection** — flags abnormal vitals (bradycardia, tachycardia, hypoxemia, hypotension, fever, etc.)
- **Auto-refresh** — ward view refreshes every 5 seconds



**Demo mode** is ON by default. It shows 3 mock patients (LOW, MEDIUM, HIGH risk) without needing the backend or pipeline. Turn it off in the sidebar to use live data.

---

## Architecture Diagram

```
┌─────────────────┐
│  vitals_clean   │
│     .csv        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Kafka Producer  │  producer/kafka_producer.py
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Apache Kafka   │  topic: vitals  (port 9092)
│  + Zookeeper    │                 (port 2181)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Spark Processor │  processor/spark_processor.py
│  (NEWS2 Score)  │  5-min windows, risk levels
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   PostgreSQL    │  table: vitals_scores  (port 5432)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  FastAPI Backend│  backend/main.py  (port 8000)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Streamlit    │  streamlit/app.py  (port 8501)
│   Dashboard     │
└─────────────────┘
```

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Message broker | Apache Kafka 7.5 (Confluent) |
| Stream processing | Apache Spark Structured Streaming (PySpark 3.5+) |
| Database | PostgreSQL 16 |
| API | FastAPI + Uvicorn |
| Dashboard | Streamlit + Altair + Pandas |
| Kafka client | confluent-kafka |
| DB driver | psycopg2 |
| Container
