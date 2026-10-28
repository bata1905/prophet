"""Günlük akış: maçları çek -> oyuncuları modelle -> oranlarla eşleştir -> seçimleri kaydet -> geçmişi sonuçlandır."""
import datetime as dt
import glob
import json
import os

from . import context, espn, model, odds as oddsmod, usodds
from .stake import kelly_stake, value

ROOT = os.path.join(os.path.dirname(__file__), "..")
PICKS_DIR = os.path.join(ROOT, "data", "picks")


def picks_path(date_str):
    return os.path.join(PICKS_DIR, f"{date_str}.json")


def load_day(date_str):
    p = picks_path(date_str)
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return None


def save_day(day):
    os.makedirs(PICKS_DIR, exist_ok=True)
    with open(picks_path(day["date"]), "w", encoding="utf-8") as f:
        json.dump(day, f, ensure_ascii=False, indent=1)


BASE = ["PTS", "REB", "AST", "3PM"]
OUT_STATUSES = ("out", "injured reserve", "suspended", "doubtful")


def _team_players(game, side):
    """Takımın oynayacak ve oynamayacak oyuncuları."""
    inj = espn.injuries_from_summary(game["id"])
    team = game[side]
    playing, out = [], []
    for p in espn.roster(team["id"]):
        status = inj.get(p["id"], p["injury"]) or ""
        p["team"] = team["abbr"]
        p["injury"] = status
        (out if status.lower() in OUT_STATUSES else playing).append(p)
    return playing, out


def _rates(pr):
    m = pr["proj_min"] or 1
    return {s: pr["markets"][s]["mean"] / m for s in BASE}


