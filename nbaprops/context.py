"""Maç bağlamı: takım formu, rakip/tempo (iddaa baremlerinden), back-to-back, sakat takım arkadaşı etkisi."""
import datetime as dt

from . import espn

# ---------------------------------------------------------------- takım geçmişi

def team_history(date, days=21):
    """Son `days` gündeki biten normal sezon maçlarından takım istatistikleri.

    Döner: {team_id: {"pts": ort. attığı, "allowed": ort. yediği, "total": ort. maç toplamı,
                      "n": maç sayısı, "last_date": son maç günü, "last_events": [son maç id'leri]}}, lig ort.
    """
    games = []
    for i in range(1, days + 1):
        d = date - dt.timedelta(days=i)
        try:
            for g in espn.games_on(d):
                if g["completed"] and g.get("season_type", 2) in (2, 3):
                    g["_d"] = d
                    games.append(g)
        except Exception:
            continue
    teams = {}
    for g in games:
        try:
            hs, as_ = float(g["home"]["score"]), float(g["away"]["score"])
        except (TypeError, ValueError):
            continue
        for side, pts, opp in (("home", hs, as_), ("away", as_, hs)):
            t = teams.setdefault(g[side]["id"], {"pts": [], "allowed": [], "dates": []})
            t["pts"].append(pts)
            t["allowed"].append(opp)
            t["dates"].append((g["_d"], g["id"]))
    allpts = [p for t in teams.values() for p in t["pts"]]
    league = sum(allpts) / len(allpts) if allpts else 114.0
    out = {}
    for tid, t in teams.items():
        n = len(t["pts"])
        k = 5  # lig ortalamasına doğru küçültme (sezon başı az maç)
        out[tid] = {
            "pts": (sum(t["pts"]) + k * league) / (n + k),
            "allowed": (sum(t["allowed"]) + k * league) / (n + k),
            "n": n,
            "last_date": max(d for d, _ in t["dates"]),
            "last_events": [e for _, e in sorted(t["dates"], reverse=True)[:2]],
        }
    return out, league


# ---------------------------------------------------------------- iddaa maç baremleri

def _tokens(s):
    return {w for w in (s or "").lower().replace(".", " ").split() if len(w) > 2}


def nesine_game_lines(nba_events, games):
    """iddaa maç toplamı (MTID 149) ve handikap (144) -> takım başı beklenen sayı.

    Döner: {espn_game_id: {team_id: beklenen_sayı, "total": toplam}}
    """
    res = {}
    for g in games:
        try:
            start = dt.datetime.fromisoformat(g["date_utc"].replace("Z", "+00:00")).timestamp() * 1000
        except Exception:
            continue
        best = None
        for e in nba_events:
            if abs((e.get("ESD") or 0) - start) > 3 * 3600 * 1000:
                continue
            sc_hh = len(_tokens(e.get("HN")) & _tokens(g["home"]["name"]))
            sc_ha = len(_tokens(e.get("HN")) & _tokens(g["away"]["name"]))
            sc_ah = len(_tokens(e.get("AN")) & _tokens(g["home"]["name"]))
            sc_aa = len(_tokens(e.get("AN")) & _tokens(g["away"]["name"]))
            if sc_hh and sc_aa:
                cand = (sc_hh + sc_aa, e, False)
            elif sc_ha and sc_ah:
                cand = (sc_ha + sc_ah, e, True)  # Nesine'de ev/deplasman ters
            else:
                continue
            if not best or cand[0] > best[0]:
                best = cand
        if not best:
            continue
        _, e, swapped = best
        total = _main_line(e, 149)
        spread = _main_line(e, 144)  # Nesine ev sahibine (HN) uygulanan handikap, ör. -3.5
        if total is None:
            continue
        spread = spread or 0.0
        hn_pts = (total - spread) / 2
        an_pts = total - hn_pts
        home_pts, away_pts = (an_pts, hn_pts) if swapped else (hn_pts, an_pts)
        res[g["id"]] = {g["home"]["id"]: home_pts, g["away"]["id"]: away_pts, "total": total}
    return res


