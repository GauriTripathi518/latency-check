import json
from pathlib import Path
from typing import List, Dict, Any
import numpy as np
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

# Enable CORS for all incoming requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load the data file from the repository
data_path = Path(__file__).resolve().parent.parent / "q-vercel-latency.json"
if not data_path.exists():
    data_path = Path(__file__).resolve().parent / "q-vercel-latency.json"

try:
    with open(data_path, "r", encoding="utf-8") as f:
        TELEMETRY_DATA = json.load(f)
except Exception:
    TELEMETRY_DATA = []

class LatencyRequest(BaseModel):
    regions: List[str]
    threshold_ms: float

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