def build_day(date, cfg, log=print):
    date_str = date.isoformat()
    games = espn.games_on(date)
    log(f"{date_str}: {len(games)} maç")
    season = espn.season_for(date)
    old = load_day(date_str) or {"games": []}
    frozen = {g["id"]: g for g in old["games"] if g.get("state") != "pre"}
    todo = [g for g in games if g["id"] not in frozen and g["state"] == "pre"]

    hist, league = context.team_history(date)
    log(f"takım geçmişi: {len(hist)} takım, lig ort. {league:.1f}")

    # Kadrolar
    rosters = {}
    for g in todo:
        for side in ("home", "away"):
            rosters[(g["id"], side)] = _team_players(g, side)
    all_players = [p for pl, _ in rosters.values() for p in pl]

    # Oranlar (Nesine bir kez indirilir)
    lines, game_lines = oddsmod.manual_odds(date_str), {}
    if cfg.get("odds_source") == "nesine" and todo:
        try:
            raw = oddsmod.fetch_nesine()
            nl = oddsmod.nesine_odds(all_players, cfg, todo, raw=raw)
            game_lines = context.nesine_game_lines(oddsmod.nba_events(raw), todo)
            log(f"Nesine: {len(nl)} oyuncu oranı, {len(game_lines)} maç baremi")
            lines += nl
        except Exception as e:
            log(f"Nesine okunamadı ({e}); model çizgileri kullanılacak")

    us_fair = {}
    if todo and usodds._key(cfg):
        try:
            us_fair = usodds.fair_lines(usodds.fetch(todo, cfg, log))
            log(f"ABD adil barem: {len(us_fair)} oyuncu/pazar")
        except Exception as e:
            log(f"ABD oranları alınamadı ({e})")

    out_games = []
    for g in games:
        if g["id"] in frozen:
            out_games.append(frozen[g["id"]])
            continue
        if g["state"] != "pre":
            continue
        projs, pool, ctx = {}, [], {}
        for side in ("away", "home"):
            playing, out = rosters[(g["id"], side)]
            pool += playing
            tm = context.team_multipliers(g, side, hist, league, game_lines, date)
            ctx[g[side]["abbr"]] = tm["notes"]
            logs = {p["id"]: (espn.gamelog(p["id"], season), espn.gamelog(p["id"], season - 1)) for p in playing + out}
            base = {}
            for p in playing + out:
                pr = model.project(*logs[p["id"]], cfg, BASE)
                if pr:
                    base[p["id"]] = pr
            rot = [{"id": p["id"], "name": p["name"], "proj_min": base[p["id"]]["proj_min"], "rates": _rates(base[p["id"]])}
                   for p in playing if p["id"] in base and base[p["id"]]["proj_min"] >= 10]
            outs = [{"id": p["id"], "name": p["name"], "proj_min": base[p["id"]]["proj_min"], "rates": _rates(base[p["id"]]),
                     "last_event": (logs[p["id"]][0] or [{}])[0].get("event")}
                    for p in out if p["id"] in base]
            boost = context.injury_boost(rot, outs, hist.get(g[side]["id"], {}).get("last_events", []))
            for p in playing:
                if p["id"] not in base:
                    continue
                b = boost.get(p["id"], {})
                adj = {"min_add": b.get("min_add", 0.0), "min_mult": tm["min_mult"],
                       "mult": {s: tm["mult"][s] * b.get("mult", {}).get(s, 1.0) for s in BASE}}
                pr = model.project(*logs[p["id"]], cfg, cfg["markets"], adj)
                if pr and pr["proj_min"] >= cfg["min_avg_minutes"]:
                    pr["notes"] = b.get("notes", [])
                    projs[p["id"]] = (p, pr)

        by_norm = {oddsmod.norm(p["name"]): p for p in pool}
        cands = []
        for l in lines:
            p = oddsmod.match_player(l["player"], by_norm)
            if not p or p["id"] not in projs or l["market"] not in model.MARKETS:
                continue
            _, pr = projs[p["id"]]
            m = pr["markets"].get(l["market"])
            if not m:
                continue
            p_model = model.prob_at_least(l["line"], m["mean"], m["var"])
            us = usodds.for_player(us_fair, p["name"], l["market"]) if us_fair else None
            if us:
                # ABD sitelerinin marjsız olasılığı -> iddaa çizgisine taşınır, modelle harmanlanır
                p_mkt = model.shift_to_market(l["line"], m["mean"], m["var"], us["line"], us["p_over"])
                w = cfg.get("model_weight_with_us", 0.35)
                src_mkt = "ABD"
            else:
                p_mkt = min(0.97, 1 / l["odds"] / cfg.get("market_margin", 1.08))
                w = cfg.get("model_weight", 0.5)
                src_mkt = "iddaa"
            prob = w * p_model + (1 - w) * p_mkt
            c = _pick(p, pr, l["market"], l["line"], prob, l["odds"], l["source"], m, cfg)
            c["prob_model"], c["prob_market"], c["market_src"] = round(p_model, 4), round(p_mkt, 4), src_mkt
            if us:
                c["us_line"], c["us_p"], c["us_books"] = us["line"], round(us["p_over"], 3), us["books"]
            cands.append(c)

        if not cands:  # oran yok -> model "adil" çizgileri
            for pid, (p, pr) in projs.items():
                for mk in ("PTS", "REB", "AST", "PRA"):
                    if mk not in pr["markets"]:
                        continue
                    m = pr["markets"][mk]
                    k, prob = model.fair_line(m["mean"], m["var"])
                    cands.append(_pick(p, pr, mk, k, prob, round(1 / max(prob, 0.01), 2), "MODEL", m, cfg))
            cands.sort(key=lambda c: (-c["prob"]))
        else:
            cands.sort(key=lambda c: (-c["value"], -c["prob"]))

        chosen, per_player = [], {}
        for c in cands:
            if per_player.get(c["player_id"], 0) >= 2:
                continue
            chosen.append(c)
            per_player[c["player_id"]] = per_player.get(c["player_id"], 0) + 1
            if len(chosen) >= cfg["picks_per_game"]:
                break
        chosen.sort(key=lambda c: -c["prob"])
        g = dict(g)
        g["picks"] = chosen
        g["all"] = [{"player_id": c["player_id"], "player": c["player"], "market": c["market"], "line": c["line"],
                     "prob": c["prob"], "prob_model": c.get("prob_model"), "prob_market": c.get("prob_market"),
                     "odds": c["odds"], "value": c["value"], "result": None, "actual": None}
                    for c in cands if c["source"] != "MODEL"]
        g["iddaa_total"] = (game_lines.get(g["id"]) or {}).get("total")
        g["context"] = ctx
        out_games.append(g)

    apply_stake_caps(out_games, cfg)
    day = {"date": date_str, "generated": dt.datetime.utcnow().isoformat() + "Z", "games": out_games}
    save_day(day)
    log(f"{sum(len(g['picks']) for g in out_games)} seçim kaydedildi -> data/picks/{date_str}.json")
    return day


