import json
from pathlib import Path
from typing import List, Dict, Any
import numpy as np
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Locate the JSON file
data_path = Path(__file__).resolve().parent.parent / "q-vercel-latency.json"
if not data_path.exists():
    data_path = Path(__file__).resolve().parent / "q-vercel-latency.json"
if not data_path.exists():
    data_path = Path("q-vercel-latency.json")

try:
    with open(data_path, "r", encoding="utf-8") as f:
        TELEMETRY_DATA = json.load(f)
        if isinstance(TELEMETRY_DATA, dict):
            for val in TELEMETRY_DATA.values():
                if isinstance(val, list):
                    TELEMETRY_DATA = val
                    break
except Exception:
    TELEMETRY_DATA = []

class LatencyRequest(BaseModel):
    regions: List[str]
    threshold_ms: float

@app.options("/{full_path:path}")
def preflight_handler(full_path: str):
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        },
    )

@app.post("/api/latency")
@app.post("/")
def get_metrics(req: LatencyRequest):
    region_metrics = {}

    for region in req.regions:
        # Match region case-insensitively
        records = [
            r for r in TELEMETRY_DATA 
            if str(r.get("region", "")).lower() == region.lower()
        ]

        if not records:
            region_metrics[region] = {
                "avg_latency": 0.0,
                "p95_latency": 0.0,
                "avg_uptime": 0.0,
                "breaches": 0,
            }
            continue

        # Handle common field names for latency and uptime
        latencies = [
            float(r.get("latency") if r.get("latency") is not None else r.get("latency_ms", 0))
            for r in records
        ]
        uptimes = [
            float(r.get("uptime") if r.get("uptime") is not None else r.get("uptime_pct", 0))
            for r in records
        ]

        avg_lat = float(np.mean(latencies)) if latencies else 0.0
        p95_lat = float(np.percentile(latencies, 95)) if latencies else 0.0
        avg_upt = float(np.mean(uptimes)) if uptimes else 0.0
        breaches_count = sum(1 for lat in latencies if lat > req.threshold_ms)

        region_metrics[region] = {
            "region": region,
            "avg_latency": avg_lat,
            "p95_latency": p95_lat,
            "avg_uptime": avg_upt,
            "breaches": breaches_count,
        }

    # Return both a regions dictionary and a regions list to satisfy either schema
    return {
        "regions": region_metrics,
        **region_metrics,
    }
