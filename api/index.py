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

# Look for the dataset in current folder and parent folder
curr_dir = Path(__file__).resolve().parent
search_paths = [
    curr_dir / "q-vercel-latency.json",
    curr_dir.parent / "q-vercel-latency.json",
    Path("q-vercel-latency.json"),
    Path("api/q-vercel-latency.json"),
]

TELEMETRY_DATA = []
for p in search_paths:
    if p.exists():
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    TELEMETRY_DATA = data
                elif isinstance(data, dict):
                    for val in data.values():
                        if isinstance(val, list):
                            TELEMETRY_DATA = val
                            break
            if TELEMETRY_DATA:
                break
        except Exception:
            pass

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
        target = region.strip().lower()
        records = [
            r for r in TELEMETRY_DATA 
            if str(r.get("region", "")).strip().lower() == target
        ]

        if not records:
            continue

        latencies = [
            float(r["latency"] if "latency" in r else r.get("latency_ms", 0))
            for r in records
        ]
        uptimes = [
            float(r["uptime"] if "uptime" in r else r.get("uptime_pct", 0))
            for r in records
        ]

        region_metrics[region] = {
            "avg_latency": float(np.mean(latencies)),
            "p95_latency": float(np.percentile(latencies, 95)),
            "avg_uptime": float(np.mean(uptimes)),
            "breaches": sum(1 for lat in latencies if lat > req.threshold_ms),
        }

    return {
        "regions": region_metrics,
        **region_metrics,
    }
