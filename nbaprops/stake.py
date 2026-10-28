"""Değer ve stake (bahis miktarı) hesabı — kesirli Kelly."""


def value(p, odds):
    """Beklenen getiri: p*oran - 1. Pozitifse uzun vadede kârlı."""
    return p * odds - 1


def kelly_stake(p, odds, cfg):
    edge = value(p, odds)
    if odds <= 1 or edge < cfg["min_edge"]:
        return 0.0
    f = edge / (odds - 1)                       # tam Kelly
    f *= cfg["kelly_fraction"]                  # çeyrek Kelly (oynaklığı düşürür)
    f = min(f, cfg["max_stake_pct"])            # tek bahiste kasanın en fazla %3'ü
    return round(cfg["bankroll_tl"] * f, 0)
