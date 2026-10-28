"""Telegram bildirimleri: günün önerileri ve dünün sonuçları."""
import datetime as dt
import hashlib
import json
import os

import requests

ROOT = os.path.join(os.path.dirname(__file__), "..")
STATE = os.path.join(ROOT, "data", "notified.json")
WD = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]


def _creds(cfg):
    return (os.environ.get("TELEGRAM_TOKEN") or cfg.get("telegram_token") or "",
            os.environ.get("TELEGRAM_CHAT_ID") or cfg.get("telegram_chat_id") or "")


def send(cfg, text):
    token, chat = _creds(cfg)
    if not token or not chat:
        return False
    for chunk in [text[i:i + 3900] for i in range(0, len(text), 3900)]:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", timeout=20,
                          data={"chat_id": chat, "text": chunk, "parse_mode": "HTML", "disable_web_page_preview": True})
        if not r.ok:
            print("Telegram hatası:", r.text[:200])
            return False
    return True


def setup(cfg):
    token, _ = _creds(cfg)
    if not token:
        print("secrets.json içine telegram_token yaz (BotFather'dan aldığın).")
        return
    r = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=20).json()
    chats = {}
    for u in r.get("result", []):
        c = (u.get("message") or u.get("channel_post") or {}).get("chat")
        if c:
            chats[c["id"]] = c.get("first_name") or c.get("title") or ""
    if not chats:
        print("Bot'a Telegram'dan bir mesaj (ör. 'merhaba') gönder ve bu komutu tekrar çalıştır.")
        return
    for cid, name in chats.items():
        print(f"chat_id: {cid}   ({name})")
    print("Bu sayıyı secrets.json -> telegram_chat_id alanına yaz.")


def _state():
    try:
        with open(STATE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"picks": {}, "results": []}


def _save(st):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(st, f)


def _tr_time(iso):
    from zoneinfo import ZoneInfo
    t = dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(ZoneInfo("Europe/Istanbul"))
    return f"{t:%d.%m} {WD[t.weekday()]} {t:%H:%M}"


def picks_message(day, cfg):
    bets = [(g, p) for g in day["games"] if g.get("state", "pre") == "pre" for p in g["picks"] if p["stake_tl"] > 0]
    lines = [f"🔮 <b>PropHet — {day['date']}</b>"]
    if not bets:
        lines.append("Bugün değeri eşiği geçen bahis yok. En yüksek olasılıklılar:")
        top = sorted([(g, p) for g in day["games"] for p in g["picks"]], key=lambda x: -x[1]["prob"])[:5]
        for g, p in top:
            lines.append(f"• {p['player']} {p['label']} {p['line']}+  @{p['odds']:.2f}  %{round(p['prob']*100)}")
    else:
        cur = None
        total = 0
        for g, p in sorted(bets, key=lambda x: (x[0]["date_utc"], -x[1]["value"])):
            if g["id"] != cur:
                cur = g["id"]
                lines.append(f"\n<b>{g['away']['abbr']} @ {g['home']['abbr']}</b>  {_tr_time(g['date_utc'])}")
            note = f"  <i>({'; '.join(p['notes'][-1:])})</i>" if p.get("notes") else ""
            lines.append(f"• {p['player']} — {p['label']} <b>{p['line']}+</b> @{p['odds']:.2f} | "
                         f"%{round(p['prob']*100)} | değer {p['value']*100:+.0f}% | <b>{p['stake_tl']:.0f} ₺</b>{note}")
            total += p["stake_tl"]
        lines.append(f"\nToplam stake: <b>{total:.0f} ₺</b> (kasa {cfg['bankroll_tl']} ₺)")
    if cfg.get("site_url"):
        lines.append(cfg["site_url"])
    return "\n".join(lines)


def results_message(day):
    ps = [p for g in day["games"] for p in g["picks"] if p["result"] in ("Tuttu", "Tutmadı")]
    if not ps:
        return None
    hit = sum(p["result"] == "Tuttu" for p in ps)
    exp = sum(p["prob"] for p in ps)
    staked = [p for p in ps if p["stake_tl"] > 0]
    risk = sum(p["stake_tl"] for p in staked)
    pl = sum(p["stake_tl"] * (p["odds"] - 1) if p["result"] == "Tuttu" else -p["stake_tl"] for p in staked)
    lines = [f"🔮 <b>PropHet · {day['date']} sonuçları</b>", f"Tüm seçimler: {hit}/{len(ps)} tuttu (model beklentisi {exp:.1f})"]
    if staked:
        lines.append(f"Stake'li bahisler: {sum(p['result']=='Tuttu' for p in staked)}/{len(staked)} | "
                     f"K/Z <b>{pl:+.0f} ₺</b> ({risk:.0f} ₺ yatırıldı)")
        for p in staked:
            mark = "✅" if p["result"] == "Tuttu" else "❌"
            lines.append(f"{mark} {p['player']} {p['label']} {p['line']}+ → {p['actual']}")
    return "\n".join(lines)


def after_build(day, cfg):
    if not any(g.get("state", "pre") == "pre" and g["picks"] for g in day["games"]):
        return  # bekleyen maç yok
    st = _state()
    msg = picks_message(day, cfg)
    h = hashlib.md5(msg.encode()).hexdigest()
    if st["picks"].get(day["date"]) != h and send(cfg, msg):
        st["picks"][day["date"]] = h
        _save(st)


def after_grade(days, cfg):
    st = _state()
    for day in days:
        if day["date"] in st["results"]:
            continue
        if not all(p["result"] for g in day["games"] for p in g["picks"]):
            continue
        msg = results_message(day)
        if msg and send(cfg, msg):
            st["results"].append(day["date"])
            _save(st)
