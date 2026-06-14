# VitalStream
VitalStream/
│
├── producer/
│   └── kafka_producer.py       # Reads CSV, publishes to Kafka
│
├── processor/
│   └── spark_processor.py      # Spark streaming NEWS2 scoring engine
│
├── backend/
│   ├── main.py                 # FastAPI app and API routes
│   ├── database/
│   │   ├── postgres.py         # PostgreSQL connection helper
│   │   ├── schema.sql          # Database table definition
│   │   └── redis_cache.py      # (planned) Redis caching
│   ├── routes/
│   │   ├── patients.py         # (planned) Patient route modules
│   │   └── alerts.py           # (planned) Alert route modules
│   └── services/
│       ├── alert_engine.py     # (planned) Clinical alert engine
│       ├── llm_analysis.py     # (planned) LLM-powered analysis
│       └── notification.py     # (planned) Alert notifications
│
├── streamlit/
│   ├── app.py                  # Main dashboard (ward view + patient detail)
│   ├── components/
│   │   └── vital_card.py       # Vital sign card component
│   └── pages/
│       ├── ward_view.py        # Ward view page (stub)
│       └── patient_detail.py   # Patient detail page (stub)
│
├── docker/
│   └── Docker-compose.yml      # Kafka, Zookeeper, PostgreSQL containers
│
├── scripts/
│   └── run_spark_processor.sh  # Runs Spark processor with Java 17
│
├── data/                       # Local vitals CSV (gitignored)
│   └── vitals_clean.csv        # Place your data here
│
├── requirements.txt            # Python dependencies
├── .gitignore
└── README.md
