# InSAR Masaüstü

Sentinel-1 verisinden D-InSAR deformasyon haritası üreten masaüstü uygulaması.
Ağır işlemi NASA/ASF **HyP3** bulutu yapar; bilgisayarınıza yalnızca bitmiş GeoTIFF'ler iner.

## Kurulum

Python 3.10+ gerekir. Windows'ta `rasterio` kurulumu için en sorunsuz yol conda'dır.

```bash
# Seçenek A: pip
python -m venv venv
venv\Scripts\activate          # Linux/macOS: source venv/bin/activate
pip install -r requirements.txt

# Seçenek B: conda (Windows için önerilen)
conda create -n insar -c conda-forge python=3.11 rasterio numpy matplotlib pillow
conda activate insar
pip install PySide6 hyp3_sdk asf_search
```

## Earthdata girişi

1. https://urs.earthdata.nasa.gov adresinden ücretsiz hesap açın.
2. Aynı hesapla https://hyp3-api.asf.alaska.edu adresine bir kez girip kullanım koşullarını onaylayın.
3. Uygulamaya giriş için üç yoldan biri:
   - **Token (önerilen):** Earthdata profilinizde *Generate Token* → uygulamada "Giriş Yap" → Token alanı.
     Kalıcı yapmak için `EARTHDATA_TOKEN` ortam değişkenine yazın; uygulama açılışta otomatik bağlanır.
   - **.netrc dosyası:** ev dizininizde (Windows: `C:\Users\<siz>\_netrc`)
     ```
     machine urs.earthdata.nasa.gov login KULLANICI password ŞİFRE
     ```
   - **Kullanıcı adı / şifre:** "Giriş Yap" penceresinden (kaydedilmez).

## Çalıştırma

```bash
python main.py
```

## Kullanım

1. Haritanın solundaki **▭** aracıyla analiz alanını çizin (veya "enlem, boylam" yazıp **Git**).
2. **Tarih 1** (olay öncesi) ve **Tarih 2** (olay sonrası) seçin → **Sentinel-1 Sahnelerini Bul**.
   Seçilen tarihlerin ±6 günü içinde, aynı yörünge/çerçeveden gelen çiftler listelenir.
3. Çifti seçip **Analizi Başlat**. Önbellekte varsa anında açılır; yoksa HyP3'e iş gönderilir
   (genelde 15–40 dk). Uygulamayı kapatsanız bile iş bulutta sürer; tekrar açtığınızda takip kaldığı yerden devam eder.
4. **Sonuçlar** listesinden katman seçin (LOS / düşey / faz / koherens), haritaya tıklayarak noktasal değeri (mm) görün.
5. **Kaydırmalı karşılaştırma** kutusunu işaretleyip sağ taraf için başka bir sonuç seçin; alttaki çubukla kaydırın.
   İki taraf aynı renk skalasıyla çizilir, böylece renkler doğrudan kıyaslanabilir.

## Dosyalar ve önbellek

Tüm sonuçlar `~/InSAR_Masaustu/outputs/{alan_kodu}_{tarih1}_{tarih2}/` altında tutulur
(`INSAR_DATA_DIR` ortam değişkeniyle değiştirilebilir). Her klasörde HyP3'ün GeoTIFF'leri
(QGIS/ArcGIS'te doğrudan açılır) ve `meta.json` bulunur.

## Bilmeniz gerekenler

- **Kredi:** HyP3 her ay ücretsiz kredi verir; kalan miktar sol panelde görünür.
- **İşaret:** LOS'ta pozitif = uyduya yaklaşma, negatif = uzaklaşma. Düşey katman, hareketin tamamen düşey olduğu varsayımıyla hesaplanır.
- **Koherens < 0.3** olan yerlerde değerler güvenilmezdir (bitki örtüsü, kar, büyük yer değiştirme).
- Değerler, HyP3'ün seçtiği referans noktasına göre **görelidir**.
- Uydu altlık haritası için internet gerekir; harita kütüphanesi (Leaflet) uygulamanın içinde gömülüdür.

## Kurulum dosyası (.exe) üretmek

```bash
pip install pyinstaller
pyinstaller --name "InSAR Masaustu" --windowed --add-data "insar/ui;insar/ui" main.py
```
(Linux/macOS'ta `--add-data "insar/ui:insar/ui"`.) Çıktı `dist/` klasöründedir.

## Proje yapısı

```
main.py                 başlatıcı
insar/config.py         klasörler ve ayarlar
insar/search.py         ASF sahne arama + çift eşleştirme
insar/processing.py     HyP3 iş gönderme / takip / indirme
insar/cache.py          önbellek ve bekleyen işler
insar/raster.py         GeoTIFF → harita katmanı, noktadan değer okuma
insar/workers.py        arka plan iş parçacıkları
insar/ui/main_window.py arayüz
insar/ui/map.html       Leaflet harita (çizim, kaydırma, lejant)
```
