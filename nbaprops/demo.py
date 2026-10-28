"""İnternetsiz demo: ESPN fonksiyonlarını sahte verilerle değiştirip tüm akışı (model, oran, stake, sonuç, sayfa) çalıştırır."""
import datetime as dt
import os
import random
import shutil

from . import espn, odds, pipeline, render

ROOT = os.path.join(os.path.dirname(__file__), "..")

TEAMS = {"1": ("KRT", "Demo Kartallar"), "2": ("ASL", "Demo Aslanlar"), "3": ("KPL", "Demo Kaplanlar"), "4": ("BOG", "Demo Boğalar")}
PLAYERS = {}  # id -> (name, team, min, pts/min, reb/min, ast/min)


def _setup():
    random.seed(7)
    first = ["Ali", "Mert", "Can", "Emre", "Kaan", "Deniz", "Burak", "Ozan", "Arda", "Efe", "Baran", "Tuna"]
    last = ["Yılmaz", "Demir", "Kaya", "Şahin", "Çelik", "Aydın", "Öztürk", "Arslan", "Doğan", "Koç", "Kurt", "Aksoy"]
    pid = 100
    for tid in TEAMS:
        for i in range(7):
            pid += 1
            PLAYERS[str(pid)] = (f"{random.choice(first)} {random.choice(last)}", tid, random.uniform(20, 36),
                                 random.uniform(0.35, 0.85), random.uniform(0.12, 0.35), random.uniform(0.05, 0.25))


def _logs(aid, n):
    _, tid, mn, p, r, a = PLAYERS[aid]
    rnd = random.Random(int(aid) * 31 + n)
    out = []
    gid = "g1" if tid in ("1", "2") else "g2"
    for i in range(n):
        m = max(5, rnd.gauss(mn, 4))
        d = dt.date(2026, 10, 26) - dt.timedelta(days=i)
        out.append({"event": f"{d}-{gid}" if n < 20 else f"old{i}", "date": d.isoformat(), "min": round(m),
                    "PTS": max(0, round(rnd.gauss(p * m, 5))), "REB": max(0, round(rnd.gauss(r * m, 2.2))),
                    "AST": max(0, round(rnd.gauss(a * m, 1.8))), "3PM": max(0, round(rnd.gauss(p * m / 9, 1.2)))})
    return out


def run(cfg):
    _setup()
    tmp = os.path.join(ROOT, "data", "demo_picks")
    shutil.rmtree(tmp, ignore_errors=True)
    pipeline.PICKS_DIR = tmp

    logo = lambda abbr: ""  # noqa
    def games_on(date):
        base = [("g1", "2", "1", "2026-10-29T00:30:00Z"), ("g2", "4", "3", "2026-10-29T02:00:00Z")]
        past = date < dt.date(2026, 10, 27)
        rnd = random.Random(str(date))
        return [{"id": f"{date}-{g}", "date_utc": t.replace("2026-10-29", (date + dt.timedelta(days=1)).isoformat()),
                 "home": {"id": h, "abbr": TEAMS[h][0], "name": TEAMS[h][1], "logo": "", "score": rnd.randint(100, 130) if past else None},
                 "away": {"id": aw, "abbr": TEAMS[aw][0], "name": TEAMS[aw][1], "logo": "", "score": rnd.randint(100, 130) if past else None},
                 "state": "post" if past else "pre", "completed": past, "season_type": 2} for g, h, aw, t in base]
    espn.games_on = games_on
    star = max((k for k, v in PLAYERS.items() if v[1] == "1"), key=lambda k: PLAYERS[k][2])
    espn.roster = lambda tid: [{"id": k, "name": v[0], "headshot": "", "pos": "", "injury": "Out" if k == star else ""}
                               for k, v in PLAYERS.items() if v[1] == tid]
    espn.injuries_from_summary = lambda eid: {}
    espn.gamelog = lambda aid, season: _logs(aid, 6 if season == 2027 else 40)

    def boxscore(eid):
        rnd = random.Random(hash(eid) % 1000)
        res = {}
        for k, (_, _, mn, p, r, a) in PLAYERS.items():
            m = max(8, rnd.gauss(mn, 4))
            res[k] = {"min": round(m), "PTS": max(0, round(rnd.gauss(p * m, 5))), "REB": max(0, round(rnd.gauss(r * m, 2.2))),
                      "AST": max(0, round(rnd.gauss(a * m, 1.8))), "3PM": max(0, round(rnd.gauss(p * m / 9, 1.2))), "dnp": False}
        return True, res
    espn.boxscore = boxscore

    # Sahte "iddaa" oranları: modelin biraz etrafında, marjlı
    real_manual = odds.manual_odds
    def fake_nesine(players, cfg, games=None, raw=None):
        rnd = random.Random(3)
        out = []
        for p in players:
            _, _, mn, pp, r, a = PLAYERS[p["id"]]
            for mk, mu in (("PTS", pp * mn), ("REB", r * mn), ("AST", a * mn), ("PRA", (pp + r + a) * mn)):
                k = max(1, round(mu * rnd.uniform(0.85, 1.05)))
                out.append({"player": p["name"], "market": mk, "line": k, "odds": round(rnd.uniform(1.55, 2.05), 2), "source": "IDDAA"})
        return out
    odds.nesine_odds = fake_nesine
    real_fetch = odds.fetch_nesine
    odds.fetch_nesine = lambda: {}
    odds.manual_odds = lambda d: []

    d1, d2 = dt.date(2026, 10, 27), dt.date(2026, 10, 28)
    pipeline.build_day(d1, cfg)
    pipeline.grade()           # dünkü maçlar "bitti"
    espn.boxscore = lambda eid: (False, {})
    pipeline.build_day(d2, cfg)
    odds.manual_odds = real_manual
    odds.fetch_nesine = real_fetch
    return render.render(os.path.join(ROOT, "docs", "demo.html"), tmp)