def _main_line(e, mtid):
    """Oranları birbirine en yakın (dengeli) bareme ana barem denir."""
    best = None
    for m in e.get("MA", []):
        if m.get("MTID") != mtid or len(m.get("OCA", [])) != 2:
            continue
        o1, o2 = m["OCA"][0]["O"], m["OCA"][1]["O"]
        if o1 <= 1.01 or o2 <= 1.01:
            continue
        diff = abs(o1 - o2)
        if best is None or diff < best[0]:
            best = (diff, float(m.get("SOV") or 0))
    return best[1] if best else None


# ---------------------------------------------------------------- çarpanlar

def team_multipliers(game, side, hist, league, lines, date):
    """Takım için istatistik çarpanları + açıklama notları."""
    team = game[side]
    opp = game["away" if side == "home" else "home"]
    th = hist.get(team["id"], {"pts": league, "allowed": league, "n": 0})
    oh = hist.get(opp["id"], {"pts": league, "allowed": league, "n": 0})
    notes = []
    gl = lines.get(game["id"])
    if gl:
        implied = gl[team["id"]]
        base = th["pts"]
        f = implied / base
        pace = gl["total"] / (th["pts"] + th["allowed"])
        notes.append(f"iddaa beklentisi {implied:.0f} sayı (ort. {base:.0f})")
    else:
        # iddaa yoksa: kendi hücumu ile rakibin yediği sayının ortalaması
        exp = (th["pts"] + oh["allowed"]) / 2
        f = exp / th["pts"] if th["pts"] else 1.0
        pace = ((th["pts"] + th["allowed"]) / 2 + (oh["pts"] + oh["allowed"]) / 2) / (2 * league) if league else 1.0
        if abs(f - 1) >= 0.02:
            notes.append(f"rakip savunması maç başı {oh['allowed']:.0f} sayı yiyor (lig {league:.0f})")
    f = max(0.88, min(1.12, f))
    pace = max(0.92, min(1.08, pace))
    mult = {"PTS": f, "3PM": f, "AST": 1 + (f - 1) * 0.7, "REB": 1 + (pace - 1) * 0.6}
    min_mult = 1.0
    last = th.get("last_date")
    if last and (date - last).days == 1:
        min_mult = 0.97
        for k in mult:
            mult[k] *= 0.985
        notes.append("back-to-back (dün oynadı)")
    return {"mult": mult, "min_mult": min_mult, "notes": notes}


def injury_boost(rotation, out_players, team_last_events):
    """Yeni sakatlanan rotasyon oyuncularının dakika ve üretimini kalanlara dağıtır.

    rotation: [{id, name, proj_min, rates:{PTS,REB,AST,3PM} (dk başı)}] (oynayacaklar)
    out_players: aynı yapı, oynamayacak olanlar + 'last_event'
    team_last_events: takımın son 2 maç id'si. Sakat oyuncu bu maçlarda oynamamışsa yokluğu zaten veride var, atlanır.
    Döner: {player_id: {"min_add": dk, "mult": {...}, "notes": [..]}}
    """
    new_out = [p for p in out_players if p["proj_min"] >= 15 and p.get("last_event") in team_last_events]
    if not new_out or not rotation:
        return {}
    lost_min = sum(p["proj_min"] for p in new_out) * 0.85
    tot_min = sum(p["proj_min"] for p in rotation) or 1
    team_prod = {s: sum(p["rates"][s] * p["proj_min"] for p in rotation + new_out) or 1 for s in ("PTS", "REB", "AST", "3PM")}
    lost_share = {s: sum(p["rates"][s] * p["proj_min"] for p in new_out) / team_prod[s] for s in team_prod}
    names = ", ".join(p["name"].split()[-1] for p in new_out)
    res = {}
    for p in rotation:
        share = p["proj_min"] / tot_min
        add = min(lost_min * share * 1.2, max(0, 38 - p["proj_min"]))
        # Dakika başı üretim: kaybedilen payın bir kısmı (yıldızlar daha çok şut alır)
        mult = {s: 1 + 0.35 * lost_share[s] for s in lost_share}
        res[p["id"]] = {"min_add": round(add, 1), "mult": mult,
                        "notes": [f"{names} yok: +{add:.1f} dk"] if add >= 0.5 else []}
    return res
