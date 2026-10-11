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

# Search common locations for the dataset
data_path = Path(__file__).resolve().parent.parent / "q-vercel-latency.json"
if not data_path.exists():
    data_path = Path(__file__).resolve().parent / "q-vercel-latency.json"
if not data_path.exists():
    data_path = Path("q-vercel-latency.json")

try:
    with open(data_path, "r", encoding="utf-8") as f:
        TELEMETRY_DATA = json.load(f)
        if isinstance(TELEMETRY_DATA, dict):
            # In case records are nested under a key
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
    response = {}
    for region in req.regions:
        records = [r for r in TELEMETRY_DATA if r.get("region") == region]
        if not records:
            continue

        latencies = [float(r.get("latency", 0)) for r in records]
        uptimes = [float(r.get("uptime", 0)) for r in records]

        response[region] = {
            "avg_latency": float(np.mean(latencies)),
            "p95_latency": float(np.percentile(latencies, 95)),
            "avg_uptime": float(np.mean(uptimes)),
            "breaches": sum(1 for lat in latencies if lat > req.threshold_ms),
        }
    return response
