"""ABD bahis sitelerinin (FanDuel, DraftKings, BetMGM...) oyuncu bahisleri — The Odds API üzerinden.

Kullanım: https://the-odds-api.com adresinden ücretsiz anahtar al, config.json -> "odds_api_key".
Maliyet: maç başı (pazar sayısı x bölge) kredi. 6 pazar x 'us' = maç başı 6 kredi.

Bu oranlar SADECE referans: her bahsin üst/alt iki tarafı olduğu için marj çıkarılıp "adil olasılık" hesaplanır.
"""
import datetime as dt
import json
import os
import statistics
import time

import requests

from .odds import match_player, norm

ROOT = os.path.join(os.path.dirname(__file__), "..")
API = "https://api.the-odds-api.com/v4/sports/basketball_nba"
MARKETS = {
    "player_points": "PTS",
    "player_rebounds": "REB",
    "player_assists": "AST",
    "player_threes": "3PM",
    "player_points_rebounds_assists": "PRA",
    "player_rebounds_assists": "RA",
}
CACHE = os.path.join(ROOT, "data", "cache", "usodds")


def _key(cfg):
    return os.environ.get("ODDS_API_KEY") or cfg.get("odds_api_key") or ""


def fetch(games, cfg, log=print):
    """Bugünün maçları için ABD oranlarını çeker (günde 'us_odds_max_fetch' defadan fazla değil)."""
    key = _key(cfg)
    if not key or not games:
        return {}
    os.makedirs(CACHE, exist_ok=True)
    day = games[0]["date_utc"][:10]
    path = os.path.join(CACHE, f"{day}.json")
    ttl = cfg.get("us_odds_ttl_hours", 6) * 3600
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < ttl:
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    r = requests.get(f"{API}/events", params={"apiKey": key}, timeout=20)
    r.raise_for_status()
    events = r.json()
    starts = {}
    for g in games:
        starts[g["id"]] = dt.datetime.fromisoformat(g["date_utc"].replace("Z", "+00:00"))
    raw, left = [], None
    for e in events:
        t = dt.datetime.fromisoformat(e["commence_time"].replace("Z", "+00:00"))
        if not any(abs((t - s).total_seconds()) < 3 * 3600 for s in starts.values()):
            continue
        rr = requests.get(f"{API}/events/{e['id']}/odds", timeout=25, params={
            "apiKey": key, "regions": cfg.get("us_regions", "us"), "markets": ",".join(MARKETS),
            "oddsFormat": "decimal"})
        if rr.status_code == 422 or rr.status_code == 404:
            continue
        rr.raise_for_status()
        raw.append(rr.json())
        left = rr.headers.get("x-requests-remaining")
    if raw:
        log(f"ABD oranları: {len(raw)} maç (kalan kredi: {left})")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(raw, f)
    return raw


def fair_lines(raw):
    """Her oyuncu/pazar/barem için sitelerin marjsız 'üst' olasılıklarının medyanı.

    Döner: {(norm_player, market): [{"line": 24.5, "p_over": 0.52, "books": 5}, ...]}
    """
    acc = {}
    for ev in raw or []:
        for bk in ev.get("bookmakers", []):
            for m in bk.get("markets", []):
                mk = MARKETS.get(m.get("key"))
                if not mk:
                    continue
                sides = {}
                for o in m.get("outcomes", []):
                    who, line = o.get("description"), o.get("point")
                    if who is None or line is None:
                        continue
                    sides.setdefault((who, line), {})[o.get("name", "").lower()] = o.get("price")
                for (who, line), s in sides.items():
                    if s.get("over") and s.get("under"):
                        io, iu = 1 / s["over"], 1 / s["under"]
                        acc.setdefault((norm(who), mk, float(line)), []).append(io / (io + iu))
    out = {}
    for (who, mk, line), ps in acc.items():
        out.setdefault((who, mk), []).append({"line": line, "p_over": statistics.median(ps), "books": len(ps)})
    for v in out.values():
        v.sort(key=lambda x: -x["books"])
    return out


def for_player(fair, name, market):
    """En çok sitenin verdiği ana barem."""
    lst = fair.get((norm(name), market))
    if lst:
        return lst[0]
    # isim farklı yazılmışsa (ör. 'Jr.') soyad+ilk harf ile dene
    cands = {k[0]: k[0] for k in fair if k[1] == market}
    m = match_player(name, {c: c for c in cands})
    return fair[(m, market)][0] if m else None
