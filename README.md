# OGC Datenquellen Explorer (data-sources)

Schlanke Flask-Webapp zum Abrufen und Anzeigen von WMS/WFS Capabilities (Layer/FeatureTypes) für vordefinierte OGC-Endpunkte – Cloud-Run-kompatibel (Source Deploy, ohne Dockerfile).

## Lokal starten

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

pip install -r requirements.txt
python main.py
