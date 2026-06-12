#!/usr/bin/env python3
"""Stream cleaned ICU vitals from CSV into Kafka."""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
import time
from pathlib import Path

from confluent_kafka import Producer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

DEFAULT_TOPIC = "vitals"
DEFAULT_BOOTSTRAP = "localhost:9092"
DEFAULT_DELAY = 0.05  # seconds between rows (~20 vitals/sec)


def delivery_report(err, msg) -> None:
    if err is not None:
        logger.error("Delivery failed: %s", err)
    else:
        logger.debug(
            "Delivered to %s [%s] @ %s",
            msg.topic(),
            msg.partition(),
            msg.offset(),
        )


def resolve_csv_path(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()

    env_path = os.getenv("VITALS_CSV_PATH")
    if env_path:
        return Path(env_path).expanduser().resolve()

    repo_root = Path(__file__).resolve().parents[1]
    return repo_root / "data" / "vitals_clean.csv"


def stream_vitals(
    csv_path: Path,
    bootstrap_servers: str,
    topic: str,
    delay_seconds: float,
    loop: bool,
) -> None:
    if not csv_path.is_file():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    producer = Producer(
        {
            "bootstrap.servers": bootstrap_servers,
            "client.id": "vitalstream-producer",
            "acks": "all",
        }
    )

    logger.info(
        "Streaming %s -> topic=%s @ %s (delay=%.2fs, loop=%s)",
        csv_path,
        topic,
        bootstrap_servers,
        delay_seconds,
        loop,
    )

    sent = 0
    while True:
        with csv_path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                payload = {
                    "patient_id": row["patient_id"],
                    "timestamp": row["timestamp"],
                    "vital_sign": row["vital_sign"],
                    "value": float(row["value"]),
                }

                producer.produce(
                    topic=topic,
                    key=str(payload["patient_id"]).encode("utf-8"),
                    value=json.dumps(payload).encode("utf-8"),
                    on_delivery=delivery_report,
                )
                producer.poll(0)
                sent += 1

                if sent % 500 == 0:
                    logger.info("Sent %s messages", sent)

                if delay_seconds > 0:
                    time.sleep(delay_seconds)

        producer.flush()
        logger.info("Finished pass (%s messages total)", sent)

        if not loop:
            break

        logger.info("Looping CSV from the beginning...")
        sent = 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stream vitals CSV rows into Kafka."
    )
    parser.add_argument(
        "--csv",
        default=None,
        help="Path to vitals_clean.csv (default: data/vitals_clean.csv)",
    )
    parser.add_argument(
        "--bootstrap-servers",
        default=os.getenv("KAFKA_BOOTSTRAP_SERVERS", DEFAULT_BOOTSTRAP),
        help=f"Kafka bootstrap servers (default: {DEFAULT_BOOTSTRAP})",
    )
    parser.add_argument(
        "--topic",
        default=os.getenv("KAFKA_TOPIC", DEFAULT_TOPIC),
        help=f"Kafka topic name (default: {DEFAULT_TOPIC})",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=float(os.getenv("PRODUCER_DELAY_SECONDS", DEFAULT_DELAY)),
        help=f"Seconds between rows (default: {DEFAULT_DELAY})",
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Restart from top of CSV when finished (good for demos)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    csv_path = resolve_csv_path(args.csv)

    try:
        stream_vitals(
            csv_path=csv_path,
            bootstrap_servers=args.bootstrap_servers,
            topic=args.topic,
            delay_seconds=args.delay,
            loop=args.loop,
        )
    except KeyboardInterrupt:
        logger.info("Stopped by user")
        return 0
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())