#!/bin/bash
# Sayfayı ve tahmin kayıtlarını GitHub'a gönderir (GitHub Pages sitesi güncellenir).
cd "$(dirname "$0")"
[ -d .git ] || { echo "Bu klasör henüz GitHub'a bağlı değil (README: GitHub kurulumu)."; exit 0; }
git add docs data/picks data/notified.json data/backtest.json 2>/dev/null
git commit -qm "PropHet güncelleme $(date '+%Y-%m-%d %H:%M')" || { echo "Yeni değişiklik yok."; exit 0; }
git push -q && echo "Site güncellendi."
