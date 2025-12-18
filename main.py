# main.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
from functools import lru_cache
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

import requests
from flask import Flask, jsonify, request, render_template_string

APP_META = {
    "service_name_slug": "data-sources",
    "page_title": "OGC Datenquellen Explorer",
    "page_h1": "OGC Datenquellen",
    "page_subtitle": "Layer- und FeatureType-Übersicht für ausgewählte WMS/WFS-Dienste.",
}


SERVICES_NAV = [
    ("PLZ → Koordinaten", "https://plz.data-tales.dev/"),
    ("OSM Baumbestand", "https://tree-locator.data-tales.dev/"),
]

OGC_SERVICES = {
    "dwd_wfs": {
        "label": "DWD GeoServer (WFS)",
        "kind": "wfs",
        "url": "https://maps.dwd.de/geoserver/wfs?SERVICE=WFS",
    },
    "dwd_wms": {
        "label": "DWD GeoServer (WMS)",
        "kind": "wms",
        "url": "https://maps.dwd.de/geoserver/wms?SERVICE=WMS",
    },
    "cdc_wfs": {
        "label": "DWD CDC GeoServer (WFS)",
        "kind": "wfs",
        "url": "https://cdc.dwd.de/geoserver/ows?service=WFS",
    },
    "cdc_wms": {
        "label": "DWD CDC GeoServer (WMS)",
        "kind": "wms",
        "url": "https://cdc.dwd.de/geoserver/ows?service=WMS",
    },
    "pegel_wfs": {
        "label": "Pegelonline (WFS)",
        "kind": "wfs",
        "url": "https://www.pegelonline.wsv.de/webservices/gis/aktuell/wfs",
    },
    "pegel_wms": {
        "label": "Pegelonline (WMS)",
        "kind": "wms",
        "url": "https://www.pegelonline.wsv.de/webservices/gis/wms/aktuell/mnwmhw?request=GetCapabilities&service=WMS",
    },
    "hydronote_nl_wfs": {
        "label": "Haleconnect Hydronote NL (WFS)",
        "kind": "wfs",
        "url": "https://haleconnect.com/ows/services/org.292.c3955762-73a3-4c16-a15c-f3869487a1e3_wfs?SERVICE=WFS",
    },
    "hynetwork_nl_wms": {
        "label": "Haleconnect HyNetwork NL (WMS)",
        "kind": "wms",
        "url": "https://haleconnect.com/ows/services/org.292.c3955762-73a3-4c16-a15c-f3869487a1e3_wms?SERVICE=WMS",
    },
    "watercourselink_nl_wfs": {
        "label": "Haleconnect WatercourseLink NL (WFS)",
        "kind": "wfs",
        "url": "https://haleconnect.com/ows/services/org.292.c3955762-73a3-4c16-a15c-f3869487a1e3_wfs",
    },

    # ---------------------------------------------------------------------
    # Deutschland (Bund) – BKG / GeoBasis-DE (Basiskarten, Grenzen, INSPIRE)
    # ---------------------------------------------------------------------
    "bkg_topplus_open_wms": {
        "label": "GeoBasis-DE / BKG TopPlusOpen (WMS)",
        "kind": "wms",
        "url": "https://sgx.geodatenzentrum.de/wms_topplus_open?SERVICE=WMS",
    },
    "bkg_basemapde_wms": {
        "label": "GeoBasis-DE / BKG basemap.de (WMS)",
        "kind": "wms",
        "url": "https://sgx.geodatenzentrum.de/wms_basemapde?SERVICE=WMS",
    },

    "bkg_vg250_wms": {
        "label": "GeoBasis-DE / BKG Verwaltungsgebiete VG250 (WMS)",
        "kind": "wms",
        "url": "https://sgx.geodatenzentrum.de/wms_vg250?SERVICE=WMS",
    },
    "bkg_vg250_wfs": {
        "label": "GeoBasis-DE / BKG Verwaltungsgebiete VG250 (WFS)",
        "kind": "wfs",
        "url": "https://sgx.geodatenzentrum.de/wfs_vg250?SERVICE=WFS",
    },

    "bkg_gn250_wms": {
        "label": "GeoBasis-DE / BKG Geographische Namen GN250 (WMS)",
        "kind": "wms",
        "url": "https://sgx.geodatenzentrum.de/wms_gn250?SERVICE=WMS",
    },
    "bkg_gn250_inspire_wms": {
        "label": "GeoBasis-DE / BKG INSPIRE Geographical Names GN250 (WMS)",
        "kind": "wms",
        "url": "https://sg.geodatenzentrum.de/wms_gn250_inspire?SERVICE=WMS",
    },
    "bkg_gn250_inspire_wfs": {
        "label": "GeoBasis-DE / BKG INSPIRE Geographical Names GN250 (WFS)",
        "kind": "wfs",
        "url": "https://sg.geodatenzentrum.de/wfs_gn250_inspire?SERVICE=WFS",
    },

    "bkg_dlm250_inspire_wfs": {
        "label": "GeoBasis-DE / BKG INSPIRE DLM250 (WFS)",
        "kind": "wfs",
        "url": "https://sgx.geodatenzentrum.de/wfs_dlm250_inspire?SERVICE=WFS",
    },
    "bkg_dlm250_inspire_wms": {
        "label": "GeoBasis-DE / BKG INSPIRE DLM250 (WMS)",
        "kind": "wms",
        "url": "https://sgx.geodatenzentrum.de/wms_dlm250_inspire?SERVICE=WMS",
    },

    # ---------------------------------------------------------------------
    # Deutschland (Bund) – BfN Schutzgebiete (Protected Sites)
    # ---------------------------------------------------------------------
    "bfn_schutzgebiete_wms": {
        "label": "BfN Schutzgebiete Deutschland (WMS)",
        "kind": "wms",
        "url": "https://geodienste.bfn.de/ogc/wms/schutzgebiet?SERVICE=WMS",
    },
    "bfn_schutzgebiete_wfs": {
        "label": "BfN Schutzgebiete Deutschland (WFS)",
        "kind": "wfs",
        "url": "https://geodienste.bfn.de/ogc/wfs/schutzgebiet?SERVICE=WFS",
    },

    # ---------------------------------------------------------------------
    # Deutschland (Bund) – Thünen Atlas (GeoServer; viele Layer WMS/WFS)
    # ---------------------------------------------------------------------
    "thuenen_atlas_wms": {
        "label": "Thünen Atlas GeoServer (WMS)",
        "kind": "wms",
        "url": "https://atlas.thuenen.de/geoserver/wms?SERVICE=WMS",
    },
    "thuenen_atlas_wfs": {
        "label": "Thünen Atlas GeoServer (WFS)",
        "kind": "wfs",
        "url": "https://atlas.thuenen.de/geoserver/wfs?SERVICE=WFS",
    },

    # ---------------------------------------------------------------------
    # Deutschland (Bund) – Umweltbundesamt (UBA) datahub (ArcGIS WMSServer)
    # ---------------------------------------------------------------------
    "uba_gwn_wms": {
        "label": "UBA datahub – Grundwasserneubildung (WMS)",
        "kind": "wms",
        "url": "https://datahub.uba.de/server/services/Wa/GWN/MapServer/WMSServer?SERVICE=WMS",
    },
    "uba_stickstoff_wms": {
        "label": "UBA datahub – Hintergrundbelastung Stickstoff (WMS)",
        "kind": "wms",
        "url": "https://datahub.uba.de/server/services/Lu/Hintergrundbelastungsdaten_Stickstoff/MapServer/WMSServer?SERVICE=WMS",
    },

    # ---------------------------------------------------------------------
    # Deutschland (Bund) – BGR (Beispiel: Bodenkarte; WMS)
    # ---------------------------------------------------------------------
    "bgr_buek1000_wms": {
        "label": "BGR – Boden (BUEK1000) (WMS)",
        "kind": "wms",
        "url": "https://services.bgr.de/wms/boden/buek1000en/?SERVICE=WMS",
    },

    # ---------------------------------------------------------------------
    # Forschung/EO – DLR & EUMETSAT (WMS/WFS)
    # ---------------------------------------------------------------------
    "dlr_eoc_land_wms": {
        "label": "DLR EOC Land (WMS)",
        "kind": "wms",
        "url": "https://geoservice.dlr.de/eoc/land/wms?SERVICE=WMS",
    },
    "dlr_eoc_land_wfs": {
        "label": "DLR EOC Land (WFS)",
        "kind": "wfs",
        "url": "https://geoservice.dlr.de/eoc/land/wfs?SERVICE=WFS",
    },
    "eumetsat_view_wms": {
        "label": "EUMETSAT view GeoServer (WMS)",
        "kind": "wms",
        "url": "https://view.eumetsat.int/geoserver/ows?SERVICE=WMS",
    },
    "eumetsat_view_wfs": {
        "label": "EUMETSAT view GeoServer (WFS)",
        "kind": "wfs",
        "url": "https://view.eumetsat.int/geoserver/ows?SERVICE=WFS",
    },

    # ---------------------------------------------------------------------
    # Europa – EEA/Discomap (WMS; CORINE/Natura2000)
    # ---------------------------------------------------------------------
    "eea_corine_clc2018_wms": {
        "label": "EEA Discomap – CORINE Land Cover 2018 (WMS)",
        "kind": "wms",
        "url": "https://image.discomap.eea.europa.eu/arcgis/services/Corine/CLC2018_WM/MapServer/WMSServer?SERVICE=WMS",
    },
    "eea_natura2000_wms": {
        "label": "EEA Discomap – Natura 2000 (WMS)",
        "kind": "wms",
        "url": "https://copernicus.discomap.eea.europa.eu/arcgis/services/Natura2000/N2K_2018/MapServer/WMSServer?SERVICE=WMS",
    },

    # ---------------------------------------------------------------------
    # Europa – Copernicus Emergency Management Service (Public WMS)
    # ---------------------------------------------------------------------
    "copernicus_effis_wms": {
        "label": "Copernicus EMS – EFFIS (Wildfires) (WMS)",
        "kind": "wms",
        "url": "https://maps.effis.emergency.copernicus.eu/effis?SERVICE=WMS",
    },
    "copernicus_efas_wms": {
        "label": "Copernicus EMS – EFAS (Flood) (WMS)",
        "kind": "wms",
        "url": "https://european-flood.emergency.copernicus.eu/api/wms/?SERVICE=WMS",
    },
    "copernicus_drought_wms": {
        "label": "Copernicus EMS – European Drought Observatory (WMS)",
        "kind": "wms",
        "url": "https://drought.emergency.copernicus.eu/api/wms?SERVICE=WMS",
    },

    # ---------------------------------------------------------------------
    # Europa – EMODnet (Marine; WMS/WFS)
    # ---------------------------------------------------------------------
    "emodnet_bathymetry_wms": {
        "label": "EMODnet Bathymetry (WMS)",
        "kind": "wms",
        "url": "https://ows.emodnet-bathymetry.eu/wms?SERVICE=WMS",
    },
    "emodnet_bathymetry_wfs": {
        "label": "EMODnet Bathymetry (WFS)",
        "kind": "wfs",
        "url": "https://ows.emodnet-bathymetry.eu/wfs?SERVICE=WFS",
    },
}


