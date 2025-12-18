Du bist mein „Cloud-Run Service Generator“ für data-tales.dev.

KONTEXT
Ich habe unten ein Python-Snippet angehängt, das aktuell als Dash-Seitenmodul („register_page“) läuft und mehrere OGC-Dienste (WMS/WFS) inspiziert. Es enthält Windows-Dateipfade, Dash-UI-Code und schreibt JSON-Dateien lokal weg. Das soll zu einer schlanken, auf Google Cloud Run (Source Deploy, ohne Dockerfile) lauffähigen Mini-Webapp umgebaut werden.

INPUT (von mir)
A) Ein einzelnes Python-Skript (unten), das aktuell NICHT als Flask-Webapp läuft (Dash-Modul, lokale Dateipfade, Offline-Cache).
B) Vorhandene Services + Landing URLs:
   - LANDING_URL = "https://data-tales.dev/"
   - COOKBOOK_URL = "https://data-tales.dev/cookbook/"
   - SERVICES:
     - "PLZ → Koordinaten" -> "https://plz.data-tales.dev/"
     - Hinweis: Weitere Service-Einträge im Prompt können Platzhalter enthalten (z.B. "<Service 2 Name>"). Diese NICHT verwenden/anzeigen.
C) Styling-Referenz: Meine Landing Page nutzt CSS-Variablen und Komponenten. Du musst diese Variablen/Klassen 1:1 einbetten (siehe Abschnitt „LANDING STYLE CSS“ unten).

ZIEL
Wandle das angehängte Skript in ein vollständiges, lauffähiges Mini-Webprojekt um, das auf Google Cloud Run deploybar ist (Source Deploy, ohne Dockerfile), mit:
- Flask Backend + Gunicorn Start (Cloud Run kompatibel; PORT via env)
- einer HTML-Oberfläche für den User (ohne externe Template-Dateien; nutze render_template_string)
- einem einheitlichen Header (sticky, blur, gleiche Variablen/Buttons wie Landing Page)
- Theme Toggle (dark/light) mit localStorage, identisch zum Landing-Verhalten
- Navigation: Links zur Landing Page + Cookbook + Links zu den realen Services aus SERVICES (nur echte URLs; keine "<...>" Platzhalter)
- sauberer Validierung + Fehleranzeige im UI
- optional: /api Endpunkt als JSON (für spätere Integration)

APP-FOKUS (funktional)
Diese App ist ein „OGC Service Explorer“:
- Sie soll die in meinem Skript enthaltenen OGC-Endpunkte (WMS/WFS) als vordefinierte Auswahl anbieten und deren Capabilities auslesen.
- Ergebnis: Übersicht (Tabelle) der verfügbaren Layer/FeatureTypes je Service.
- Minimaler Funktionsumfang, aber robust:
  1) Auswahl/Abfrage eines Services
  2) Anzeigen der Layer/FeatureTypes (Name/Identifier + Title; optional Styles bei WMS)
  3) Filter-/Suchfeld im UI (clientseitig via JS reicht)
  4) /api liefert dieselben Daten als JSON

WICHTIG: Entferne/ersetze diese NICHT Cloud-Run-kompatiblen Teile aus dem Skript:
- Dash (dash, dcc, dash_table, dash_bootstrap_components, register_page, navigation.navbar)
- lokale Windows-Dateipfade zu JSON (OBS_DEU_PT10M_T2M_properties.json etc.)
- Schreiben/Lesen von Cache-Dateien an feste Pfade (nutze stattdessen In-Memory Cache, z.B. functools.lru_cache; optional /tmp falls wirklich nötig)

OGC-ENDPOINTS (aus dem Skript; exakt übernehmen)
WFS_DWD = "https://maps.dwd.de/geoserver/wfs?SERVICE=WFS"
WMS_DWD = "https://maps.dwd.de/geoserver/wms?SERVICE=WMS"
WFS_CDC = "https://cdc.dwd.de/geoserver/ows?service=WFS"
WMS_CDC = "https://cdc.dwd.de/geoserver/ows?service=WMS"
WFS_HLNUG_WATER = "https://inspire-hessen.de/ows/services/org.2.afb44ba2-6e6a-4493-98af-da5a88b955fc_wfs?"
WFS_PEGEL = "https://www.pegelonline.wsv.de/webservices/gis/aktuell/wfs"
WMS_PEGEL = "https://www.pegelonline.wsv.de/webservices/gis/wms/aktuell/mnwmhw?request=GetCapabilities&service=WMS"
WFS_HYDRONOTE_NL = "https://haleconnect.com/ows/services/org.292.c3955762-73a3-4c16-a15c-f3869487a1e3_wfs?SERVICE=WFS"
WMS_HYNETWORK_NL = "https://haleconnect.com/ows/services/org.292.c3955762-73a3-4c16-a15c-f3869487a1e3_wms?SERVICE=WMS"
WFS_WATERCOURSELINK_NL = "https://haleconnect.com/ows/services/org.292.c3955762-73a3-4c16-a15c-f3869487a1e3_wfs"

SERVICE_META (für diese neue App; exakt so verwenden)
- service_name_slug: "data-sources"
- page_title: "OGC Datenquellen Explorer"
- page_h1: "OGC Datenquellen"
- page_subtitle: "Layer- und FeatureType-Übersicht für ausgewählte WMS/WFS-Dienste."

