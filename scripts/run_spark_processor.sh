#!/usr/bin/env bash
# Run the Spark NEWS2 processor with a local Java install (no Homebrew required).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
JAVA_HOME="${JAVA_HOME:-$HOME/.local/java/jdk-17.0.19+10/Contents/Home}"
export JAVA_HOME
export PATH="$JAVA_HOME/bin:$PATH"

if [[ ! -x "$JAVA_HOME/bin/java" ]]; then
  echo "Java not found at $JAVA_HOME"
  echo "Install with: curl -L -o ~/.local/java/jdk17.tar.gz \\"
  echo "  'https://api.adoptium.net/v3/binary/latest/17/ga/mac/aarch64/jdk/hotspot/normal/eclipse?project=jdk'"
  echo "  && tar -xzf ~/.local/java/jdk17.tar.gz -C ~/.local/java"
  exit 1
fi

echo "Using Java: $($JAVA_HOME/bin/java -version 2>&1 | head -1)"
exec /usr/local/bin/python3 "$ROOT/processor/spark_processor.py" "$@"
