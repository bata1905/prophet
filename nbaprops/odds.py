"""Oran kaynakları.

1) Nesine (iddaa — Türkiye'de yasal; iddaa oranları Nesine/Misli/Bilyoner'de aynıdır).
   Nesine'nin web sitesinin kullandığı herkese açık bülten JSON'u okunur. Resmi, belgelenmiş
   bir API değil; yapısı değişebilir. Oyuncu bahisleri pazar kodları (MTID) bülten yapısına
   göre bir kez ayarlanmalı:  python run.py --nesine-debug  ->  data/raw/ altına döküm alır.
2) Elle girilen oranlar: data/odds_manual.csv (her zaman çalışır, Nesine'den hızlıca kopyala).

Her kaynak şu kayıtları döner: {player, market, line(k, "k+" demek), odds, source}
"""
import csv
import datetime as dt
import json
import math
import os
import re
import unicodedata

import requests

ROOT = os.path.join(os.path.dirname(__file__), "..")
NESINE_URL = "https://cdnbulten.nesine.com/api/bulten/getprebultenfull"

# Pazar adındaki kelimelerden market tahmini (Nesine pazar adları Türkçe)
KEYWORDS = [
    (("sayı", "ribaund", "asist"), "PRA"),
    (("sayı", "ribaund"), "PR"),
    (("sayı", "asist"), "PA"),
    (("ribaund", "asist"), "RA"),
    (("ribaund",), "REB"),
    (("asist",), "AST"),
    (("sayı",), "PTS"),
]


def norm(name):
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z ]", "", s)
    s = re.sub(r"\b(jr|sr|ii|iii|iv)\b", "", s)
    return " ".join(s.split())


def line_to_k(line):
    """'15' -> 15 (15+), '14.5' üst -> 15+."""
    x = float(str(line).replace(",", "."))
    return int(x) if x == int(x) else int(math.floor(x)) + 1


def match_player(name, players):
    """players: {norm_name: player}. Tam eşleşme; yoksa 'soyad + ilk harf' (yalnızca tek aday varsa)."""
    n = norm(name)
    if n in players:
        return players[n]
    parts = n.split()
    if not parts:
        return None
    cands = [p for key, p in players.items()
             if key.split() and key.split()[-1] == parts[-1] and key.split()[0][:1] == parts[0][:1]]
    return cands[0] if len(cands) == 1 else None


def manual_odds(date_str):
    path = os.path.join(ROOT, "data", "odds_manual.csv")
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        rows = [l for l in f if l.strip() and not l.lstrip().startswith("#")]
    for r in csv.DictReader(rows):
        if r.get("date", "").strip() != date_str:
            continue
        try:
            out.append({
                "player": r["player"].strip(),
                "market": r["market"].strip().upper(),
                "line": line_to_k(r["line"]),
                "odds": float(r["odds"].replace(",", ".")),
                "source": "MANUEL",
            })
        except Exception:
            continue
    return out


def fetch_nesine():
    r = requests.get(NESINE_URL, timeout=25, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": "https://www.nesine.com/",
        "Origin": "https://www.nesine.com",
        "Accept": "application/json",
    })
    r.raise_for_status()
    return r.json()


def _events(raw):
    """Bülten içindeki tüm etkinlik sözlüklerini (HN/AN/MA alanları olan) bul."""
    stack, out = [raw], []
    while stack:
        x = stack.pop()
        if isinstance(x, dict):
            if "MA" in x and ("HN" in x or "AN" in x or "ENN" in x):
                out.append(x)
            stack.extend(x.values())
        elif isinstance(x, list):
            stack.extend(x)
    return out


def _guess_market(text):
    t = text.lower()
    for words, mk in KEYWORDS:
        if all(w in t for w in words):
            return mk
    return None


NBA_LC = 138          # Nesine'de NBA lig kodu
NBA_GT = 2            # basketbol
DEFAULT_MAP = {"717": "PTS", "718": "REB", "719": "AST", "720": "3PM", "725": "PRA", "766": "RA"}
_ON_RE = re.compile(r"^(.*?)\s+(\d+)\+\s*$")


def nba_events(raw):
    return [e for e in _events(raw) if e.get("LC") == NBA_LC and e.get("GT") == NBA_GT]


def nesine_debug(players_today=None):
    """Ham bülteni kaydeder, NBA maçlarını ve oyuncu pazarlarını özetler."""
    os.makedirs(os.path.join(ROOT, "data", "raw"), exist_ok=True)
    raw = fetch_nesine()
    with open(os.path.join(ROOT, "data", "raw", "nesine_bulten.json"), "w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False)
    evs = nba_events(raw)
    with open(os.path.join(ROOT, "data", "raw", "nesine_nba.json"), "w", encoding="utf-8") as f:
        json.dump(evs, f, ensure_ascii=False, indent=1)
    print(f"Nesine NBA maçı: {len(evs)}  (data/raw/nesine_nba.json)")
    for e in evs:
        props = {}
        for m in e.get("MA", []):
            if any("ON" in o for o in m.get("OCA", [])):
                props[m["MTID"]] = props.get(m["MTID"], 0) + len(m["OCA"])
        print(f" - {e.get('D')} {e.get('T')}  {e.get('HN')} - {e.get('AN')}  | oyuncu pazarları {props}")


def nesine_odds(players_today, cfg, games=None, raw=None):
    """Nesine NBA oyuncu bahisleri. Seçenek adı 'Oyuncu Adı 15+' biçiminde, tek oran (üst)."""
    raw = raw if raw is not None else fetch_nesine()
    players = {norm(p["name"]): p for p in players_today}
    mmap = {str(k): v for k, v in (cfg.get("nesine_market_map") or DEFAULT_MAP).items()}
    starts = []
    for g in games or []:
        try:
            starts.append(dt.datetime.fromisoformat(g["date_utc"].replace("Z", "+00:00")).timestamp() * 1000)
        except Exception:
            pass
    out = []
    for e in nba_events(raw):
        esd = e.get("ESD") or 0
        if starts and not any(abs(esd - s) <= 3 * 3600 * 1000 for s in starts):
            continue  # başka günün maçı
        for m in e.get("MA", []):
            mk = mmap.get(str(m.get("MTID")))
            if not mk:
                continue
            for o in m.get("OCA", []):
                mt = _ON_RE.match(str(o.get("ON", "")))
                if not mt:
                    continue
                p = match_player(mt.group(1), players)
                if not p:
                    continue
                out.append({"player": p["name"], "market": mk, "line": int(mt.group(2)),
                            "odds": float(o["O"]), "source": "IDDAA",
                            "event": f"{e.get('HN')} - {e.get('AN')}"})
    return out
