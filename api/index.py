import json
from pathlib import Path
from typing import List, Any
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
)

def load_data():
    search_paths = [
        Path(__file__).resolve().parent / "q-vercel-latency.json",
        Path(__file__).resolve().parent.parent / "q-vercel-latency.json",
        Path("q-vercel-latency.json"),
        Path("api/q-vercel-latency.json"),
    ]
    for p in search_paths:
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    content = json.load(f)
                    if isinstance(content, list):
                        return content
                    if isinstance(content, dict):
                        for val in content.values():
                            if isinstance(val, list):
                                return val
            except Exception:
                pass
    return []

TELEMETRY_DATA = load_data()

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
    regions_list = []
    regions_dict = {}

    for region in req.regions:
        target = region.strip().lower()
        records = [
            r for r in TELEMETRY_DATA 
            if str(r.get("region", "")).strip().lower() == target
        ]

        latencies = []
        uptimes = []
        for r in records:
            # Safely extract latency
            lat = r.get("latency") if r.get("latency") is not None else r.get("latency_ms")
            if lat is not None:
                latencies.append(float(lat))
            
            # Safely extract uptime
            upt = r.get("uptime") if r.get("uptime") is not None else r.get("uptime_pct")
            if upt is not None:
                uptimes.append(float(upt))

        avg_lat = round(float(np.mean(latencies)), 2) if latencies else 0.0
        p95_lat = round(float(np.percentile(latencies, 95)), 2) if latencies else 0.0
        avg_upt = round(float(np.mean(uptimes)), 2) if uptimes else 0.0
        breaches_cnt = sum(1 for l in latencies if l > req.threshold_ms)

        stats = {
            "region": region,
            "avg_latency": avg_lat,
            "p95_latency": p95_lat,
            "avg_uptime": avg_upt,
            "breaches": breaches_cnt,
        }

        regions_list.append(stats)
        regions_dict[region] = stats

    # Return formats compatible with both array and dictionary expectations
    return {
        "regions": regions_list,
        **regions_dict
    }
