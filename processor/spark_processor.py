#!/usr/bin/env python3
"""NEWS2 scoring engine: read vitals from Kafka, compute scores in Spark."""

import os
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, from_json, window, max as spark_max, when, lit
)
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType
)

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
INPUT_TOPIC = os.getenv("KAFKA_INPUT_TOPIC", "vitals")

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "vitalstream")
POSTGRES_USER = os.getenv("POSTGRES_USER", "vitalstream")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "vitalstream")
POSTGRES_TABLE = "vitals_scores"

JDBC_PACKAGES = (
    "org.apache.spark:spark-sql-kafka-0-10_2.13:4.1.2,"
    "org.postgresql:postgresql:42.7.3"
)

VITAL_SCHEMA = StructType([
    StructField("patient_id", StringType()),
    StructField("timestamp", StringType()),
    StructField("vital_sign", StringType()),
    StructField("value", DoubleType()),
])


def build_spark() -> SparkSession:
    return (
        SparkSession.builder
        .appName("VitalStream-NEWS2")
        .config("spark.jars.packages", JDBC_PACKAGES)
        .getOrCreate()
    )


def score_respiratory_rate(rr):
    return (
        when(rr <= 8, 3)
        .when((rr >= 9) & (rr <= 11), 1)
        .when((rr >= 12) & (rr <= 20), 0)
        .when((rr >= 21) & (rr <= 24), 2)
        .otherwise(3)
    )


def score_spo2(spo2):
    return (
        when(spo2 <= 91, 3)
        .when((spo2 >= 92) & (spo2 <= 93), 2)
        .when((spo2 >= 94) & (spo2 <= 95), 1)
        .otherwise(0)
    )


def score_systolic_bp(bp):
    return (
        when(bp <= 90, 3)
        .when((bp >= 91) & (bp <= 100), 2)
        .when((bp >= 101) & (bp <= 110), 1)
        .when((bp >= 111) & (bp <= 219), 0)
        .otherwise(3)
    )


def score_heart_rate(hr):
    return (
        when(hr <= 40, 3)
        .when((hr >= 41) & (hr <= 50), 1)
        .when((hr >= 51) & (hr <= 90), 0)
        .when((hr >= 91) & (hr <= 110), 1)
        .when((hr >= 111) & (hr <= 130), 2)
        .otherwise(3)
    )


def score_temperature(temp):
    return (
        when(temp <= 35.0, 3)
        .when((temp >= 35.1) & (temp <= 36.0), 1)
        .when((temp >= 36.1) & (temp <= 38.0), 0)
        .when((temp >= 38.1) & (temp <= 39.0), 1)
        .otherwise(2)
    )


def risk_level(score_col):
    return (
        when(score_col <= 4, lit("LOW"))
        .when(score_col <= 6, lit("MEDIUM"))
        .otherwise(lit("HIGH"))
    )


def jdbc_url() -> str:
    return (
        f"jdbc:postgresql://{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    )


def write_batch(batch_df, batch_id: int) -> None:
    if batch_df.isEmpty():
        return

    batch_df.show(truncate=False)

    (
        batch_df.write
        .format("jdbc")
        .option("url", jdbc_url())
        .option("dbtable", POSTGRES_TABLE)
        .option("user", POSTGRES_USER)
        .option("password", POSTGRES_PASSWORD)
        .option("driver", "org.postgresql.Driver")
        .mode("append")
        .save()
    )


def main():
    spark = build_spark()
    spark.sparkContext.setLogLevel("WARN")

    raw = (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP)
        .option("subscribe", INPUT_TOPIC)
        .option("startingOffsets", "latest")
        .load()
    )

    vitals = (
        raw
        .select(from_json(col("value").cast("string"), VITAL_SCHEMA).alias("v"))
        .select("v.*")
        .withColumn("event_time", col("timestamp").cast("timestamp"))
    )

    windowed = (
        vitals
        .withWatermark("event_time", "10 minutes")
        .groupBy(
            window(col("event_time"), "5 minutes"),
            col("patient_id"),
        )
        .pivot("vital_sign", [
            "heart_rate", "respiratory_rate", "spo2", "systolic_bp", "temperature"
        ])
        .agg(spark_max("value"))
    )

    scored = (
        windowed
        .withColumn("rr_score", score_respiratory_rate(col("respiratory_rate")))
        .withColumn("spo2_score", score_spo2(col("spo2")))
        .withColumn("bp_score", score_systolic_bp(col("systolic_bp")))
        .withColumn("hr_score", score_heart_rate(col("heart_rate")))
        .withColumn("temp_score", score_temperature(col("temperature")))
        .withColumn(
            "news2_score",
            col("rr_score") + col("spo2_score") + col("bp_score")
            + col("hr_score") + col("temp_score")
        )
        .withColumn("risk_level", risk_level(col("news2_score")))
        .select(
            col("patient_id").cast("integer").alias("patient_id"),
            col("window.start").alias("window_start"),
            col("news2_score"),
            col("risk_level"),
            col("heart_rate"),
            col("respiratory_rate"),
            col("spo2"),
            col("systolic_bp"),
            col("temperature"),
        )
    )

    query = (
        scored.writeStream
        .outputMode("append")
        .foreachBatch(write_batch)
        .start()
    )

    query.awaitTermination()


if __name__ == "__main__":
    main()
