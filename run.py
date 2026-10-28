"""NBA oyuncu bahisleri — günlük çalıştırma.

  python run.py                 # dünü sonuçlandır, bugünün maçlarını tahmin et, docs/index.html üret
  python run.py --date 2026-10-30
  python run.py --grade-only    # sadece sonuçları güncelle
  python run.py --nesine-debug  # Nesine bültenini indir, oyuncu pazarlarının yapısını göster
  python run.py --demo          # internetsiz örnek sayfa (sahte oyuncular)
  python run.py --backtest      # geçen sezon üzerinde doğruluk testi (sayfada 📈 Performans)
  python run.py --telegram-setup  # Telegram chat_id'ni bul
  python run.py --telegram-test   # bugünün mesajını Telegram'a gönder
"""
import argparse
import datetime as dt
import json
import os
import sys
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from nbaprops import espn, pipeline, render  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="ABD maç günü (YYYY-AA-GG). Varsayılan: New York'taki bugün")
    ap.add_argument("--grade-only", action="store_true")
    ap.add_argument("--nesine-debug", action="store_true")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--telegram-setup", action="store_true")
    ap.add_argument("--backtest", action="store_true", help="geçen sezon üzerinde test")
    ap.add_argument("--telegram-test", action="store_true")
    a = ap.parse_args()

    with open(os.path.join(HERE, "config.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    # Gizli anahtarlar ayrı dosyada (GitHub'a yüklenmez): secrets.json
    sp = os.path.join(HERE, "secrets.json")
    if os.path.exists(sp):
        with open(sp, encoding="utf-8") as f:
            cfg.update({k: v for k, v in json.load(f).items() if v})

    if a.demo:
        from nbaprops import demo
        print("Demo sayfa:", demo.run(cfg))
        return

    date = dt.date.fromisoformat(a.date) if a.date else dt.datetime.now(ZoneInfo("America/New_York")).date()

    if a.nesine_debug:
        from nbaprops import odds
        odds.nesine_debug()
        return

    if a.backtest:
        from nbaprops import backtest
        backtest.run(cfg)
        print("Sayfa:", render.render())
        return

    from nbaprops import notify
    if a.telegram_setup:
        notify.setup(cfg)
        return
    if a.telegram_test:
        day = pipeline.load_day(date.isoformat())
        ok = notify.send(cfg, notify.picks_message(day, cfg) if day else "Test mesajı ✅")
        print("Gönderildi" if ok else "Gönderilemedi: secrets.json'daki telegram_token / telegram_chat_id'yi kontrol et")
        return

    days = pipeline.grade()
    notify.after_grade(days, cfg)
    if not a.grade_only:
        day = pipeline.build_day(date, cfg)
        notify.after_build(day, cfg)
    print("Sayfa:", render.render())


if __name__ == "__main__":
    main()