DEFAULT_TIMEOUT = (3.05, 18)  # (connect, read)
MAX_URL_LEN = 400


def _ua() -> str:
    return os.environ.get(
        "USER_AGENT",
        "data-tales.dev (data-sources) - OGC Service Explorer",
    )


def _build_url(base_url: str, updates: dict) -> str:
    if not base_url or len(base_url) > MAX_URL_LEN:
        raise ValueError("Ungültige Service-URL.")

    parts = urlsplit(base_url)
    if parts.scheme.lower() != "https":
        raise ValueError("Nur https:// URLs sind erlaubt.")

    q = dict((k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True))
    for k, v in updates.items():
        q[k] = v

    query = urlencode(q, doseq=True)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))


def _safe_int(v: str, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _local(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def _child_text(elem, child_local_name: str) -> str | None:
    for c in list(elem):
        if _local(c.tag) == child_local_name:
            t = (c.text or "").strip()
            return t if t else None
    return None


def _iter_children(elem, child_local_name: str):
    for c in list(elem):
        if _local(c.tag) == child_local_name:
            yield c


def _find_first(elem, local_name: str):
    for e in elem.iter():
        if _local(e.tag) == local_name:
            return e
    return None


def _find_all(elem, local_name: str):
    for e in elem.iter():
        if _local(e.tag) == local_name:
            yield e


def _fetch_xml(url: str) -> bytes:
    r = requests.get(
        url,
        headers={"User-Agent": _ua(), "Accept": "application/xml,text/xml,*/*;q=0.9"},
        timeout=DEFAULT_TIMEOUT,
    )
    r.raise_for_status()
    return r.content


def _parse_wms(xml_bytes: bytes) -> tuple[list[dict], str | None]:
    import xml.etree.ElementTree as ET

    root = ET.fromstring(xml_bytes)
    cap = _find_first(root, "Capability") or root

    top_layer = None
    for e in cap.iter():
        if _local(e.tag) == "Layer":
            top_layer = e
            break

    items: list[dict] = []

    def walk(layer_elem, inherited_title: str | None = None):
        name = _child_text(layer_elem, "Name")
        title = _child_text(layer_elem, "Title") or inherited_title

        styles = []
        for s in _iter_children(layer_elem, "Style"):
            s_name = _child_text(s, "Name") or ""
            s_title = _child_text(s, "Title") or ""
            if s_name or s_title:
                styles.append({"name": s_name, "title": s_title})

        if name:
            items.append(
                {
                    "type": "wms_layer",
                    "name": name,
                    "title": title or "",
                    "styles": styles,
                }
            )

        for child_layer in _iter_children(layer_elem, "Layer"):
            walk(child_layer, title)

    if top_layer is not None:
        walk(top_layer, None)

    version = root.attrib.get("version") or root.attrib.get("Version")
    return items, version


def _parse_wfs(xml_bytes: bytes) -> tuple[list[dict], str | None]:
    import xml.etree.ElementTree as ET

    root = ET.fromstring(xml_bytes)
    version = root.attrib.get("version") or root.attrib.get("Version")

    items: list[dict] = []
    ft_list = _find_first(root, "FeatureTypeList")
    if ft_list is None:
        feature_types = list(_find_all(root, "FeatureType"))
    else:
        feature_types = list(_iter_children(ft_list, "FeatureType"))

    for ft in feature_types:
        name = _child_text(ft, "Name") or ""
        title = _child_text(ft, "Title") or ""
        default_crs = _child_text(ft, "DefaultCRS") or _child_text(ft, "DefaultSRS") or ""
        if name:
            items.append(
                {
                    "type": "wfs_featuretype",
                    "name": name,
                    "title": title,
                    "default_crs": default_crs,
                }
            )

    return items, version


@lru_cache(maxsize=64)
def _get_service_data_cached(service_key: str, cache_token: int) -> dict:
    svc = OGC_SERVICES.get(service_key)
    if not svc:
        raise ValueError("Unbekannter Service.")

    kind = svc["kind"]
    base_url = svc["url"]

    if kind == "wms":
        versions = ["1.3.0", "1.1.1", ""]
        last_err = None
        for v in versions:
            try:
                cap_url = _build_url(
                    base_url,
                    {
                        "service": "WMS",
                        "request": "GetCapabilities",
                        **({"version": v} if v else {}),
                    },
                )
                xml_bytes = _fetch_xml(cap_url)
                items, parsed_version = _parse_wms(xml_bytes)
                return {
                    "ok": True,
                    "service": {
                        "key": service_key,
                        "label": svc["label"],
                        "kind": kind,
                        "url": base_url,
                        "capabilities_url": cap_url,
                        "version": parsed_version or (v or None),
                    },
                    "counts": {
                        "items": len(items),
                        "styles": sum(len(it.get("styles", [])) for it in items),
                    },
                    "items": sorted(items, key=lambda x: x.get("name", "")),
                    "fetched_at": int(time.time()),
                }
            except Exception as e:
                last_err = e
                continue
        raise RuntimeError(f"WMS Capabilities konnten nicht geladen werden: {str(last_err)[:220]}")

    if kind == "wfs":
        versions = ["2.0.0", "1.1.0", "1.0.0", ""]
        last_err = None
        for v in versions:
            try:
                cap_url = _build_url(
                    base_url,
                    {
                        "service": "WFS",
                        "request": "GetCapabilities",
                        **({"version": v} if v else {}),
                    },
                )
                xml_bytes = _fetch_xml(cap_url)
                items, parsed_version = _parse_wfs(xml_bytes)
                return {
                    "ok": True,
                    "service": {
                        "key": service_key,
                        "label": svc["label"],
                        "kind": kind,
                        "url": base_url,
                        "capabilities_url": cap_url,
                        "version": parsed_version or (v or None),
                    },
                    "counts": {
                        "items": len(items),
                    },
                    "items": sorted(items, key=lambda x: x.get("name", "")),
                    "fetched_at": int(time.time()),
                }
            except Exception as e:
                last_err = e
                continue
        raise RuntimeError(f"WFS Capabilities konnten nicht geladen werden: {str(last_err)[:220]}")

    raise ValueError("Unbekannter Service-Typ.")


def get_service_data(service_key: str, refresh: int) -> dict:
    if service_key not in OGC_SERVICES:
        raise ValueError("Bitte wähle einen gültigen Service aus.")
    refresh = 1 if refresh == 1 else 0
    cache_token = int(time.time()) if refresh else 0
    return _get_service_data_cached(service_key, cache_token)


def _nav_links_html() -> str:
    service_links = [(n, u) for (n, u) in SERVICES_NAV if isinstance(u, str) and u.startswith("https://")]
    head = service_links[:6]
    rest = service_links[6:]

    out = []
    for name, url in head:
        out.append(f'<a href="{url}">{name}</a>')
    return "\n".join(out)


def _sanitize_error(msg: str) -> str:
    msg = (msg or "").strip()
    if not msg:
        return "Unbekannter Fehler."
    if len(msg) > 280:
        msg = msg[:280] + "…"
    return msg


HTML_TEMPLATE = r"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="description" content="{{ meta.page_subtitle }}" />
  <meta name="theme-color" content="#0b0f19" />
  <title>{{ meta.page_title }}</title>

  <style>
:root{
  --bg: #0b0f19;
  --bg2:#0f172a;
  --card:#111a2e;
  --text:#e6eaf2;
  --muted:#a8b3cf;
  --border: rgba(255,255,255,.10);
  --shadow: 0 18px 60px rgba(0,0,0,.35);
  --primary:#6ea8fe;
  --primary2:#8bd4ff;
  --focus: rgba(110,168,254,.45);

  --radius: 18px;
  --container: 1100px;
  --gap: 18px;

  --font: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, "Apple Color Emoji","Segoe UI Emoji";
}

[data-theme="light"]{
  --bg:#f6f7fb;
  --bg2:#ffffff;
  --card:#ffffff;
  --text:#111827;
  --muted:#4b5563;
  --border: rgba(17,24,39,.12);
  --shadow: 0 18px 60px rgba(17,24,39,.10);
  --primary:#2563eb;
  --primary2:#0ea5e9;
  --focus: rgba(37,99,235,.25);
}

*{box-sizing:border-box}
html,body{height:100%}
body{
  margin:0;
  font-family:var(--font);
  background: radial-gradient(1200px 800px at 20% -10%, rgba(110,168,254,.25), transparent 55%),
              radial-gradient(1000px 700px at 110% 10%, rgba(139,212,255,.20), transparent 55%),
              linear-gradient(180deg, var(--bg), var(--bg2));
  color:var(--text);
}

.container{
  max-width:var(--container);
  margin:0 auto;
  padding:0 18px;
}

.skip-link{
  position:absolute; left:-999px; top:10px;
  background:var(--card); color:var(--text);
  padding:10px 12px; border-radius:10px;
  border:1px solid var(--border);
}
.skip-link:focus{left:10px; outline:2px solid var(--focus)}

.site-header{
  position:sticky; top:0; z-index:20;
  backdrop-filter: blur(10px);
  background: rgba(10, 14, 24, .55);
  border-bottom:1px solid var(--border);
}
[data-theme="light"] .site-header{ background: rgba(246,247,251,.75); }

.header-inner{
  display:flex; align-items:center; justify-content:space-between;
  padding:14px 0;
  gap:14px;
}
.brand{display:flex; align-items:center; gap:10px; text-decoration:none; color:var(--text); font-weight:700}
.brand-mark{
  width:14px; height:14px; border-radius:6px;
  background: linear-gradient(135deg, var(--primary), var(--primary2));
  box-shadow: 0 10px 25px rgba(110,168,254,.25);
}
.nav{display:flex; gap:16px; flex-wrap:wrap}
.nav a{color:var(--muted); text-decoration:none; font-weight:600}
.nav a:hover{color:var(--text)}
.header-actions{display:flex; gap:10px; align-items:center}
.header-actions .btn{ font-size: 18px; }

.btn{
  display:inline-flex; align-items:center; justify-content:center;
  gap:8px;
  padding:10px 14px;
  border-radius:12px;
  border:1px solid transparent;
  text-decoration:none;
  font-weight:700;
  color:var(--text);
  background: transparent;
  cursor:pointer;
}
.btn:focus{outline:2px solid var(--focus); outline-offset:2px}
.btn-primary{
  border-color: transparent;
  background: linear-gradient(135deg, var(--primary), var(--primary2));
  color: #0b0f19;
}
[data-theme="light"] .btn-primary{ color:#ffffff; }
.btn-secondary{ background: rgba(255,255,255,.06); }
[data-theme="light"] .btn-secondary{ background: rgba(17,24,39,.04); }
.btn-ghost{ background: transparent; }
.btn:hover{transform: translateY(-1px)}
.btn:active{transform:none}

.section-head{display:flex; align-items:flex-end; justify-content:space-between; gap:14px; flex-wrap:wrap; margin-bottom:16px}
h1{margin:0 0 12px; font-size:42px; line-height:1.1}
@media (max-width: 520px){ h1{font-size:34px} }
h2{margin:0; font-size:26px}
.muted{color:var(--muted); line-height:1.6; margin:0}

.card{
  border:1px solid var(--border);
  border-radius: var(--radius);
  background: rgba(255,255,255,.04);
  padding:16px;
  box-shadow: var(--shadow);
}

.sr-only{
  position:absolute; width:1px; height:1px; padding:0; margin:-1px;
  overflow:hidden; clip:rect(0,0,0,0); border:0;
}

/* minimal additions */
.content{padding:34px 0 56px}
.lead{margin:0 0 18px; color:var(--muted); font-size:16px; line-height:1.6}

.form-row{display:flex; flex-wrap:wrap; gap:12px; align-items:flex-end; margin:16px 0 12px}
.field{flex:1; min-width:260px}
.field label{display:block; font-weight:800; font-size:12px; letter-spacing:.07em; text-transform:uppercase; color:var(--muted); margin:0 0 8px}
.field select{
  width:100%;
  padding:12px 14px;
  border-radius:12px;
  border:1px solid var(--border);
  background: rgba(255,255,255,.04);
  color: var(--text);
  font-weight:650;
}
[data-theme="light"] .field select{ background: rgba(17,24,39,.03); }
.field select:focus{ outline:2px solid var(--focus); outline-offset:2px }
.field option{ background: var(--bg2, #ffffff); color: var(--text, #111827); }

.inline{display:flex; gap:10px; align-items:center; flex-wrap:wrap}
.inline .checkbox{
  display:flex; align-items:center; gap:10px;
  padding:10px 12px;
  border-radius:12px;
  border:1px solid var(--border);
  background: rgba(255,255,255,.04);
  color: var(--muted);
  font-weight:750;
}
[data-theme="light"] .inline .checkbox{ background: rgba(17,24,39,.03); }
.inline input[type="checkbox"]{ width:18px; height:18px; accent-color: var(--primary); }

.table-wrap{overflow:auto; border-radius: var(--radius); border:1px solid var(--border)}
.table-wrap--vh{
  max-height: 79vh;
  overflow: auto;          /* du hast schon overflow:auto, kann so bleiben */
  -webkit-overflow-scrolling: touch;
}
.table{width:100%; border-collapse: collapse; min-width: 720px}
.table thead th{
  position: sticky;
  top: 0;
  background: var(--card);
  z-index: 1;
}
.table th, .table td{ text-align:left; padding:12px 14px; border-bottom:1px solid var(--border); vertical-align:top }
.table th{ color: var(--muted); font-weight:900; font-size:12px; letter-spacing:.07em; text-transform:uppercase }
.table tr:last-child td{border-bottom:none}
.small{font-size:12px; color: var(--muted); font-weight:650}

.kv{display:flex; gap:14px; flex-wrap:wrap; margin-top:10px}
.kv .pill{
  border:1px solid var(--border);
  background: rgba(255,255,255,.04);
  border-radius:999px;
  padding:8px 10px;
  font-weight:850;
  color: var(--muted);
}
[data-theme="light"] .kv .pill{ background: rgba(17,24,39,.03); }

.search{margin:14px 0 0}
.search input{
  width:100%;
  padding:12px 14px;
  border-radius:12px;
  border:1px solid var(--border);
  background: rgba(255,255,255,.04);
  color: var(--text);
  font-weight:650;
}
[data-theme="light"] .search input{ background: rgba(17,24,39,.03); }
.search input:focus{ outline:2px solid var(--focus); outline-offset:2px }

.badge{
  display:inline-flex;
  padding:6px 10px;
  border-radius:999px;
  border:1px solid var(--border);
  font-weight:850;
  font-size:12px;
  color: var(--muted);
  background: rgba(255,255,255,.03);
}
[data-theme="light"] .badge{ background: rgba(17,24,39,.02); }
  </style>
</head>

<body>
  <a class="skip-link" href="#main">Zum Inhalt springen</a>

  <header class="site-header">
    <div class="container header-inner">
      <a class="brand" href="{{ landing_url }}" aria-label="Startseite">
        <span class="brand-mark" aria-hidden="true"></span>
        <span class="brand-text">data-tales</span>
      </a>

      <nav class="nav" aria-label="Hauptnavigation">
        {{ nav_links|safe }}
      </nav>

      <div class="header-actions">
        <a class="btn btn-primary" href="{{ landing_url }}#contact">Kontakt</a>
        <button class="btn btn-ghost" id="themeToggle" type="button" aria-label="Theme umschalten">
          <span aria-hidden="true" id="themeIcon">☾</span>
          <span class="sr-only">Theme umschalten</span>
        </button>
      </div>
    </div>
  </header>

  <main id="main" class="content">
    <section class="container">
      <div class="section-head">
        <div>
          <h1>{{ meta.page_h1 }}</h1>
          <p class="lead">{{ meta.page_subtitle }}</p>
        </div>
      </div>

      <div class="card">
        <form method="GET" action="/" novalidate>
          <div class="form-row">
            <div class="field">
              <label for="service">Service</label>
              <select id="service" name="service" required>
                <option value="" {% if not selected %}selected{% endif %}>Bitte wählen…</option>
                {% for key, svcopt in ogc_services.items() %}
                  <option value="{{ key }}" {% if selected == key %}selected{% endif %}>
                    {{ svcopt.label }}
                  </option>
                {% endfor %}
              </select>
            </div>

            <div class="inline">
              <label class="checkbox" for="refresh">
                <input type="checkbox" id="refresh" name="refresh" value="1" {% if refresh == 1 %}checked{% endif %} />
                Cache umgehen (refresh=1)
              </label>
              <button class="btn btn-primary" type="submit">Abrufen</button>
            </div>
          </div>

          <div class="small">
            Tipp: /api?service=&lt;key&gt;&amp;refresh=0|1 liefert das Ergebnis als JSON.
          </div>
        </form>
      </div>

      {% if error %}
        <div class="card" style="margin-top: var(--gap);">
          <h2>Fehler</h2>
          <p class="muted">{{ error }}</p>
        </div>
      {% endif %}

      {% if has_data %}
        <div class="card" style="margin-top: var(--gap);">
          <div class="section-head" style="margin-bottom: 10px;">
            <div>
              <h2>Ergebnis</h2>
              <p class="muted">{{ svc.label }} <span class="badge">{{ svc.kind|upper }}</span></p>
            </div>
            <div class="inline">
              <a class="btn btn-secondary" href="{{ svc.capabilities_url }}" target="_blank" rel="noreferrer">Capabilities öffnen</a>
              <a class="btn btn-secondary" href="/api?service={{ svc.key }}&refresh={{ refresh }}">JSON (/api)</a>
            </div>
          </div>

          <div class="kv">
            <span class="pill">Items: <strong>{{ counts_items }}</strong></span>
            {% if counts_styles is not none %}
              <span class="pill">Styles: <strong>{{ counts_styles }}</strong></span>
            {% endif %}
            {% if svc.version %}
              <span class="pill">Version: <strong>{{ svc.version }}</strong></span>
            {% endif %}
            <span class="pill">Fetched: <strong>{{ fetched_at }}</strong></span>
          </div>

          <div class="search">
            <input id="tableFilter" type="text" placeholder="Tabelle filtern (Name, Titel, Styles) …" autocomplete="off" />
          </div>

          <div class="table-wrap table-wrap--vh" style="margin-top: 14px;">
            <table class="table" id="resultTable">
              <thead>
                <tr>
                  <th>Typ</th>
                  <th>Name</th>
                  <th>Titel</th>
                  <th>Details</th>
                </tr>
              </thead>
              <tbody>
                {% for it in rows %}
                  <tr>
                    <td>{% if it.type == "wms_layer" %}WMS{% else %}WFS{% endif %}</td>
                    <td><strong>{{ it.name }}</strong></td>
                    <td>{{ it.title }}</td>
                    <td class="small">
                      {% if it.type == "wms_layer" %}
                        Styles: {{ (it.styles|length) if it.styles is defined else 0 }}
                        {% if it.styles and (it.styles|length) > 0 %}
                          <br/>
                          {% for s in it.styles[:3] %}
                            <span class="badge">{{ s.name }}</span>
                          {% endfor %}
                          {% if (it.styles|length) > 3 %}
                            <span class="badge">+{{ (it.styles|length) - 3 }}</span>
                          {% endif %}
                        {% endif %}
                      {% else %}
                        {% if it.default_crs %}CRS: {{ it.default_crs }}{% else %}—{% endif %}
                      {% endif %}
                    </td>
                  </tr>
                {% endfor %}
              </tbody>
            </table>
          </div>

          <p class="small" style="margin-top: 12px;">
            Hinweis: Die Tabelle wird clientseitig gefiltert; die Rohdaten kommen aus dem jeweiligen Capabilities-Dokument.
          </p>
        </div>
      {% endif %}
    </section>
  </main>

  <script>
  // Theme toggle (Landing-kompatibel)
  (function() {
    const root = document.documentElement;
    const btn = document.getElementById('themeToggle');
    const icon = document.getElementById('themeIcon');

    function apply(theme) {
      if (theme === 'light') {
        root.setAttribute('data-theme', 'light');
        if (icon) icon.textContent = '☀';
      } else {
        root.removeAttribute('data-theme');
        if (icon) icon.textContent = '☾';
      }
    }

    const saved = localStorage.getItem('theme');
    apply(saved === 'light' ? 'light' : 'dark');

    btn && btn.addEventListener('click', function() {
      const isLight = root.getAttribute('data-theme') === 'light';
      const next = isLight ? 'dark' : 'light';
      localStorage.setItem('theme', next);
      apply(next);
    });
  })();

  // Table filter
  (function() {
    const input = document.getElementById('tableFilter');
    const table = document.getElementById('resultTable');
    if (!input || !table) return;

    input.addEventListener('input', function() {
      const q = (input.value || '').toLowerCase().trim();
      const rows = table.querySelectorAll('tbody tr');
      rows.forEach(row => {
        const text = row.textContent.toLowerCase();
        row.style.display = (!q || text.includes(q)) ? '' : 'none';
      });
    });
  })();
  </script>
</body>
</html>
"""


app = Flask(__name__)


@app.get("/healthz")
def healthz():
    return jsonify({"ok": True})


@app.get("/api")
def api():
    service_key = (request.args.get("service") or "").strip()
    refresh = _safe_int(request.args.get("refresh", "0"), 0)
    refresh = 1 if refresh == 1 else 0

    if not service_key:
        return jsonify({"ok": False, "error": "Query-Parameter 'service' fehlt."}), 400
    if service_key not in OGC_SERVICES:
        return jsonify({"ok": False, "error": "Unbekannter Service-Key."}), 400

    try:
        data = get_service_data(service_key, refresh)
        return jsonify(data), 200
    except ValueError as e:
        return jsonify({"ok": False, "error": _sanitize_error(str(e))}), 400
    except requests.exceptions.Timeout:
        return jsonify({"ok": False, "error": "Timeout beim Abruf der Capabilities."}), 504
    except requests.exceptions.RequestException:
        return jsonify({"ok": False, "error": "HTTP-Fehler beim Abruf der Capabilities."}), 502
    except Exception as e:
        return jsonify({"ok": False, "error": _sanitize_error(str(e))}), 500


@app.get("/")
def index():
    service_key = (request.args.get("service") or "").strip()
    refresh = _safe_int(request.args.get("refresh", "0"), 0)
    refresh = 1 if refresh == 1 else 0

    data = None
    error = None

    if service_key:
        if service_key not in OGC_SERVICES:
            error = "Bitte wähle einen gültigen Service aus."
        else:
            try:
                data = get_service_data(service_key, refresh)
            except ValueError as e:
                error = _sanitize_error(str(e))
            except requests.exceptions.Timeout:
                error = "Timeout beim Abruf der Capabilities."
            except requests.exceptions.RequestException:
                error = "HTTP-Fehler beim Abruf der Capabilities."
            except Exception as e:
                error = _sanitize_error(str(e))

    ogc_services_for_select = {
        k: {"label": v["label"], "kind": v["kind"], "url": v["url"]}
        for k, v in OGC_SERVICES.items()
    }

    # Avoid Jinja dict-key collision with .items() by passing explicit vars
    has_data = bool(data and isinstance(data, dict))
    svc = (data or {}).get("service", {}) if has_data else {}
    counts = (data or {}).get("counts", {}) if has_data else {}
    rows = (data or {}).get("items", []) if has_data else []
    counts_items = counts.get("items", 0) if isinstance(counts, dict) else 0
    counts_styles = counts.get("styles", None) if isinstance(counts, dict) else None
    fetched_at = (data or {}).get("fetched_at", None) if has_data else None

    return render_template_string(
        HTML_TEMPLATE,
        meta=APP_META,
        nav_links=_nav_links_html(),
        ogc_services=ogc_services_for_select,
        selected=service_key or None,
        refresh=refresh,
        error=error,
        has_data=has_data,
        svc=svc,
        counts_items=counts_items,
        counts_styles=counts_styles,
        fetched_at=fetched_at,
        rows=rows,
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port, debug=True)
