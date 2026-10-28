#!/bin/bash
# Mac'te her gün otomatik çalıştırma kurulumu.
#   10:00 -> gece biten maçları sonuçlandır (+ Telegram sonuç mesajı)
#   17:00 -> günün seçimleri (+ Telegram öneri mesajı)
#   00:30 -> son sakatlık haberleriyle güncelle
# Kaldırmak için:  bash otomatik_kur.sh kaldir
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST="$HOME/Library/LaunchAgents/com.prophet.daily.plist"

if [ "$1" = "kaldir" ]; then
  launchctl unload "$PLIST" 2>/dev/null || true
  rm -f "$PLIST"
  echo "Otomatik çalışma kaldırıldı."
  exit 0
fi

case "$DIR" in
  "$HOME/Desktop"*|"$HOME/Documents"*|"$HOME/Downloads"*)
    echo "macOS, arka planda çalışan işlerin Masaüstü/Belgeler/İndirilenler'e erişmesini engelliyor."
    echo "Klasörü ana klasörüne taşıyıp kurulumu orada yap (aşağıdakileri sırayla yapıştır):"
    echo "  mv \"$DIR\" ~/nba-props"
    echo "  cd ~/nba-props && rm -rf .venv && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
    echo "  bash otomatik_kur.sh"
    exit 1;;
esac

if [ ! -x "$DIR/.venv/bin/python" ]; then
  echo "Önce kurulumu yap: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

mkdir -p "$HOME/Library/LaunchAgents" "$DIR/data"
cat > "$DIR/gunluk.sh" <<SH
#!/bin/bash
cd "$DIR"
H=\$(date +%H)
if [ "\$H" -ge 6 ] && [ "\$H" -lt 13 ]; then ARG="--grade-only"; else ARG=""; fi
echo "=== \$(date) \$ARG" >> data/log.txt
"$DIR/.venv/bin/python" run.py \$ARG >> data/log.txt 2>&1
bash "$DIR/yayinla.sh" >> data/log.txt 2>&1
SH
chmod +x "$DIR/gunluk.sh"

cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.prophet.daily</string>
  <key>ProgramArguments</key><array><string>/bin/bash</string><string>$DIR/gunluk.sh</string></array>
  <key>StartCalendarInterval</key><array>
    <dict><key>Hour</key><integer>10</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Hour</key><integer>17</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Hour</key><integer>0</integer><key>Minute</key><integer>30</integer></dict>
  </array>
</dict></plist>
PL
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
echo "Tamam. Her gün 10:00, 17:00 ve 00:30'da çalışacak (Mac uykudaysa uyandığında çalışır)."
echo "Kayıtlar: data/log.txt  |  Hemen denemek için: bash gunluk.sh"
