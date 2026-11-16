#!/bin/bash
# usage: simrun.sh NAME  -> fresh database nativeflows_sim_NAME, dry LLM fixtures, logs/trace in build/runs/NAME.*
set -u
N=$1
export PGPASSWORD=lab
export NATIVEFLOWS_DOCS=${NATIVEFLOWS_DOCS:?set NATIVEFLOWS_DOCS to a docs directory}
export SIM_LLM=off
DB=nativeflows_sim_$N
PY=${PYTHON:-python3}
$PY - <<PYEOF
import psycopg
cx = psycopg.connect("host=127.0.0.1 port=5561 dbname=postgres user=lab password=lab", autocommit=True)
cx.execute("DROP DATABASE IF EXISTS $DB WITH (FORCE)")
cx.execute("CREATE DATABASE $DB")
PYEOF
export NATIVEFLOWS_SIM_DSN="host=127.0.0.1 port=5561 dbname=$DB user=lab password=lab"
cd "$(dirname "$0")"
$PY run_all.py > build/runs/$N.log 2>&1
rc=$?
cp trace/trace.json build/runs/$N.json
cp trace/trace.md build/runs/$N.md
echo "rc=$rc"
tail -45 build/runs/$N.log
