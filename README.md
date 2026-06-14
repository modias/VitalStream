# VitalStream
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
