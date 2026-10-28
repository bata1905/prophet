"""Oyuncu projeksiyon modeli.

Mantık:
  1. Dakika tahmini: son maçların ağırlıklı ortalaması (yeni maç daha ağır, yarı ömür = half_life_games).
  2. Dakika başı üretim: aynı ağırlıklarla, geçen sezon verisi küçük ağırlıkla karıştırılır (sezon başı için).
  3. Beklenen değer = dakika başı üretim x tahmini dakika.
  4. Dağılım: Negatif binom (sayım verisi, gerçek maçlardaki oynaklıktan tahmin), P(X >= çizgi).
"""
import math

MARKETS = {
    "PTS": ("Sayı", ("PTS",)),
    "REB": ("Ribaund", ("REB",)),
    "AST": ("Asist", ("AST",)),
    "PR": ("Sayı+Ribaund", ("PTS", "REB")),
    "PA": ("Sayı+Asist", ("PTS", "AST")),
    "RA": ("Ribaund+Asist", ("REB", "AST")),
    "PRA": ("Sayı+Rib+Asist", ("PTS", "REB", "AST")),
    "3PM": ("Üçlük", ("3PM",)),
}


# Tipik değişim katsayısı (std / ortalama), NBA oyuncu maç başı istatistikleri
CV = {"PTS": 0.36, "REB": 0.42, "AST": 0.47, "3PM": 0.62, "PR": 0.32, "PA": 0.33, "RA": 0.38, "PRA": 0.30}


def stat_value(game, market):
    return sum(game[k] for k in MARKETS[market][1])


def _wmean(xs, ws):
    s = sum(ws)
    return sum(x * w for x, w in zip(xs, ws)) / s if s else 0.0


def _wvar(xs, ws, m):
    s = sum(ws)
    return sum(w * (x - m) ** 2 for x, w in zip(xs, ws)) / s if s else 0.0


def project(cur_logs, prev_logs, cfg, markets=None, adj=None):
    """Bir oyuncu için {market: {mean, var}} ve dakika tahmini döner. Yetersiz veri -> None.

    adj (isteğe bağlı): {"min_add": +dk, "min_mult": x, "mult": {"PTS": x, "REB": x, "AST": x, "3PM": x}}
    """
    markets = markets or cfg["markets"]
    adj = adj or {}
    hl = cfg["half_life_games"]
    lb = cfg["lookback_games"]
    cur = [g for g in cur_logs if g["min"] > 0][:lb]
    # Sezon başı: geçen sezonun son maçlarıyla tamamla ki 4-5 maçlık sıcak başlangıç ortalamayı şişirmesin
    prev = [g for g in prev_logs if g["min"] > 0][: max(0, cfg.get("min_sample", 20) - len(cur))]
    games = [(g, 0.5 ** (i / hl)) for i, g in enumerate(cur)]
    games += [(g, cfg["prev_season_weight"] * 0.5 ** (i / (2 * hl))) for i, g in enumerate(prev)]
    if len(games) < 4:
        return None

    mins = [g["min"] for g, _ in games]
    ws = [w for _, w in games]
    if len(cur) >= 3:
        cw = [0.5 ** (i / hl) for i in range(len(cur))]
        base_min = _wmean([g["min"] for g in cur], cw)
    else:
        base_min = _wmean(mins, ws)
    var_min = _wvar(mins, ws, _wmean(mins, ws))
    proj_min = min(42.0, (base_min + adj.get("min_add", 0.0)) * adj.get("min_mult", 1.0))
    smult = adj.get("mult", {})

    out = {"proj_min": round(proj_min, 1), "base_min": round(base_min, 1),
           "n_games": len(cur), "n_prev": len(prev), "markets": {}}
    for mk in markets:
        comps = MARKETS[mk][1]
        vals = [stat_value(g, mk) for g, _ in games]
        msum = max(1e-9, sum(m * w for m, w in zip(mins, ws)))
        comp_rates = {c: sum(g[c] * w for g, w in games) / msum for c in comps}
        rate0 = sum(comp_rates.values())
        rate = sum(r * smult.get(c, 1.0) for c, r in comp_rates.items())
        mean = rate * proj_min
        scaled = [v / m * proj_min for v, m in zip(vals, mins)]
        ws_eff = [w * min(1.0, m / max(proj_min, 1)) for w, m in zip(ws, mins)]
        var = _wvar(scaled, ws_eff, _wmean(scaled, ws_eff)) * (rate / rate0 if rate0 else 1) ** 2 \
            + rate ** 2 * var_min * 0.5
        # Gerçekçi oynaklık tabanı (NBA'de maçtan maça sapma): az maçla ölçülen düşük oynaklığa güvenme
        cv = CV.get(mk, 0.32)
        var = max(var, mean * 1.1, (cv * mean) ** 2, 0.3)
        out["markets"][mk] = {"mean": round(mean, 2), "var": round(var, 2)}
    return out


def _nb_logpmf(k, r, p):
    return math.lgamma(k + r) - math.lgamma(k + 1) - math.lgamma(r) + r * math.log(p) + k * math.log1p(-p)


def prob_at_least(k, mean, var):
    """P(X >= k), X ~ NegBin(mean, var) (var<=mean ise Poisson)."""
    k = int(k)
    if k <= 0:
        return 1.0
    if mean <= 0:
        return 0.0
    if var <= mean * 1.0001:
        cdf = sum(math.exp(-mean + j * math.log(mean) - math.lgamma(j + 1)) for j in range(k))
    else:
        p = mean / var
        r = mean * p / (1 - p)
        cdf = sum(math.exp(_nb_logpmf(j, r, p)) for j in range(k))
    return max(0.0, min(1.0, 1 - cdf))


def shift_to_market(k, mean, var, us_line, us_p_over):
    """Modelin dağılım şeklini koru, ortalamayı ABD baremine (ör. 24.5 üst = %52) oturt, sonra P(X >= k) ver.

    iddaa çizgisi (23+) ile ABD çizgisi (24.5) farklı olduğunda olasılığı doğru taşımak için.
    """
    t = int(us_line) + 1 if us_line == int(us_line) + 0.5 else int(round(us_line))
    lo, hi = 0.4, 2.0
    for _ in range(40):
        s = (lo + hi) / 2
        if prob_at_least(t, mean * s, var * s) < us_p_over:
            lo = s
        else:
            hi = s
    s = (lo + hi) / 2
    return prob_at_least(k, mean * s, var * s)


def fair_line(mean, var, target=0.58):
    """Bahis şirketi çizgisi yoksa: olasılığı hedefe en yakın 'X+' eşiği."""
    best = None
    for k in range(1, int(mean * 2) + 3):
        p = prob_at_least(k, mean, var)
        if best is None or abs(p - target) < abs(best[1] - target):
            best = (k, p)
    return best


def confidence(p, n_games, injury):
    if injury:
        return "Riskli"
    if p >= 0.60 and n_games >= 5:
        return "Yüksek Güven"
    if p >= 0.45:
        return "Orta Güven"
    return "Düşük Güven"
