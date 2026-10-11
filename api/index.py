import json
import os
from pathlib import Path
from typing import List, Any
import numpy as np
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI()

# Add standard CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware to guarantee CORS headers on every response, including errors
@app.middleware("http")
async def add_cors_headers(request: Request, call_next):
    if request.method == "OPTIONS":
        return Response(
            status_code=200,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "*",
                "Access-Control-Allow-Headers": "*",
            },
        )
    try:
        response = await call_next(request)
    except Exception as e:
        response = JSONResponse(
            status_code=500,
            content={"error": str(e)},
        )
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "*"
    return response


def get_telemetry_records():
    # Search all possible locations where the json file might reside
    candidates = [
        Path(__file__).resolve().parent / "q-vercel-latency.json",
        Path(__file__).resolve().parent.parent / "q-vercel-latency.json",
        Path("q-vercel-latency.json"),
        Path("api/q-vercel-latency.json"),
    ]
    for p in candidates:
        if p.is_file():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return data
                    if isinstance(data, dict):
                        for val in data.values():
                            if isinstance(val, list):
                                return val
            except Exception:
                continue
    return []


TELEMETRY_DATA = get_telemetry_records()


class LatencyRequest(BaseModel):
    regions: List[str]
    threshold_ms: float


@app.options("/{full_path:path}")
def handle_options(full_path: str):
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        },
    )


@app.post("/api/latency")
@app.post("/")
def calculate_metrics(req: LatencyRequest):
    # Fallback: re-read data if empty at module start
    data = TELEMETRY_DATA if TELEMETRY_DATA else get_telemetry_records()

    regions_list = []
    regions_dict = {}

    for region in req.regions:
        target = region.strip().lower()
        records = [
            r for r in data
            if str(r.get("region", "")).strip().lower() == target
        ]

        latencies = []
        uptimes = []
        for r in records:
            lat = r.get("latency") if r.get("latency") is not None else r.get("latency_ms")
            if lat is not None:
                latencies.append(float(lat))

            upt = r.get("uptime") if r.get("uptime") is not None else r.get("uptime_pct")
            if upt is not None:
                uptimes.append(float(upt))

        avg_lat = round(float(np.mean(latencies)), 2) if latencies else 0.0
        p95_lat = round(float(np.percentile(latencies, 95)), 2) if latencies else 0.0
        avg_upt = round(float(np.mean(uptimes)), 2) if uptimes else 0.0
        breaches = sum(1 for l in latencies if l > req.threshold_ms)

        stats = {
            "region": region,
            "avg_latency": avg_lat,
            "p95_latency": p95_lat,
            "avg_uptime": avg_upt,
            "breaches": breaches,
        }
        regions_list.append(stats)
        regions_dict[region] = stats

    return {
        "regions": regions_list,
        **regions_dict,
    }
