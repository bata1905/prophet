"""Geçen sezon üzerinde geriye dönük test (backtest).

Her oyuncunun her maçı için model, SADECE o maçtan önceki verilerle tahmin yapar ve gerçek sonuçla karşılaştırılır.
Geçmiş iddaa oranları elimizde olmadığı için barem olarak bahis şirketlerinin tipik yaklaşımı kullanılır:
oyuncunun son 10 maç ortalamasının yuvarlanmışı ("X+").

Ölçülenler:
  - Kalibrasyon: model %60 dediğinde gerçekten ~%60 tutuyor mu?
  - Brier skoru (düşük = iyi): model vs. "son 10 maçta kaç kere geçti" basit yöntemi.
"""
import datetime as dt
import json
import os

from . import espn, model

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(ROOT, "data", "backtest.json")
MKTS = ["PTS", "REB", "AST", "3PM", "RA", "PRA"]
BUCKETS = [(0.0, 0.3), (0.3, 0.4), (0.4, 0.5), (0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 1.01)]


def run(cfg, season=None, log=print):
    season = season or espn.season_for(dt.date.today()) - 1
    log(f"Backtest: {season - 1}-{str(season)[2:]} sezonu. Kadrolar alınıyor...")
    players = {}
    for tid in range(1, 31):
        try:
            for p in espn.roster(str(tid)):
                players[p["id"]] = p["name"]
        except Exception:
            continue
    log(f"{len(players)} oyuncu. Maç logları çekiliyor (ilk sefer 5-15 dk sürebilir)...")

    recs = []
    for i, (pid, name) in enumerate(players.items()):
        if i % 50 == 0:
            log(f"  {i}/{len(players)}")
        cur = espn.gamelog(pid, season)
        prev = espn.gamelog(pid, season - 1)
        asc = [g for g in reversed(cur) if g["min"] > 0]
        for idx in range(5, len(asc)):
            g = asc[idx]
            before = list(reversed(asc[:idx]))
            pr = model.project(before, prev, cfg, MKTS)
            if not pr or pr["proj_min"] < cfg["min_avg_minutes"]:
                continue
            last10 = before[:10]
            for mk in MKTS:
                vals = [model.stat_value(x, mk) for x in last10]
                k = int(round(sum(vals) / len(vals)))
                if k < 1:
                    continue
                m = pr["markets"][mk]
                p = model.prob_at_least(k, m["mean"], m["var"])
                naive = sum(v >= k for v in vals) / len(vals)
                hit = model.stat_value(g, mk) >= k
                recs.append((mk, p, naive, hit))
    log(f"{len(recs)} tahmin değerlendirildi.")
    res = summarize(recs, season)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print_summary(res)
    return res


def _brier(xs, idx):
    return sum((x[idx] - x[3]) ** 2 for x in xs) / len(xs) if xs else None


def summarize(recs, season):
    buckets = []
    for lo, hi in BUCKETS:
        xs = [r for r in recs if lo <= r[1] < hi]
        if xs:
            buckets.append({"lo": lo, "hi": min(hi, 1.0), "n": len(xs),
                            "pred": sum(r[1] for r in xs) / len(xs), "act": sum(r[3] for r in xs) / len(xs)})
    by_market = {}
    for mk in MKTS:
        xs = [r for r in recs if r[0] == mk]
        if xs:
            by_market[mk] = {"n": len(xs), "pred": sum(r[1] for r in xs) / len(xs), "act": sum(r[3] for r in xs) / len(xs),
                             "brier": _brier(xs, 1), "brier_naive": _brier(xs, 2)}
    # Güvenli bölge: model %60+ dediğinde
    hi = [r for r in recs if r[1] >= 0.6]
    return {
        "season": f"{season - 1}-{str(season)[2:]}",
        "generated": dt.datetime.utcnow().isoformat() + "Z",
        "n": len(recs),
        "brier": _brier(recs, 1), "brier_naive": _brier(recs, 2), "brier_coin": 0.25,
        "buckets": buckets, "by_market": by_market,
        "high_conf": {"n": len(hi), "act": sum(r[3] for r in hi) / len(hi) if hi else None,
                      "pred": sum(r[1] for r in hi) / len(hi) if hi else None},
    }


def print_summary(res):
    print(f"\n=== Backtest {res['season']} — {res['n']} tahmin ===")
    print(f"Brier: model {res['brier']:.4f} | basit yöntem {res['brier_naive']:.4f} | yazı-tura 0.25  (düşük = iyi)")
    print("Kalibrasyon (model dedi -> gerçekte tuttu):")
    for b in res["buckets"]:
        print(f"  %{b['lo']*100:.0f}-{b['hi']*100:.0f}: {b['n']:6d} tahmin | model %{b['pred']*100:.1f} -> gerçek %{b['act']*100:.1f}")
    for mk, v in res["by_market"].items():
        print(f"  {mk:4s}: n={v['n']:6d}  model %{v['pred']*100:.1f} gerçek %{v['act']*100:.1f}  brier {v['brier']:.4f} (basit {v['brier_naive']:.4f})")
