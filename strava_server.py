import os
import time

import httpx
from pathlib import Path
from dotenv import load_dotenv

from mcp.server.fastmcp import FastMCP
from datetime import date, datetime, timedelta

load_dotenv(Path(__file__).parent / ".env")

mcp = FastMCP("strava-basic")

API = "https://www.strava.com/api/v3"
TOKENS = {
    "access": os.environ["STRAVA_ACCESS_TOKEN"],
    "refresh": os.environ["STRAVA_REFRESH_TOKEN"],
}


def refresh_tokens():
    r = httpx.post(
        "https://www.strava.com/oauth/token",
        data={
            "client_id": os.environ["STRAVA_CLIENT_ID"],
            "client_secret": os.environ["STRAVA_CLIENT_SECRET"],
            "grant_type": "refresh_token",
            "refresh_token": TOKENS["refresh"],
        },
    )
    r.raise_for_status()
    d = r.json()
    TOKENS["access"] = d["access_token"]
    TOKENS["refresh"] = d["refresh_token"]


def strava_get(path, params=None):
    for attempt in (1, 2):
        r = httpx.get(
            f"{API}{path}",
            params=params,
            headers={"Authorization": f"Bearer {TOKENS['access']}"},
        )
        if r.status_code == 401 and attempt == 1:
            refresh_tokens()
            continue
        r.raise_for_status()
        return r.json()


@mcp.tool()
def get_recent_activities(days: int = 14, sport: str = "") -> list[dict]:
    """Palauttaa käyttäjän Strava-aktiviteetit viimeisiltä päiviltä.

    days: kuinka monta päivää taaksepäin haetaan (oletus 14, max 60).
    sport: valinnainen rajaus, esim. "Run" tai "Ride". Tyhjä = kaikki lajit.
    Matkat ovat kilometreinä ja ajat minuutteina.
    """
    days = min(days, 60)
    after = int(time.time()) - days * 86400
    acts = strava_get("/athlete/activities", {"after": after, "per_page": 100})
    out = []
    for a in acts:
        kind = a.get("sport_type") or a.get("type", "")
        if sport and kind.lower() != sport.lower():
            continue
        out.append({
            "id": a["id"],
            "name": a["name"],
            "sport": kind,
            "date": a["start_date_local"][:10],
            "distance_km": round(a["distance"] / 1000, 1),
            "moving_time_min": round(a["moving_time"] / 60),
            "elevation_m": round(a.get("total_elevation_gain", 0)),
            "avg_hr": a.get("average_heartrate"),
        })
    return out

RUN_TYPES = {"Run", "TrailRun", "VirtualRun"}
RIDE_TYPES = {"Ride", "VirtualRide", "GravelRide", "MountainBikeRide", "EBikeRide"}


def fetch_since(after: int, max_pages: int = 5) -> list[dict]:
    """Hakee aktiviteetit sivutettuna (Strava antaa max 100 / sivu)."""
    out = []
    for page in range(1, max_pages + 1):
        batch = strava_get(
            "/athlete/activities", {"after": after, "per_page": 100, "page": page}
        )
        out.extend(batch)
        if len(batch) < 100:
            break
    return out


@mcp.tool()
def weekly_load(weeks: int = 6) -> list[dict]:
    """Palauttaa viikoittaisen harjoituskuorman, vanhimmasta viikosta uusimpaan.

    weeks: montako viikkoa haetaan (oletus 6, max 12). Viikko alkaa maanantaina.
    Jokaisesta viikosta: juoksukilometrit, pyöräilykilometrit, kokonaisaika
    tunteina, nousumetrit, treenien määrä ja kokonaisajan muutos edelliseen
    viikkoon verrattuna prosentteina (null, jos edellisellä viikolla ei ollut
    treenejä). Kuluva viikko on kesken (partial=true), joten sen luvut eivät ole
    suoraan vertailukelpoisia täysiin viikkoihin. Kuorman mittarina on
    liikkumisaika, ei sykepohjainen kuormitus.
    """
    weeks = max(1, min(weeks, 12))
    today = date.today()
    this_monday = today - timedelta(days=today.weekday())
    first_monday = this_monday - timedelta(weeks=weeks - 1)
    after = int(datetime.combine(first_monday, datetime.min.time()).timestamp())

    buckets = {
        first_monday + timedelta(weeks=i): {
            "run_km": 0.0, "ride_km": 0.0, "seconds": 0, "elevation_m": 0.0, "sessions": 0,
        }
        for i in range(weeks)
    }

    for a in fetch_since(after):
        d = date.fromisoformat(a["start_date_local"][:10])
        monday = d - timedelta(days=d.weekday())
        b = buckets.get(monday)
        if b is None:
            continue
        kind = a.get("sport_type") or a.get("type", "")
        km = a["distance"] / 1000
        if kind in RUN_TYPES:
            b["run_km"] += km
        elif kind in RIDE_TYPES:
            b["ride_km"] += km
        b["seconds"] += a["moving_time"]
        b["elevation_m"] += a.get("total_elevation_gain", 0)
        b["sessions"] += 1

    result, prev = [], None
    for monday in sorted(buckets):
        b = buckets[monday]
        change = None
        if prev:
            change = round((b["seconds"] - prev) / prev * 100)
        result.append({
            "week_start": monday.isoformat(),
            "run_km": round(b["run_km"], 1),
            "ride_km": round(b["ride_km"], 1),
            "hours": round(b["seconds"] / 3600, 1),
            "elevation_m": round(b["elevation_m"]),
            "sessions": b["sessions"],
            "change_vs_prev_week_pct": change,
            "partial": monday == this_monday,
        })
        prev = b["seconds"]
    return result


if __name__ == "__main__":
    mcp.run()  # stdio-kuljetus oletuksena