"""ESPN'in herkese açık (anahtarsız) NBA API'leri: maç programı, kadro, sakatlık, oyuncu maç logları, boxscore."""
import hashlib
import json
import os
import time

import requests

BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
WEB = "https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba"
CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "cache")

_S = requests.Session()
_S.headers["User-Agent"] = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


def _get(url, params=None, ttl=1800):
    os.makedirs(CACHE_DIR, exist_ok=True)
    key = hashlib.md5((url + json.dumps(params or {}, sort_keys=True)).encode()).hexdigest()
    path = os.path.join(CACHE_DIR, key + ".json")
    if ttl and os.path.exists(path) and time.time() - os.path.getmtime(path) < ttl:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    last = None
    for attempt in range(3):
        try:
            r = _S.get(url, params=params, timeout=20)
            r.raise_for_status()
            data = r.json()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f)
            return data
        except Exception as e:  # noqa
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"ESPN isteği başarısız: {url} {params} -> {last}")


def season_for(date):
    """ESPN sezonu bitiş yılıyla adlandırır: Ekim 2026 -> 2027."""
    return date.year + 1 if date.month >= 9 else date.year


def games_on(date):
    """date: ABD (New York) takvim günü. Maç listesi döner."""
    import datetime as _dt
    past = date < _dt.date.today() - _dt.timedelta(days=1)
    data = _get(f"{BASE}/scoreboard", {"dates": date.strftime("%Y%m%d")}, ttl=30 * 86400 if past else 600)
    games = []
    for ev in data.get("events", []):
        comp = ev["competitions"][0]
        teams = {}
        for c in comp["competitors"]:
            t = c["team"]
            teams[c["homeAway"]] = {
                "id": t["id"],
                "abbr": t.get("abbreviation", ""),
                "name": t.get("displayName", ""),
                "logo": t.get("logo", ""),
                "score": c.get("score"),
            }
        st = ev.get("status", {}).get("type", {})
        games.append({
            "id": ev["id"],
            "date_utc": ev["date"],
            "home": teams["home"],
            "away": teams["away"],
            "state": st.get("state", "pre"),          # pre / in / post
            "completed": bool(st.get("completed")),
            "season_type": (ev.get("season") or {}).get("type", 2),
        })
    return games


def roster(team_id):
    data = _get(f"{BASE}/teams/{team_id}/roster", ttl=3 * 3600)
    out = []
    items = data.get("athletes", [])
    # Bazı yanıtlarda pozisyon grupları halinde gelir
    if items and isinstance(items[0], dict) and "items" in items[0]:
        items = [a for g in items for a in g["items"]]
    for a in items:
        inj = a.get("injuries") or []
        status = inj[0].get("status", "") if inj else ""
        out.append({
            "id": str(a["id"]),
            "name": a.get("displayName") or a.get("fullName"),
            "headshot": (a.get("headshot") or {}).get("href", ""),
            "pos": (a.get("position") or {}).get("abbreviation", ""),
            "injury": status,
        })
    return out


def injuries_from_summary(event_id):
    """Maç özetindeki güncel sakatlık listesi {athlete_id: status}."""
    try:
        data = _get(f"{BASE}/summary", {"event": event_id}, ttl=900)
    except Exception:
        return {}
    res = {}
    for team in data.get("injuries", []):
        for inj in team.get("injuries", []):
            ath = inj.get("athlete", {})
            if ath.get("id"):
                res[str(ath["id"])] = inj.get("status", "")
    return res


def _num(s):
    try:
        return float(str(s).split("-")[0])
    except Exception:
        return 0.0


def gamelog(athlete_id, season):
    """Oyuncunun sezon maç logu, en yeni maç başta. Her maç: date, min, PTS, REB, AST."""
    try:
        data = _get(f"{WEB}/athletes/{athlete_id}/gamelog", {"season": season}, ttl=6 * 3600)
    except Exception:
        return []
    labels = data.get("labels") or data.get("names") or []
    idx = {l.upper(): i for i, l in enumerate(labels)}
    meta = data.get("events", {}) or {}
    games = []
    for stype in data.get("seasonTypes", []):
        name = (stype.get("displayName") or "").lower()
        if "preseason" in name:
            continue
        for cat in stype.get("categories", []):
            for e in cat.get("events", []) or []:
                st = e.get("stats") or []
                if not st:
                    continue
                def g(lbl):
                    i = idx.get(lbl)
                    return _num(st[i]) if i is not None and i < len(st) else 0.0
                m = meta.get(str(e.get("eventId")), {})
                games.append({
                    "event": str(e.get("eventId")),
                    "date": m.get("gameDate", ""),
                    "min": g("MIN"),
                    "PTS": g("PTS"),
                    "REB": g("REB"),
                    "AST": g("AST"),
                    "3PM": g("3PT"),
                })
    seen, uniq = set(), []
    for x in sorted(games, key=lambda x: x["date"], reverse=True):
        if x["event"] not in seen:
            seen.add(x["event"])
            uniq.append(x)
    return uniq


def boxscore(event_id):
    """Biten maçın oyuncu istatistikleri {athlete_id: {min, PTS, REB, AST}} ve maç durumu."""
    data = _get(f"{BASE}/summary", {"event": event_id}, ttl=300)
    comp = (data.get("header", {}).get("competitions") or [{}])[0]
    completed = bool(comp.get("status", {}).get("type", {}).get("completed"))
    res = {}
    for team in data.get("boxscore", {}).get("players", []):
        for block in team.get("statistics", []):
            labels = [l.upper() for l in (block.get("labels") or [])]
            idx = {l: i for i, l in enumerate(labels)}
            for a in block.get("athletes", []):
                aid = str(a.get("athlete", {}).get("id"))
                st = a.get("stats") or []
                if a.get("didNotPlay") or not st:
                    res[aid] = {"min": 0, "PTS": 0, "REB": 0, "AST": 0, "3PM": 0, "dnp": True}
                    continue
                def g(lbl):
                    i = idx.get(lbl)
                    return _num(st[i]) if i is not None and i < len(st) else 0.0
                res[aid] = {"min": g("MIN"), "PTS": g("PTS"), "REB": g("REB"), "AST": g("AST"), "3PM": g("3PT"), "dnp": False}
    return completed, res
