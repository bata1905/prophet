# PropHet 🔮 — NBA oyuncu bahisleri

Her gün o günün bütün NBA maçları için oyuncu bahislerini (Sayı, Ribaund, Asist ve kombinasyonları) modelliyor, iddaa oranlarıyla karşılaştırıyor, değer ve stake hesaplıyor. Ertesi gün de sonuçları (tuttu/tutmadı, gerçek dakika) kendisi işliyor.

## Veri kaynakları
| Ne | Nereden | Not |
|---|---|---|
| Maç programı, kadro, sakatlık, maç logları, boxscore | ESPN'in herkese açık JSON API'si | Anahtar gerekmiyor |
| Oranlar | Nesine bülteni (iddaa, Türkiye'de yasal) | Resmi bir API değil, ilk kurulumda bir kez ayarlanması gerekiyor (aşağıda) |
| Oranlar (yedek) | `data/odds_manual.csv` | Nesine'den kopyalayıp elle girersin |

Hiç oran bulunamazsa model kendi "adil çizgisini" ve adil oranı gösterir (MODEL etiketi).

## Mac'te kurulum (bir kez)
```bash
cd nba-props
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python run.py --demo        # internetsiz örnek -> docs/demo.html
python run.py               # gerçek veri -> docs/index.html
```
`docs/index.html` dosyasını tarayıcıda aç.

## Nesine pazarları (ayarlı)
NBA lig kodu 138. Oyuncu pazarları: 717 Sayı, 718 Ribaund, 719 Asist, 720 Üçlük, 725 Sayı+Rib+Asist, 766 Ribaund+Asist (`config.json` → `nesine_market_map`).
Nesine yapıyı değiştirirse `python run.py --nesine-debug` ile kontrol et.

## ABD oranları (isteğe bağlı, önerilir)
https://the-odds-api.com → ücretsiz anahtar al → `secrets.json` → `"odds_api_key"`.
FanDuel/DraftKings vb. üst/alt oranlarından marjsız olasılık çıkarılır, iddaa çizgisine taşınır ve modelle harmanlanır
(ağırlık `model_weight_with_us`, varsayılan model %35 / ABD %65). Maç başı 6 kredi. Ücretsiz 500 kredi ≈ 1 hafta,
$30'lık plan tüm sezona yeter. `us_odds_ttl_hours` (20) → günde bir kez çekilir.

## Doğruluk takibi
- Sayfada **📈 Performans**: sonuçlanan *tüm* iddaa baremleri (yalnızca seçilenler değil) için kalibrasyon tablosu.
  "Model %60 dedi → gerçekte %?" Fark sütunu ±4 içindeyse model iyi kalibre.
- `python run.py --backtest`: geçen sezonun her maçını, o güne kadarki veriyle tahmin edip sonuçla karşılaştırır (5-15 dk).
- Geçmiş günler üstteki tarih düğmelerinde; sonuçlar `python run.py --grade-only` ile işlenir.

## Ayarlar (`config.json`)
- `bankroll_tl`: kasan (stake bunun yüzdesi olarak hesaplanır)
- `kelly_fraction`: 0.25 = çeyrek Kelly (tam Kelly çok oynaktır)
- `max_stake_pct`: tek bahiste kasanın en fazla bu kadarı (0.03 = %3)
- `min_edge`: stake önermek için gereken en düşük değer (0.03 = +%3)
- `picks_per_game`: maç başı seçim sayısı

## Telegram bildirimi
1. Telegram'da **@BotFather**'a `/newbot` yaz, isim ver. Sana bir **token** verir (`123456:ABC...`).
2. `secrets.example.json` dosyasını `secrets.json` adıyla kopyala, içine `"telegram_token": "BURAYA"` yaz. (Bu dosya GitHub'a yüklenmez.)
3. Yeni botuna Telegram'dan "merhaba" yaz.
4. `python run.py --telegram-setup` → çıkan **chat_id**'yi `config.json` → `"telegram_chat_id"` alanına (`secrets.json`) yaz.
5. `python run.py --telegram-test` ile dene.
Her gün öneriler (stake'li bahisler) ve ertesi sabah sonuçlar gelir. Seçimler değişmediyse aynı mesaj tekrar gönderilmez.

## Her gün otomatik çalışsın
**A) Mac'te (en kolay):** `bash otomatik_kur.sh` → her gün 10:00 (sonuçlar), 17:00 (seçimler), 00:30 (son sakatlık güncellemesi).
Mac uykudaysa uyandığında çalışır. Kayıtlar `data/log.txt`. Kaldırmak için: `bash otomatik_kur.sh kaldir`.
macOS arka plan işlerinin Masaüstü'ne erişmesini engeller. Klasör Masaüstü'ndeyse script sana taşıma komutlarını yazar.

**B) GitHub (Mac kapalıyken de çalışır):** repoya yükle → Settings → Secrets → Actions'a `TELEGRAM_TOKEN` ve `TELEGRAM_CHAT_ID` ekle →
Settings → Pages → Branch `main`, klasör `/docs`. GitHub sunucuları ABD'de. Nesine yurt dışı IP'yi engellerse oran gelmez, o zaman A'yı kullan.

## Model nasıl çalışıyor
1. **Dakika:** son maçların ağırlıklı ortalaması (yeni maç daha ağır), geçen sezon az ağırlıkla.
2. **Sakat takım arkadaşı:** rotasyondan biri *yeni* sakatlandıysa (son 2 maçta oynamışsa) dakikası ve üretimi kalanlara dağıtılır. Uzun süredir yoksa etkisi zaten veride olduğu için ekleme yapılmaz.
3. **Rakip + tempo:** iddaa'nın maç toplamı ve handikabından takımın beklenen sayısı çıkarılır, takımın ortalamasıyla oranlanır (Sayı/Üçlük tam, Asist %70, Ribaund tempoya göre). iddaa baremi yoksa rakibin yediği sayıya bakılır.
4. **Back-to-back:** dün oynayan takımda dakika %3, üretim %1.5 düşürülür.
5. **Dağılım:** negatif binom → P(istatistik ≥ çizgi). Değer = olasılık × oran − 1.
6. **Stake:** çeyrek Kelly. Limitler: tek bahis %3, oyuncu başı %4, maç başı %8, gün başı %20 (config'te). Aynı oyuncunun ikinci bahsi yarı stake alır (ilişkili oldukları için).

"Out/Doubtful" oyuncular çıkarılır, "Questionable/Day-To-Day" oyuncular **Riskli** etiketi alır. Oynamayan oyuncunun bahsi **İade** sayılır.

**Oynadım sütunu:** gerçekten oynadığın bahsi işaretle, tutarı yaz. "Benim K/Z" kartı gerçek sonucunu gösterir (bu tarayıcıda saklanır).

## Dürüst not
Model şeffaf ama basit. İlk 5 değişiklikleri, maç içi faul sorunu ve uzatma gibi şeyleri bilmez. Sezon başında örneklem küçük. Birkaç hafta "Toplam tutan" ile "Model beklentisi" kartlarını karşılaştır. Model iyi kalibre ise ikisi birbirine yakın olur. Bahis 18 yaş altına yasaktır.