ERWARTETES VERHALTEN IM BROWSER
- Seite zeigt ein Auswahlfeld (Dropdown) für den vordefinierten Service + optional ein Textfeld für Custom-URL (nur wenn sicher umsetzbar; sonst weglassen).
- Nach Klick auf „Abrufen“ wird entweder Ergebnis (Card mit Tabelle + Stats) angezeigt oder Fehler (Card).
- Ergebnis ist auch als JSON über /api abrufbar.
- Header sieht aus wie Landing Page und verlinkt sinnvoll.

SICHERHEIT / ROBUSTNESS (verbindlich)
- Strikte Validierung:
  - Wenn du Custom-URL anbietest: nur https, maximale Länge begrenzen, keine Credentials, keine lokalen IPs; idealerweise allowlist der Hosts aus den vordefinierten URLs.
  - Wenn kein Custom-URL: nur vordefinierte Auswahl zulassen.
- Externe Calls:
  - HTTP timeouts setzen (connect + read)
  - verständliche Fehlermeldungen; keine Stacktraces im UI
- Caching:
  - lru_cache für Capabilities-Requests oder geparste Ergebnisse (Key = normalisierte URL)
  - Möglichkeit zum Refresh per Query-Param (z.B. refresh=1), der den Cache für diesen Key umgeht

API (verbindlich)
- GET /api?service=<key>&refresh=0|1
- service ist ein Schlüssel (z.B. dwd_wms, dwd_wfs, cdc_wms, cdc_wfs, hlnug_wfs_water, pegel_wfs, pegel_wms, hydronote_nl_wfs, hynetwork_nl_wms, watercourselink_nl_wfs)
- Response:
  - { "ok": true, "service": {...}, "counts": {...}, "items": [ ... ] }
  - oder { "ok": false, "error": "..." }

TECHNISCHE IMPLEMENTATION (verbindliche Leitplanken)
- Flask App in main.py, exportiert app
- Cloud Run Start: gunicorn -b :$PORT main:app
- Keine externen Template-Dateien; nutze render_template_string
- Keine Datenbank, keine externen APIs außer den OGC-Endpunkten oben
- Anforderungen so klein wie möglich halten:
  - bevorzugt: requests + xml.etree.ElementTree zum Parsen der Capabilities (WMS/WFS)
  - Alternativ ist owslib ok, aber nur wenn Timeouts sauber gesetzt werden können
- UI:
  - Layout zentriert in .container
  - Ergebnis/Fehler als .card
  - Tabellen-Rendering als HTML (mit minimalem JS-Filter)
  - Keine Drittanbieter-CDNs, keine externen CSS/JS Frameworks

HEADER / NAV (verbindlich)
- Header-Klassen semantisch wie Landing Page:
  - .site-header, .container, .header-inner, .brand, .brand-mark, .nav, .header-actions, .btn, .btn-primary, .btn-ghost
- Links:
  - Brand klickt auf LANDING_URL
  - Nav enthält: "Landing" (LANDING_URL), "Cookbook" (COOKBOOK_URL), "PLZ → Koordinaten" (https://plz.data-tales.dev/)
  - Wenn >6 reale Services vorhanden wären: nur die ersten 6 + "Mehr…" -> LANDING_URL + "#projects" (hier vermutlich nicht nötig, aber implementiere die Logik robust)
- Rechtes Ende:
  - Theme Toggle Button (☾/☀)
  - optional: Primary Button „Kontakt“ -> LANDING_URL + "#contact"

THEME TOGGLE (verbindlich)
- setzt data-theme="light" auf document.documentElement (oder entfernt es) genau wie auf der Landing Page
- speichert theme in localStorage
- initialisiert Theme beim Laden anhand localStorage

LANDING STYLE CSS (muss verwendet werden)
Ich hänge hier die kompletten CSS-Variablen und relevanten Klassen aus der Landing Page an. Du musst sie 1:1 übernehmen, aber entferne Variablen, die du in dieser App nicht nutzt. Du darfst minimal ergänzen (z.B. .content, .result, .table, .form-row), aber NICHT den Look verändern.

[HIER KOMMT DER CSS-BLOCK AUS MEINER LANDING PAGE REIN – UNVERÄNDERT]

AUSGABEFORMAT (sehr wichtig)
Gib AUSSCHLIESSLICH die folgenden Dateien aus, jeweils in einem eigenen Codeblock mit Dateiname als Überschrift:
1) requirements.txt
2) main.py
3) README.md
Keine weiteren Erklärtexte außerhalb der Dateien.

README-VORGABEN (verbindlich)
- Kurzer Zweck (1–2 Sätze)
- Lokales Starten:
  - python -m venv .venv
  - pip install
  - python main.py
  - URL nennen (http://127.0.0.1:8080)
- Cloud Run Deploy (Source):
  - gcloud run deploy data-sources --source . --region europe-west1 --allow-unauthenticated
- Hinweis auf env vars (falls genutzt), z.B. USER_AGENT
- Optional: Domain mapping Hinweis „Subdomain -> Cloud Run“

WICHTIG
- Schreibe keine generischen Platzhalter-Links. Nutze exakt die oben angegebenen URLs.
- Ignoriere/unterdrücke Service-Einträge mit "<...>".
- Liefere lauffähigen Code ohne TODOs.

ANHANG: PYTHON SCRIPT (zu transformieren)
[PASTE: mein gesamtes Skript von unten – unverändert]