def apply_stake_caps(games, cfg):
    """Korelasyon/risk sınırı: oyuncu, maç ve gün başına toplam stake."""
    bank = cfg["bankroll_tl"]
    lim_p = cfg.get("max_player_pct", 0.04) * bank
    lim_g = cfg.get("max_game_pct", 0.08) * bank
    lim_d = cfg.get("max_day_pct", 0.20) * bank

    def scale(picks, limit):
        tot = sum(p["stake_tl"] for p in picks)
        if tot > limit > 0:
            for p in picks:
                p["stake_tl"] = float(round(p["stake_tl"] * limit / tot))

    pending = [g for g in games if g.get("state", "pre") == "pre"]
    for g in pending:
        # Aynı oyuncudan birden fazla bahis aynı yönde ilişkili -> ikincisini yarıya indir
        seen = set()
        for p in sorted(g["picks"], key=lambda x: -(x["value"] or 0)):
            if p["stake_tl"] and p["player_id"] in seen:
                p["stake_tl"] = float(round(p["stake_tl"] / 2))
            seen.add(p["player_id"])
        for pid in {p["player_id"] for p in g["picks"]}:
            scale([p for p in g["picks"] if p["player_id"] == pid], lim_p)
        scale(g["picks"], lim_g)
    scale([p for g in pending for p in g["picks"]], lim_d)


def _pick(p, pr, mk, line, prob, odds, source, m, cfg):
    return {
        "player_id": p["id"], "player": p["name"], "team": p["team"], "headshot": p.get("headshot", ""),
        "injury": p.get("injury", ""),
        "market": mk, "label": model.MARKETS[mk][0], "line": int(line),
        "prob": round(prob, 4), "odds": round(float(odds), 2), "source": source,
        "value": round(value(prob, odds), 4) if source != "MODEL" else None,
        "stake_tl": kelly_stake(prob, odds, cfg) if source != "MODEL" else 0,
        "expected": m["mean"], "proj_min": pr["proj_min"],
        "notes": pr.get("notes", []),
        "confidence": model.confidence(prob, pr["n_games"], p.get("injury")),
        "actual": None, "actual_min": None, "result": None,
    }


def grade(days_back=10, log=print):
    """Geçmiş günlerin seçimlerini gerçek istatistiklerle sonuçlandırır. Son günleri döner."""
    days = []
    for path in sorted(glob.glob(os.path.join(PICKS_DIR, "*.json")))[-days_back:]:
        with open(path, encoding="utf-8") as f:
            day = json.load(f)
        changed = False
        for g in day["games"]:
            items = g["picks"] + g.get("all", [])
            if items and all(p["result"] for p in items):
                continue
            try:
                completed, box = espn.boxscore(g["id"])
            except Exception as e:
                log(f"boxscore alınamadı {g['id']}: {e}")
                continue
            if not completed:
                continue
            g["state"], g["completed"] = "post", True
            for p in g["picks"] + g.get("all", []):
                b = box.get(p["player_id"])
                if b is None or b.get("dnp"):
                    p["result"], p["actual"] = "İade", 0   # oynamadı -> iddaa'da genelde iade
                    p["actual_min"] = 0
                else:
                    act = model.stat_value(b, p["market"])
                    p["actual"] = act
                    p["actual_min"] = round(b["min"])
                    p["result"] = "Tuttu" if act >= p["line"] else "Tutmadı"
                changed = True
        if changed:
            save_day(day)
            log(f"sonuçlandırıldı: {day['date']}")
        days.append(day)
    return days[-3:]
