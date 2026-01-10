#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API:
- GET /healthz                      -> Überprüft den Zustand des Dienstes
- GET /api?service=<service_key>&refresh=<0|1> -> Ruft die Capabilities eines OGC-Dienstes ab
"""

import os
import time
import json
from datetime import datetime
from functools import lru_cache
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

import requests
from flask import Flask, jsonify, request, render_template_string
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ------------------------------------------------------------
# Meta / Nav
# ------------------------------------------------------------

APP_META = {
    "service_name_slug": "data-sources",
    "page_title": "WMS / WFS Information Tool",
    "page_h1": "WMS / WFS Information Tool",
    "page_subtitle": "Layer- und FeatureType-Übersicht für ausgewählte WMS/WFS-Dienste.",
}

LANDING_URL = os.environ.get("LANDING_URL", "https://data-tales.dev/")

SERVICES_NAV = [
    ("PLZ → Koordinaten", "https://plz.data-tales.dev/"),
    ("OSM Baumbestand", "https://tree-locator.data-tales.dev/"),
]

# ------------------------------------------------------------
# OGC Services
# ------------------------------------------------------------

OGC_SERVICES = {
    "dwd_wfs": {
        "label": "DWD GeoServer (WFS)",
        "kind": "wfs",
        "url": "https://maps.dwd.de/geoserver/wfs?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetCapabilities",
    },
    "dwd_wms": {
        "label": "DWD GeoServer (WMS)",
        "kind": "wms",
        "url": "https://maps.dwd.de/geoserver/wms?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetCapabilities",
    },
    "cdc_wfs": {
        "label": "DWD CDC GeoServer (WFS)",
        "kind": "wfs",
        "url": "https://cdc.dwd.de/geoserver/ows?service=WFS&version=2.0.0&request=GetCapabilities",
    },
    "cdc_wms": {
        "label": "DWD CDC GeoServer (WMS)",
        "kind": "wms",
        "url": "https://cdc.dwd.de/geoserver/ows?service=WMS&version=1.3.0&request=GetCapabilities",
    },
    "dwd_warnungen_wms": {
        "label": "DWD Warnungen (WMS)",
        "kind": "wms",
        "url": "https://maps.dwd.de/geoproxy_warnungen/service?service=wms&version=1.3.0&request=GetCapabilities",
    },
    "dwd_geoproxy_wms": {
        "label": "DWD Geoproxy (WMS)",
        "kind": "wms",
        "url": "https://maps.dwd.de/geoproxy/service?service=wms&version=1.3.0&request=GetCapabilities",
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

    "wmts_dop": {
        "label": "GeoBasis-DE / BKG WMTS DOP",
        "kind": "wms",
        "url": "https://sg.geodatenzentrum.de/wmts_dop?request=GetCapabilities&service=WMTS"
    },
    "wms_dop": {
        "label": "GeoBasis-DE / BKG WMS DOP",
        "kind": "wms",
        "url": "https://sg.geodatenzentrum.de/wms_dop?request=GetCapabilities&service=WMS"
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
        "url": "https://services.bgr.de/wms/boden/buek1000de/?SERVICE=WMS",
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

    # ---------------------------------------------------------------------
    # Deutschland (Länder) – DOP20 (WMS)
    # ---------------------------------------------------------------------
    "dop20_bw_wms": {
        "label": "DOP20 Baden-Württemberg (WMS)",
        "kind": "wms",
        "url": "https://owsproxy.lgl-bw.de/owsproxy/ows/WMS_LGL-BW_ATKIS_DOP_20_C?REQUEST=GetCapabilities&SERVICE=WMS",
    },
    "dop20_by_wms": {
        "label": "DOP20 Bayern (WMS)",
        "kind": "wms",
        "url": "https://geoservices.bayern.de/od/wms/dop/v1/dop20?REQUEST=GetCapabilities&SERVICE=WMS",
    },
    "dop20_be_wms": {
        "label": "DOP20 Berlin (WMS)",
        "kind": "wms",
        "url": "https://gdi.berlin.de/services/wms/dop_2025_fruehjahr?REQUEST=GetCapabilities&SERVICE=WMS",
    },
    "dop20_bb_wms": {
        "label": "DOP20 Brandenburg (WMS)",
        "kind": "wms",
        "url": "https://isk.geobasis-bb.de/mapproxy/dop20c/service/wms?REQUEST=GetCapabilities&SERVICE=WMS",
    },
    "dop20_hb_wms": {
        "label": "DOP20 Bremen (WMS)",
        "kind": "wms",
        "url": "https://geodienste.bremen.de/wms_dop_lb?REQUEST=GetCapabilities&SERVICE=WMS",
    },
    "dop20_hh_wms": {
        "label": "DOP20 Hamburg (WMS)",
        "kind": "wms",
        "url": "https://geodienste.hamburg.de/HH_WMS_DOP?SERVICE=WMS&REQUEST=GetCapabilities",
    },
    "dop20_he_wms": {
        "label": "DOP20 Hessen (WMS)",
        "kind": "wms",
        "url": "https://www.geoportal.hessen.de/mapbender/php/wms.php?inspire=1&layer_id=54936&withChilds=1&REQUEST=GetCapabilities&SERVICE=WMS",
    },
    "dop20_mv_wms": {
        "label": "DOP20 Mecklenburg-Vorpommern (WMS)",
        "kind": "wms",
        "url": "https://www.geodaten-mv.de/dienste/adv_dop?SERVICE=WMS&REQUEST=GetCapabilities",
    },
    "dop20_ni_wms": {
        "label": "DOP20 Niedersachsen (WMS)",
        "kind": "wms",
        "url": "https://opendata.lgln.niedersachsen.de/doorman/noauth/dop_wms?REQUEST=GetCapabilities&SERVICE=WMS",
    },
    "dop20_nw_wms": {
        "label": "DOP20 Nordrhein-Westfalen (WMS)",
        "kind": "wms",
        "url": "https://www.wms.nrw.de/geobasis/wms_nw_dop?REQUEST=GetCapabilities&SERVICE=WMS",
    },
    "dop20_rp_wms": {
        "label": "DOP20 Rheinland-Pfalz (WMS)",
        "kind": "wms",
        "url": "https://www.geoportal.rlp.de/mapbender/php/wms.php?inspire=1&layer_id=61676&withChilds=1&REQUEST=GetCapabilities&SERVICE=WMS",
    },
    "dop20_sl_wms": {
        "label": "DOP20 Saarland (WMS)",
        "kind": "wms",
        "url": "https://geoportal.saarland.de/mapbender/php/wms.php?inspire=1&layer_id=46747&withChilds=1&REQUEST=GetCapabilities&SERVICE=WMS",
    },
    "dop20_sn_wms": {
        "label": "DOP20 Sachsen (WMS)",
        "kind": "wms",
        "url": "https://geodienste.sachsen.de/wms_geosn_dop-rgb/guest?REQUEST=GetCapabilities&SERVICE=WMS",
    },
    "dop20_st_wms": {
        "label": "DOP20 Sachsen-Anhalt (WMS)",
        "kind": "wms",
        "url": "https://www.geodatenportal.sachsen-anhalt.de/wss/service/ST_LVermGeo_GDI_DOP20/guest?SERVICE=WMS&REQUEST=GetCapabilities",
    },
    "dop20_sh_wms": {
        "label": "DOP20 Schleswig-Holstein (WMS)",
        "kind": "wms",
        "url": "https://service.gdi-sh.de/WMS_SH_MD_DOP?SERVICE=WMS&REQUEST=GetCapabilities&VERSION=1.3.0",
    },
    "dop20_th_wms": {
        "label": "DOP20 Thüringen (WMS)",
        "kind": "wms",
        "url": "https://www.geoproxy.geoportal-th.de/geoproxy/services/DOP?SERVICE=WMS&REQUEST=GetCapabilities",
    },

    # ---------------------------------------------------------------------
    # Deutschland (Länder) – DOP20 (WCS)
    # ---------------------------------------------------------------------
    "dop20_bw_wcs": {
        "label": "DOP20 Baden-Württemberg (WCS)",
        "kind": "wcs",
        "url": "https://owsproxy.lgl-bw.de/owsproxy/wcs/WCS_INSP_BW_Orthofoto_DOP20?SERVICE=WCS&REQUEST=GetCapabilities",
    },
    "dop20_bb_wcs": {
        "label": "DOP20 Brandenburg (WCS)",
        "kind": "wcs",
        "url": "https://inspire.brandenburg.de/services/oi_dop20_wcs?REQUEST=GetCapabilities&SERVICE=WCS",
    },
    "dop20_he_wcs": {
        "label": "DOP20 Hessen (WCS)",
        "kind": "wcs",
        "url": "https://inspire-hessen.de/raster/dop20/ows?SERVICE=WCS&VERSION=2.0.1&REQUEST=GetCapabilities",
    },
    "dop20_mv_wcs": {
        "label": "DOP20 Mecklenburg-Vorpommern (WCS)",
        "kind": "wcs",
        "url": "https://www.geodaten-mv.de/dienste/inspire_oi_dop_wcs?SERVICE=WCS&REQUEST=GetCapabilities",
    },
    "dop20_nw_wcs": {
        "label": "DOP20 Nordrhein-Westfalen (WCS)",
        "kind": "wcs",
        "url": "https://www.wcs.nrw.de/geobasis/wcs_nw_dop?SERVICE=WCS&REQUEST=GetCapabilities",
    },
    "dop20_sl_wcs": {
        "label": "DOP20 Saarland (WCS)",
        "kind": "wcs",
        "url": "https://geoportal.saarland.de/gdi-sl/inspireraster/inspirewcsoi?SERVICE=WCS&REQUEST=GetCapabilities&",
    },
}

# ------------------------------------------------------------
# Runtime / Config
# ------------------------------------------------------------

MAX_URL_LEN = int(os.environ.get("MAX_URL_LEN", "400"))
CACHE_TTL_SECONDS = int(os.environ.get("CACHE_TTL_SECONDS", "900"))  # 15 min
UI_SOFT_LIMIT = int(os.environ.get("UI_SOFT_LIMIT", "2000"))         # max rows rendered in HTML
MAX_XML_BYTES = int(os.environ.get("MAX_XML_BYTES", "8000000"))      # safety limit (8 MB)

CONNECT_TIMEOUT = float(os.environ.get("CONNECT_TIMEOUT", "3.05"))
READ_TIMEOUT = float(os.environ.get("READ_TIMEOUT", "18"))
DEFAULT_TIMEOUT = (CONNECT_TIMEOUT, READ_TIMEOUT)

HTTP_RETRIES = int(os.environ.get("HTTP_RETRIES", "2"))
HTTP_BACKOFF = float(os.environ.get("HTTP_BACKOFF", "0.3"))


def _ua() -> str:
    return os.environ.get(
        "USER_AGENT",
        "data-tales.dev (data-sources) - OGC Service Explorer",
    )


# requests.Session + retries
SESSION = requests.Session()
_retry = Retry(
    total=HTTP_RETRIES,
    read=HTTP_RETRIES,
    connect=HTTP_RETRIES,
    backoff_factor=HTTP_BACKOFF,
    status_forcelist=(429, 500, 502, 503, 504),
    allowed_methods=frozenset(["GET", "HEAD"]),
    raise_on_status=False,
)
_adapter = HTTPAdapter(max_retries=_retry, pool_connections=20, pool_maxsize=50)
SESSION.mount("https://", _adapter)


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def _build_url(base_url: str, updates: dict) -> str:
    if not base_url or len(base_url) > MAX_URL_LEN:
        raise ValueError("Ungültige Service-URL.")

    parts = urlsplit(base_url)
    if parts.scheme.lower() != "https":
        raise ValueError("Nur https:// URLs sind erlaubt.")

    # Case-insensitive normalize for deterministic query output
    q = {k.lower(): v for k, v in parse_qsl(parts.query, keep_blank_values=True)}
    for k, v in updates.items():
        q[str(k).lower()] = str(v)

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


def _split_qname(name: str) -> tuple[str, str]:
    if not name:
        return "", ""
    if ":" in name:
        p, rest = name.split(":", 1)
        return p, rest
    return "", name


def _bbox_to_str(b: dict | None) -> str:
    if not b:
        return ""
    keys = ("minx", "miny", "maxx", "maxy")
    if all(k in b for k in keys):
        return f"{b.get('minx')},{b.get('miny')},{b.get('maxx')},{b.get('maxy')}"
    return ""


def _sanitize_error(msg: str) -> str:
    msg = (msg or "").strip()
    if not msg:
        return "Unbekannter Fehler."
    if len(msg) > 280:
        msg = msg[:280] + "…"
    return msg


def _fetch_xml(url: str) -> bytes:
    r = SESSION.get(
        url,
        headers={"User-Agent": _ua(), "Accept": "application/xml,text/xml,*/*;q=0.9"},
        timeout=DEFAULT_TIMEOUT,
        stream=True,
    )
    # retries may return a non-2xx without raising; enforce here
    r.raise_for_status()

    chunks = []
    size = 0
    for chunk in r.iter_content(chunk_size=65536):
        if not chunk:
            continue
        chunks.append(chunk)
        size += len(chunk)
        if size > MAX_XML_BYTES:
            raise ValueError("Capabilities-Dokument ist zu groß (Limit überschritten).")
    return b"".join(chunks)


# ------------------------------------------------------------
# Parsing
# ------------------------------------------------------------

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

    def parse_wgs84_bbox(layer_elem) -> dict | None:
        # WMS 1.3.0: <WGS84BoundingBox><LowerCorner>..</LowerCorner><UpperCorner>..</UpperCorner>
        wgs = None
        for bb in _iter_children(layer_elem, "WGS84BoundingBox"):
            wgs = bb
            break
        if wgs is not None:
            lower = _child_text(wgs, "LowerCorner")
            upper = _child_text(wgs, "UpperCorner")
            if lower and upper:
                try:
                    lx, ly = [float(x) for x in lower.split()]
                    ux, uy = [float(x) for x in upper.split()]
                    return {"minx": lx, "miny": ly, "maxx": ux, "maxy": uy, "crs": "EPSG:4326"}
                except Exception:
                    return None

        # Older: <LatLonBoundingBox minx=".." miny=".." maxx=".." maxy=".."/>
        for bb in layer_elem.iter():
            if _local(bb.tag) == "LatLonBoundingBox":
                try:
                    return {
                        "minx": float(bb.attrib.get("minx", "")),
                        "miny": float(bb.attrib.get("miny", "")),
                        "maxx": float(bb.attrib.get("maxx", "")),
                        "maxy": float(bb.attrib.get("maxy", "")),
                        "crs": "EPSG:4326",
                    }
                except Exception:
                    return None
        return None

    def collect_crs(layer_elem) -> list[str]:
        vals = []
        for c in list(layer_elem):
            ln = _local(c.tag)
            if ln in ("CRS", "SRS"):
                t = (c.text or "").strip()
                if t:
                    vals.append(t)
        # de-dup, stable
        seen = set()
        out = []
        for v in vals:
            if v not in seen:
                out.append(v)
                seen.add(v)
        return out

    def walk(layer_elem, inherited_title: str | None = None, inherited_crs: list[str] | None = None):
        name = _child_text(layer_elem, "Name")
        title = _child_text(layer_elem, "Title") or inherited_title
        abstract = _child_text(layer_elem, "Abstract") or ""
        queryable = layer_elem.attrib.get("queryable") or ""

        crs_here = collect_crs(layer_elem)
        crs = crs_here if crs_here else (inherited_crs or [])
        bbox = parse_wgs84_bbox(layer_elem)

        styles = []
        for s in _iter_children(layer_elem, "Style"):
            s_name = _child_text(s, "Name") or ""
            s_title = _child_text(s, "Title") or ""
            if s_name or s_title:
                styles.append({"name": s_name, "title": s_title})

        if name:
            prefix, localname = _split_qname(name)
            items.append(
                {
                    "type": "wms_layer",
                    "name": name,
                    "prefix": prefix,
                    "local_name": localname,
                    "title": title or "",
                    "abstract": abstract,
                    "queryable": queryable,
                    "crs": crs,
                    "bbox_wgs84": bbox,
                    "styles": styles,
                }
            )

        for child_layer in _iter_children(layer_elem, "Layer"):
            walk(child_layer, title, crs)

    if top_layer is not None:
        walk(top_layer, None, [])

    version = root.attrib.get("version") or root.attrib.get("Version")
    return items, version


def _parse_wfs(xml_bytes: bytes) -> tuple[list[dict], str | None, list[str]]:
    import xml.etree.ElementTree as ET

    root = ET.fromstring(xml_bytes)
    version = root.attrib.get("version") or root.attrib.get("Version")

    # Output formats from OperationsMetadata/GetFeature
    output_formats: list[str] = []
    ops = _find_first(root, "OperationsMetadata")
    if ops is not None:
        for op in _find_all(ops, "Operation"):
            if (op.attrib.get("name") or "").lower() == "getfeature":
                for p in _find_all(op, "Parameter"):
                    if (p.attrib.get("name") or "").lower() == "outputformat":
                        for v in _find_all(p, "Value"):
                            t = (v.text or "").strip()
                            if t:
                                output_formats.append(t)
    # de-dup stable
    seen = set()
    of = []
    for x in output_formats:
        if x not in seen:
            of.append(x)
            seen.add(x)
    output_formats = of

    def parse_wgs84_bbox(ft_elem) -> dict | None:
        # WFS 2.0: <WGS84BoundingBox><LowerCorner>..</LowerCorner>...
        wgs = None
        for bb in _iter_children(ft_elem, "WGS84BoundingBox"):
            wgs = bb
            break
        if wgs is not None:
            lower = _child_text(wgs, "LowerCorner")
            upper = _child_text(wgs, "UpperCorner")
            if lower and upper:
                try:
                    lx, ly = [float(x) for x in lower.split()]
                    ux, uy = [float(x) for x in upper.split()]
                    return {"minx": lx, "miny": ly, "maxx": ux, "maxy": uy, "crs": "EPSG:4326"}
                except Exception:
                    return None
        return None

    items: list[dict] = []
    ft_list = _find_first(root, "FeatureTypeList")
    if ft_list is None:
        feature_types = list(_find_all(root, "FeatureType"))
    else:
        feature_types = list(_iter_children(ft_list, "FeatureType"))

    for ft in feature_types:
        name = _child_text(ft, "Name") or ""
        title = _child_text(ft, "Title") or ""
        abstract = _child_text(ft, "Abstract") or ""
        default_crs = _child_text(ft, "DefaultCRS") or _child_text(ft, "DefaultSRS") or ""
        bbox = parse_wgs84_bbox(ft)

        if name:
            prefix, localname = _split_qname(name)
            items.append(
                {
                    "type": "wfs_featuretype",
                    "name": name,
                    "prefix": prefix,
                    "local_name": localname,
                    "title": title,
                    "abstract": abstract,
                    "default_crs": default_crs,
                    "bbox_wgs84": bbox,
                }
            )

    return items, version, output_formats


def _parse_wcs(xml_bytes: bytes) -> tuple[list[dict], str | None, list[str]]:
    import xml.etree.ElementTree as ET

    root = ET.fromstring(xml_bytes)
    version = root.attrib.get("version") or root.attrib.get("Version")

    output_formats: list[str] = []
    
    items: list[dict] = []
    for cov in _find_all(root, "CoverageSummary"):
        name = _child_text(cov, "CoverageId") or ""
        title = _child_text(cov, "Title") or ""
        
        if name:
            items.append(
                {
                    "type": "wcs_coverage",
                    "name": name,
                    "prefix": "",
                    "local_name": name,
                    "title": title,
                    "abstract": "",
                    "default_crs": "",
                    "bbox_wgs84": None,
                }
            )

    return items, version, output_formats


# ------------------------------------------------------------
# Service groups (Optgroups + Search)
# ------------------------------------------------------------

def _group_for_service_key(key: str, svc: dict) -> str:
    k = key.lower()
    label = (svc.get("label") or "").lower()

    if k.startswith("dwd_") or "dwd" in label:
        return "DWD"
    if k.startswith("cdc_") or "cdc" in label:
        return "DWD (CDC)"
    if k.startswith("pegel_") or "pegel" in label:
        return "Deutschland (Pegelonline)"
    if k.startswith(("bkg_", "bfn_", "bgr_", "uba_", "thuenen_")):
        return "Deutschland (Bund)"
    if k.startswith("dop20_"):
        return "Deutschland (Länder) – DOP20"
    if k.startswith(("dlr_", "eumetsat_")):
        return "Forschung / EO"
    if k.startswith(("eea_", "copernicus_", "emodnet_")):
        return "Europa"
    if "haleconnect" in label or "haleconnect" in (svc.get("url") or "").lower():
        return "Niederlande (Haleconnect)"
    return "Weitere"

def _services_grouped() -> list[tuple[str, list[tuple[str, dict]]]]:
    groups: dict[str, list[tuple[str, dict]]] = {}
    for key, svc in OGC_SERVICES.items():
        g = _group_for_service_key(key, svc)
        groups.setdefault(g, []).append((key, svc))

    # stable sort within groups
    for g in groups:
        groups[g].sort(key=lambda kv: (kv[1].get("label", ""), kv[0]))

    order = ["DWD", "DWD (CDC)", "Deutschland (Pegelonline)", "Deutschland (Bund)", "Deutschland (Länder) – DOP20", "Forschung / EO", "Europa", "Niederlande (Haleconnect)", "Weitere"]
    out: list[tuple[str, list[tuple[str, dict]]]] = []
    for g in order:
        if g in groups:
            out.append((g, groups[g]))
    # any remaining
    for g in sorted(set(groups.keys()) - set(order)):
        out.append((g, groups[g]))
    return out


# ------------------------------------------------------------
# Fetch + Cache
# ------------------------------------------------------------

def _get_service_data_impl(service_key: str) -> dict:
    svc = OGC_SERVICES.get(service_key)
    if not svc:
        raise ValueError("Unbekannter Service.")

    kind = svc["kind"]
    base_url = svc["url"]

    started = time.perf_counter()

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

                elapsed_ms = int((time.perf_counter() - started) * 1000)
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
                    "items": sorted(items, key=lambda x: (x.get("prefix", ""), x.get("local_name", ""), x.get("name", ""))),
                    "fetched_at": int(time.time()),
                    "fetch_ms": elapsed_ms,
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
                items, parsed_version, output_formats = _parse_wfs(xml_bytes)

                elapsed_ms = int((time.perf_counter() - started) * 1000)
                return {
                    "ok": True,
                    "service": {
                        "key": service_key,
                        "label": svc["label"],
                        "kind": kind,
                        "url": base_url,
                        "capabilities_url": cap_url,
                        "version": parsed_version or (v or None),
                        "output_formats": output_formats,
                    },
                    "counts": {
                        "items": len(items),
                    },
                    "items": sorted(items, key=lambda x: (x.get("prefix", ""), x.get("local_name", ""), x.get("name", ""))),
                    "fetched_at": int(time.time()),
                    "fetch_ms": elapsed_ms,
                }
            except Exception as e:
                last_err = e
                continue
        raise RuntimeError(f"WFS Capabilities konnten nicht geladen werden: {str(last_err)[:220]}")

    if kind == "wcs":
        versions = ["2.0.1", "2.0.0", "1.0.0", ""]
        last_err = None
        for v in versions:
            try:
                cap_url = _build_url(
                    base_url,
                    {
                        "service": "WCS",
                        "request": "GetCapabilities",
                        **({"version": v} if v else {}),
                    },
                )
                xml_bytes = _fetch_xml(cap_url)
                items, parsed_version, output_formats = _parse_wcs(xml_bytes)

                elapsed_ms = int((time.perf_counter() - started) * 1000)
                return {
                    "ok": True,
                    "service": {
                        "key": service_key,
                        "label": svc["label"],
                        "kind": kind,
                        "url": base_url,
                        "capabilities_url": cap_url,
                        "version": parsed_version or (v or None),
                        "output_formats": output_formats,
                    },
                    "counts": {
                        "items": len(items),
                    },
                    "items": sorted(items, key=lambda x: (x.get("prefix", ""), x.get("local_name", ""), x.get("name", ""))),
                    "fetched_at": int(time.time()),
                    "fetch_ms": elapsed_ms,
                }
            except Exception as e:
                last_err = e
                continue
        raise RuntimeError(f"WCS Capabilities konnten nicht geladen werden: {str(last_err)[:220]}")

    raise ValueError("Unbekannter Service-Typ.")


@lru_cache(maxsize=64)
def _get_service_data_cached(service_key: str, bucket: int) -> dict:
    # bucket is only there to make TTL cache keys change over time
    _ = bucket
    return _get_service_data_impl(service_key)


def get_service_data(service_key: str, refresh: int) -> dict:
    if service_key not in OGC_SERVICES:
        raise ValueError("Bitte wähle einen gültigen Service aus.")
    refresh = 1 if refresh == 1 else 0

    if refresh:
        # bypass cache completely
        return _get_service_data_impl(service_key)

    bucket = int(time.time()) // max(CACHE_TTL_SECONDS, 1)
    return _get_service_data_cached(service_key, bucket)


# ------------------------------------------------------------
# UI helpers
# ------------------------------------------------------------

def _nav_links_html() -> str:
    service_links = [(n, u) for (n, u) in SERVICES_NAV if isinstance(u, str) and u.startswith("https://")]
    head = service_links[:6]
    out = []
    for name, url in head:
        out.append(f'<a href="{url}">{name}</a>')
    return "\n".join(out)


# ------------------------------------------------------------
# HTML
# ------------------------------------------------------------

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
  .container{max-width:var(--container); margin:0 auto; padding:0 18px;}
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
    padding:14px 0; gap:14px;
  }
  .brand{display:flex; align-items:center; gap:10px; text-decoration:none; color:var(--text); font-weight:700}
  .brand-mark{
    width:14px; height:14px; border-radius:6px;
    background: linear-gradient(135deg, var(--primary), var(--primary2));
    box-shadow: 0 10px 25px rgba(110,168,254,.25);
  }

  /* Dropdown */
  .nav-dropdown{ position: relative; display: inline-flex; align-items: center; }
  .nav-dropbtn{
    background: none; border: none; padding: 0; margin: 0; font-family: inherit;
    color: var(--muted); text-decoration: none; font-weight: 600;
    display: inline-flex; align-items: center; gap: 8px;
    cursor: pointer; height: 100%;
  }
  .nav-dropbtn:hover{ color: var(--text); transform: none; }
  .nav-caret{ font-size: .9em; opacity: 1; }

  .nav-menu{
    position: absolute;
    top: calc(100% + 10px);
    left: 0;
    min-width: 240px;
    padding: 10px;
    z-index: 6000;
    backdrop-filter: blur(10px);
  }

  .nav-menu a{
    display: block;
    padding: 10px 10px;
    border-radius: 12px;
    text-decoration: none;
    color: var(--text);
    font-weight: 650;
  }
  .nav-menu a:hover{ background: rgba(110,168,254,.12); }

  /* --- Buttons / misc --- */
  .header-actions{display:flex; gap:10px; align-items:center}
  .header-note{
    display:flex; align-items:center; gap:8px;
    padding:8px 10px;
    border-radius:12px;
    border:1px solid var(--border);
    background: rgba(255,255,255,.04);
    color: var(--muted);
    font-weight: 750;
    font-size: 12px;
    line-height: 1;
    white-space: nowrap;
  }
  [data-theme="light"] .header-note{ background: rgba(17,24,39,.03); }
  .header-note__label{
    letter-spacing: .06em; text-transform: uppercase;
    font-weight: 900; color: var(--muted);
  }
  .header-note__mail{
    color: var(--text);
    text-decoration: none;
    font-weight: 850;
  }
  .header-note__mail:hover{ text-decoration: underline; }
  @media (max-width: 720px){ .header-note__label{ display:none; } }

 
  .header-inner{
    padding-left: 6px;   /* addiert sich zum container padding */
    padding-right: 6px;
  }

  .btn{
    display:inline-flex; align-items:center; justify-content:center;
    gap:8px; padding:5px 7px;
    border-radius:12px; border:1px solid transparent;
    text-decoration:none; font-weight:700;
    color:var(--text); background: transparent;
    cursor:pointer; user-select:none;
  }
  .btn:focus{outline:2px solid var(--focus); outline-offset:2px}
  .btn-primary{
    border-color: transparent;
    background: linear-gradient(135deg, var(--primary), var(--primary2));
    color: #0b0f19;
  }
  [data-theme="light"] .btn-primary{ color:#ffffff; }
  .btn-secondary{ background: rgba(255,255,255,.06); border-color: rgba(255,255,255,.02); }
  [data-theme="light"] .btn-secondary{ background: rgba(17,24,39,.04); border-color: rgba(17,24,39,.04); }
  .btn-ghost{ background: transparent; border-color: rgba(255,255,255,.10); }
  [data-theme="light"] .btn-ghost{ border-color: rgba(17,24,39,.12); }
  .btn:hover{transform: translateY(-1px)}
  .btn:active{transform:none}
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
.field select, .field input[type="text"]{
  width:100%;
  padding:12px 14px;
  border-radius:12px;
  border:1px solid var(--border);
  background: rgba(255,255,255,.04);
  color: var(--text);
  font-weight:650;
}
[data-theme="light"] .field select,
[data-theme="light"] .field input[type="text"]{ background: rgba(17,24,39,.03); }
.field select:focus, .field input[type="text"]:focus{ outline:2px solid var(--focus); outline-offset:2px }
.field option{ background: var(--bg2, #ffffff); color: var(--text, #111827); }

/* Select-Liste konsistent einfärben (Optionen) */
.field select option{
  background: var(--bg2, #0f172a);
  color: var(--text);
}

/* Optgroup ist in Chromium kaum stylbar – daher: Gruppen als disabled <option> */
.field select option.optgroup-head{
  background: rgba(255,255,255,.07);
  color: var(--muted);
  font-weight: 900;
  letter-spacing: .10em;
  text-transform: uppercase;
}

/* disabled Optionen werden sonst oft “ausgegraut” – hier bewusst lesbar halten */
.field select option.optgroup-head:disabled{
  opacity: 1;
}

/* Einrückung für normale Optionen (funktioniert je nach Browser; harmless fallback) */
.field select option.optitem{
  padding-left: 14px;
}

/* Light Theme: Header leicht abgesetzt */
[data-theme="light"] .field select option.optgroup-head{
  background: rgba(17,24,39,.06);
}


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
  overflow: auto;
  -webkit-overflow-scrolling: touch;
}
.table{width:100%; border-collapse: collapse; min-width: 860px}
.table thead th{
  position: sticky;
  top: 0;
  background: var(--card);
  z-index: 1;
}
.table th, .table td{
  text-align:left;
  padding:12px 14px;
  border-bottom:1px solid var(--border);
  vertical-align:top;
  overflow-wrap:anywhere; /* E) */
}
.table th{
  color: var(--muted);
  font-weight:900;
  font-size:12px;
  letter-spacing:.07em;
  text-transform:uppercase;
  user-select:none;
}
.table td:nth-child(3){ max-width: 520px; } /* E) */
.table td:nth-child(4){ max-width: 320px; } /* E) */
.table tr:last-child td{border-bottom:none}
.table tbody tr.data-row{ cursor:pointer; }
.table tbody tr.data-row:hover{ background: rgba(255,255,255,.03); }
[data-theme="light"] .table tbody tr.data-row:hover{ background: rgba(17,24,39,.03); }

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

.badge-mini{ padding:4px 8px; font-size:11px; font-weight:900; letter-spacing:.02em; }

.thbtn{
  all:unset;
  cursor:pointer;
  display:inline-flex;
  align-items:center;
  gap:8px;
  color: var(--muted);
}
.thbtn:hover{ color: var(--text); }
.sort-ind{ opacity:.85; font-weight:900; }

.actions{
  display:flex;
  gap:8px;
  align-items:center;
  flex-wrap:wrap;
}
.iconbtn{
  border:1px solid var(--border);
  background: rgba(255,255,255,.03);
  color: var(--text);
  border-radius:10px;
  padding:8px 10px;
  font-weight:850;
  cursor:pointer;
}
[data-theme="light"] .iconbtn{ background: rgba(17,24,39,.02); }
.iconbtn:hover{ transform: translateY(-1px); }
.iconbtn:active{ transform:none; }
.iconbtn:focus{ outline:2px solid var(--focus); outline-offset:2px; }

.hl{
  background: rgba(110,168,254,.28);
  border:1px solid rgba(110,168,254,.22);
  padding:0 2px;
  border-radius:6px;
}

.notice{
  border:1px solid var(--border);
  background: rgba(255,255,255,.03);
  padding:12px 14px;
  border-radius: 12px;
  margin-top: 14px;
}
[data-theme="light"] .notice{ background: rgba(17,24,39,.02); }

.group-row td{
  background: rgba(255,255,255,.02);
  color: var(--muted);
  font-weight:900;
  letter-spacing:.04em;
  text-transform:uppercase;
}
[data-theme="light"] .group-row td{ background: rgba(17,24,39,.02); }

.modal-backdrop{
  position:fixed;
  inset:0;
  background: rgba(0,0,0,.45);
  backdrop-filter: blur(6px);
  display:none;
  align-items:flex-start;
  justify-content:center;
  padding: 22px;
  z-index: 50;
}
.modal-backdrop[open]{ display:flex; }
.modal-card{
  width:min(920px, 100%);
  margin-top: 40px;
  border:1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg2);
  box-shadow: var(--shadow);
  padding: 16px;
}
.modal-head{
  display:flex; align-items:flex-start; justify-content:space-between; gap:12px; flex-wrap:wrap;
  border-bottom:1px solid var(--border);
  padding-bottom: 12px;
  margin-bottom: 12px;
}
.modal-title{ margin:0; font-size: 22px; }
.modal-sub{ margin:6px 0 0; color: var(--muted); line-height: 1.5; }
.kv2{ display:flex; gap:10px; flex-wrap:wrap; margin-top:10px; }
.kv2 .pill{ border:1px solid var(--border); border-radius:999px; padding:8px 10px; color:var(--muted); font-weight:850; background: rgba(255,255,255,.03); }
[data-theme="light"] .kv2 .pill{ background: rgba(17,24,39,.02); }
.codebox{
  border:1px solid var(--border);
  background: rgba(255,255,255,.03);
  border-radius: 12px;
  padding: 12px;
  overflow:auto;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
  font-size: 12px;
  color: var(--text);
}
[data-theme="light"] .codebox{ background: rgba(17,24,39,.02); }

.toast{
  position:fixed;
  right: 18px;
  bottom: 18px;
  z-index: 60;
  display:none;
  border:1px solid var(--border);
  background: rgba(17,26,46,.92);
  color: var(--text);
  border-radius: 14px;
  padding: 12px 14px;
  box-shadow: var(--shadow);
  max-width: 520px;
}
[data-theme="light"] .toast{ background: rgba(255,255,255,.92); }
.toast[open]{ display:block; }
  </style>
</head>

<body>
  <a class="skip-link" href="#main">Zum Inhalt springen</a>

  <header class="site-header">
      <div class="container header-inner">
        <a class="brand" href="{{ landing_url }}" aria-label="Zur Landing Page">
          <span class="brand-mark" aria-hidden="true"></span>
          <span class="brand-text">data-tales.dev</span>
        </a>

        <div class="nav-dropdown" data-dropdown>
            <button class="btn btn-ghost nav-dropbtn"
                    type="button"
                    aria-haspopup="true"
                    aria-expanded="false"
                    aria-controls="servicesMenu">
              Dienste <span class="nav-caret" aria-hidden="true">▾</span>
            </button>

            <div id="servicesMenu" class="card nav-menu" role="menu" hidden>
              <a role="menuitem" href="https://flybi-demo.data-tales.dev/">Flybi Dashboard Demo</a>
              <a role="menuitem" href="https://wms-wfs-sources.data-tales.dev/">WMS/WFS Server Viewer</a>
              <a role="menuitem" href="https://tree-locator.data-tales.dev/">Tree Locator</a>
              <a role="menuitem" href="https://plz.data-tales.dev/">PLZ → Koordinaten</a>
              <a role="menuitem" href="https://paw-wiki.data-tales.dev/">Paw Wiki</a>
              <a role="menuitem" href="https://paw-quiz.data-tales.dev/">Paw Quiz</a>
              <a role="menuitem" href="https://wizard-quiz.data-tales.dev/">Wizard Quiz</a>
              <a role="menuitem" href="https://worm-attack-3000.data-tales.dev/">Wurm Attacke 3000</a>
            </div>
        </div>

        <div class="header-actions">
          <div class="header-note" aria-label="Feedback Kontakt">
            <span class="header-note__label">Änderung / Kritik:</span>
            <a class="header-note__mail" href="mailto:info@data-tales.dev">info@data-tales.dev</a>
          </div>

          <button class="btn btn-ghost" id="themeToggle" type="button" aria-label="Theme umschalten">
            <span aria-hidden="true" id="themeIcon">☾</span>
            <span class="sr-only">Theme umschalten</span>
          </button>
        </div>
      </div>
    </header>


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
              <label for="serviceSearch">Service suchen</label>
              <input id="serviceSearch" type="text" placeholder="z. B. DWD, BKG, Copernicus …" autocomplete="off" />
            </div>

            <div class="field">
              <label for="service">Service</label>
              <select id="service" name="service" required>
                <option value="" {% if not selected %}selected{% endif %}>Bitte wählen…</option>

                {% for group_label, entries in service_groups %}
                <option class="optgroup-head" disabled>— {{ group_label }} —</option>
                {% for key, svcopt in entries %}
                    <option class="optitem" value="{{ key }}" {% if selected == key %}selected{% endif %}>
                    {{ svcopt.label }}
                    </option>
                {% endfor %}
                {% endfor %}

              </select>
            </div>

            <div class="inline">
              <label class="checkbox" for="refresh">
                <input type="checkbox" id="refresh" name="refresh" value="1" {% if refresh == 1 %}checked{% endif %} />
                Cache umgehen (refresh=1)
              </label>

              <label class="checkbox" for="groupByPrefix">
                <input type="checkbox" id="groupByPrefix" />
                Nach Prefix gruppieren
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
            <span class="pill">Fetched: <strong>{{ fetched_at_dt or "—" }}</strong>{% if fetched_in_s %} <span class="small">({{ fetched_in_s }}s)</span>{% endif %}</span>
          </div>

          {% if ui_truncated %}
            <div class="notice">
              <strong>Hinweis:</strong> Im UI werden aus Performance-Gründen nur <strong>{{ ui_limit }}</strong> von <strong>{{ counts_items }}</strong> Items gerendert.
              Nutze Filter/Sortierung oder exportiere via <strong>JSON (/api)</strong>.
            </div>
          {% endif %}

          <div class="search">
            <input id="tableFilter" type="text" placeholder="Tabelle filtern (Name, Titel, Prefix) …" autocomplete="off" />
          </div>

          <div class="inline" style="margin-top: 10px; justify-content:space-between;">
            <div class="small" id="filterStats">—</div>
            <button class="iconbtn" id="clearFilter" type="button">Filter löschen</button>
          </div>

          <div class="table-wrap table-wrap--vh" style="margin-top: 14px;">
            <table class="table" id="resultTable"
              data-svc-kind="{{ svc.kind }}"
              data-svc-url="{{ svc.url }}"
              data-svc-version="{{ svc.version or '' }}"
              data-svc-cap-url="{{ svc.capabilities_url }}"
              data-svc-output-formats='{{ (svc.output_formats or [])|tojson }}'>
              <thead>
                <tr>
                  <th><button class="thbtn" type="button" data-sort="type">Typ <span class="sort-ind" aria-hidden="true"></span></button></th>
                  <th><button class="thbtn" type="button" data-sort="prefix">Prefix <span class="sort-ind" aria-hidden="true"></span></button></th>
                  <th><button class="thbtn" type="button" data-sort="name">Name <span class="sort-ind" aria-hidden="true"></span></button></th>
                  <th><button class="thbtn" type="button" data-sort="title">Titel <span class="sort-ind" aria-hidden="true"></span></button></th>
                  <th><button class="thbtn" type="button" data-sort="details">Details <span class="sort-ind" aria-hidden="true"></span></button></th>
                  <th>Aktionen</th>
                </tr>
              </thead>
              <tbody id="tbody">
                {% for it in rows_ui %}
                  <tr class="data-row"
                      data-row="1"
                      data-type="{{ it.type }}"
                      data-name="{{ it.name }}"
                      data-prefix="{{ it.prefix or '' }}"
                      data-local-name="{{ it.local_name or it.name }}"
                      data-title="{{ it.title or '' }}"
                      data-abstract="{{ it.abstract or '' }}"
                      data-queryable="{{ it.queryable or '' }}"
                      data-default-crs="{{ it.default_crs or '' }}"
                      data-crs='{{ (it.crs or [])|tojson }}'
                      data-bbox='{{ (it.bbox_wgs84 or {})|tojson }}'
                      data-styles='{{ (it.styles or [])|tojson }}'>
                    <td class="small">{% if it.type == "wms_layer" %}WMS{% else %}WFS{% endif %}</td>
                    <td class="small">
                      {% if it.prefix %}
                        <span class="badge badge-mini">{{ it.prefix }}</span>
                      {% else %}
                        —
                      {% endif %}
                    </td>
                    <td>
                      <span class="nameLocal"><strong>{{ it.local_name or it.name }}</strong></span>
                      <span class="sr-only nameFull">{{ it.name }}</span>
                    </td>
                    <td><span class="titleText">{{ it.title }}</span></td>
                    <td class="small">
                      {% if it.type == "wms_layer" %}
                        Styles: {{ (it.styles|length) if it.styles is defined else 0 }}
                        {% if it.crs and (it.crs|length) > 0 %}
                          <br/>CRS: {{ it.crs[0] }}{% if (it.crs|length) > 1 %} <span class="badge">+{{ (it.crs|length)-1 }}</span>{% endif %}
                        {% endif %}
                        {% if it.bbox_wgs84 %}
                          <br/>BBOX: {{ it.bbox_wgs84.minx }},{{ it.bbox_wgs84.miny }},{{ it.bbox_wgs84.maxx }},{{ it.bbox_wgs84.maxy }}
                        {% endif %}
                      {% else %}
                        {% if it.default_crs %}CRS: {{ it.default_crs }}{% else %}CRS: —{% endif %}
                        {% if it.bbox_wgs84 %}
                          <br/>BBOX: {{ it.bbox_wgs84.minx }},{{ it.bbox_wgs84.miny }},{{ it.bbox_wgs84.maxx }},{{ it.bbox_wgs84.maxy }}
                        {% endif %}
                      {% endif %}
                    </td>
                    <td>
                      <div class="actions">
                        <button class="iconbtn act-copy" type="button" title="Name kopieren">Copy</button>
                        <button class="iconbtn act-example" type="button" title="Beispiel-Request">Example</button>
                        <button class="iconbtn act-details" type="button" title="Details">Details</button>
                      </div>
                    </td>
                  </tr>
                {% endfor %}
              </tbody>
            </table>
          </div>

          <p class="small" style="margin-top: 12px;">
            Hinweis: Filter/Sortierung/Grouping laufen clientseitig. Rohdaten stammen aus dem Capabilities-Dokument.
          </p>
        </div>
      {% endif %}
    </section>
  </main>

  <!-- Modal -->
  <div class="modal-backdrop" id="detailBackdrop" role="dialog" aria-modal="true" aria-labelledby="detailTitle">
    <div class="modal-card">
      <div class="modal-head">
        <div>
          <h3 class="modal-title" id="detailTitle">Details</h3>
          <p class="modal-sub" id="detailSub">—</p>
          <div class="kv2" id="detailPills"></div>
        </div>
        <div class="inline">
          <button class="iconbtn" id="modalCopyName" type="button">Name kopieren</button>
          <button class="iconbtn" id="modalCopyCap" type="button">Capabilities kopieren</button>
          <button class="iconbtn" id="modalClose" type="button">Schließen</button>
        </div>
      </div>

      <div class="small" style="margin-bottom:10px;">Beschreibung</div>
      <div class="codebox" id="detailAbstract">—</div>

      <div class="section-head" style="margin-top:16px; margin-bottom:10px;">
        <h2 style="font-size:18px;">Requests</h2>
      </div>

      <div class="small" style="margin-bottom:6px;">Beispiel</div>
      <div class="codebox" id="detailExample">—</div>
      <div class="inline" style="margin-top:10px;">
        <button class="iconbtn" id="modalCopyExample" type="button">Example kopieren</button>
        <a class="iconbtn" id="modalOpenExample" href="#" target="_blank" rel="noreferrer">Example öffnen</a>
      </div>

      <div class="section-head" style="margin-top:16px; margin-bottom:10px;">
        <h2 style="font-size:18px;">Details</h2>
      </div>
      <div class="codebox" id="detailJson">—</div>
    </div>
  </div>

  <!-- Toast -->
  <div class="toast" id="toast" role="status" aria-live="polite"></div>

  <script>
    (function(){
    const dd = document.querySelector('[data-dropdown]');
    if(!dd) return;

    const btn = dd.querySelector('.nav-dropbtn');
    const menu = dd.querySelector('.nav-menu');

    function setOpen(isOpen){
      btn.setAttribute('aria-expanded', String(isOpen));
      if(isOpen){
        menu.hidden = false;
        dd.classList.add('open');
      }else{
        menu.hidden = true;
        dd.classList.remove('open');
      }
    }

    btn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      const isOpen = btn.getAttribute('aria-expanded') === 'true';
      setOpen(!isOpen);
    });

    document.addEventListener('click', (e) => {
      if(!dd.contains(e.target)) setOpen(false);
    });

    document.addEventListener('keydown', (e) => {
      if(e.key === 'Escape') setOpen(false);
    });

    // Wenn per Tab aus dem Dropdown rausnavigiert wird: schließen
    dd.addEventListener('focusout', () => {
      requestAnimationFrame(() => {
        if(!dd.contains(document.activeElement)) setOpen(false);
      });
    });

    // Initial geschlossen
    setOpen(false);
  })();
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

  // Service search -> filter select options
  (function() {
    const input = document.getElementById('serviceSearch');
    const sel = document.getElementById('service');
    if (!input || !sel) return;

    function applyFilter() {
      const q = (input.value || '').toLowerCase().trim();
      const groups = sel.querySelectorAll('optgroup');
      const options = sel.querySelectorAll('option');

      options.forEach(opt => {
        if (!opt.value) return;
        const txt = (opt.textContent || '').toLowerCase();
        opt.hidden = q && !txt.includes(q);
      });

      groups.forEach(g => {
        const visibleChild = Array.from(g.querySelectorAll('option')).some(o => !o.hidden);
        g.hidden = !visibleChild;
      });
    }

    input.addEventListener('input', applyFilter);
  })();

  // Toast helper
  (function() {
    const el = document.getElementById('toast');
    let t = null;
    window.__toast = function(msg) {
      if (!el) return;
      el.textContent = msg;
      el.setAttribute('open', 'open');
      clearTimeout(t);
      t = setTimeout(() => el.removeAttribute('open'), 2400);
    };
  })();

  // Table controller: filter + highlight + stats + sort + prefix group + modal + copy + examples
  (function() {
    const input = document.getElementById('tableFilter');
    const clearBtn = document.getElementById('clearFilter');
    const stats = document.getElementById('filterStats');
    const groupToggle = document.getElementById('groupByPrefix');
    const table = document.getElementById('resultTable');
    const tbody = document.getElementById('tbody');
    if (!table || !tbody) return;

    const svcKind = table.dataset.svcKind || '';
    const svcUrl = table.dataset.svcUrl || '';
    const svcVersion = table.dataset.svcVersion || '';
    const capUrl = table.dataset.svcCapUrl || '';
    let outputFormats = [];
    try { outputFormats = JSON.parse(table.dataset.svcOutputFormats || '[]') || []; } catch(e) {}

    const world3857 = "-20037508.342789244,-20037508.342789244,20037508.342789244,20037508.342789244";
    const crs3857 = "EPSG:3857";

    function mergeUrl(baseUrl, params) {
      const u = new URL(baseUrl);
      // delete case-insensitive duplicates for each param
      Object.keys(params).forEach(k => {
        const target = k.toLowerCase();
        Array.from(u.searchParams.keys()).forEach(existing => {
          if (existing.toLowerCase() === target && existing !== k) u.searchParams.delete(existing);
        });
        u.searchParams.set(k, params[k]);
      });
      return u.toString();
    }

    function pickOutputFormat() {
      const lower = outputFormats.map(x => (x || '').toLowerCase());
      const idxJson = lower.findIndex(x => x.includes("json"));
      if (idxJson >= 0) return outputFormats[idxJson];
      if (outputFormats.length) return outputFormats[0];
      return "application/json";
    }

    function buildExampleForRow(rowData) {
      if (rowData.type === "wms_layer") {
        const is13 = (svcVersion || '').startsWith("1.3");
        const params = {
          service: "WMS",
          request: "GetMap",
          ...(svcVersion ? {version: svcVersion} : {}),
          layers: rowData.name,
          styles: "",
          format: "image/png",
          transparent: "true",
          width: "800",
          height: "500",
          ...(is13 ? {crs: crs3857} : {srs: crs3857}),
          bbox: world3857,
        };
        return mergeUrl(svcUrl, params);
      }

      // WFS
      const is20 = (svcVersion || '').startsWith("2.");
      const typeKey = is20 ? "typenames" : "typename";
      const limitKey = is20 ? "count" : "maxFeatures";
      const getFeature = mergeUrl(svcUrl, {
        service: "WFS",
        request: "GetFeature",
        ...(svcVersion ? {version: svcVersion} : {}),
        [typeKey]: rowData.name,
        [limitKey]: "10",
        outputFormat: pickOutputFormat(),
      });

      const describe = mergeUrl(svcUrl, {
        service: "WFS",
        request: "DescribeFeatureType",
        ...(svcVersion ? {version: svcVersion} : {}),
        typeName: rowData.name
      });

      return getFeature + "\n\n" + describe;
    }

    // Model rows
    const rows = Array.from(tbody.querySelectorAll('tr[data-row="1"]')).map(tr => {
      let crs = [];
      let bbox = {};
      let styles = [];
      try { crs = JSON.parse(tr.dataset.crs || '[]') || []; } catch(e) {}
      try { bbox = JSON.parse(tr.dataset.bbox || '{}') || {}; } catch(e) {}
      try { styles = JSON.parse(tr.dataset.styles || '[]') || []; } catch(e) {}

      const nameLocalEl = tr.querySelector('.nameLocal');
      const titleEl = tr.querySelector('.titleText');
      const localNameText = (tr.dataset.localName || '').trim();
      const titleText = (tr.dataset.title || '').trim();

      return {
        tr,
        type: tr.dataset.type || '',
        name: tr.dataset.name || '',
        prefix: tr.dataset.prefix || '',
        localName: localNameText || (tr.dataset.name || ''),
        title: titleText,
        abstract: tr.dataset.abstract || '',
        queryable: tr.dataset.queryable || '',
        defaultCrs: tr.dataset.defaultCrs || '',
        crs,
        bbox,
        styles,
        nameLocalEl,
        titleEl,
        baseText: ((tr.dataset.type || '') + " " + (tr.dataset.prefix || '') + " " + (tr.dataset.name || '') + " " + (tr.dataset.title || '')).toLowerCase()
      };
    });

    // Sorting state
    let sortKey = "name";
    let sortDir = "asc";

    function setSortIndicators() {
      table.querySelectorAll('th .sort-ind').forEach(el => el.textContent = "");
      const btn = table.querySelector(`.thbtn[data-sort="${sortKey}"]`);
      if (!btn) return;
      const ind = btn.querySelector('.sort-ind');
      if (ind) ind.textContent = sortDir === "asc" ? "▲" : "▼";
    }

    function cmp(a, b) {
      function v(x) {
        if (sortKey === "type") return (x.type || "");
        if (sortKey === "prefix") return (x.prefix || "");
        if (sortKey === "title") return (x.title || "");
        if (sortKey === "details") return (x.type === "wms_layer" ? (x.crs[0] || "") : (x.defaultCrs || ""));
        // name
        return (x.localName || x.name || "");
      }
      const av = v(a).toLowerCase();
      const bv = v(b).toLowerCase();
      if (av < bv) return sortDir === "asc" ? -1 : 1;
      if (av > bv) return sortDir === "asc" ? 1 : -1;
      return 0;
    }

    function escapeHtml(s) {
      return String(s)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
    }

    function highlightText(text, q) {
      if (!q) return escapeHtml(text);
      const t = String(text);
      const idx = t.toLowerCase().indexOf(q);
      if (idx < 0) return escapeHtml(t);
      const before = escapeHtml(t.slice(0, idx));
      const mid = escapeHtml(t.slice(idx, idx + q.length));
      const after = escapeHtml(t.slice(idx + q.length));
      return before + '<span class="hl">' + mid + '</span>' + after;
    }

    function clearHighlights(r) {
      if (r.nameLocalEl) r.nameLocalEl.innerHTML = "<strong>" + escapeHtml(r.localName) + "</strong>";
      if (r.titleEl) r.titleEl.innerHTML = escapeHtml(r.title);
    }

    function applyHighlights(r, q) {
      if (!q) { clearHighlights(r); return; }
      if (r.nameLocalEl) r.nameLocalEl.innerHTML = "<strong>" + highlightText(r.localName, q) + "</strong>";
      if (r.titleEl) r.titleEl.innerHTML = highlightText(r.title, q);
    }

    function removeGroupRows() {
      Array.from(tbody.querySelectorAll('tr.group-row')).forEach(tr => tr.remove());
    }

    function insertGroupRows(visibleRowsSorted) {
      removeGroupRows();
      let last = null;
      visibleRowsSorted.forEach(r => {
        const p = (r.prefix || "—");
        if (p !== last) {
          const g = document.createElement('tr');
          g.className = 'group-row';
          const td = document.createElement('td');
          td.colSpan = 6;
          td.textContent = (p === "—" ? "Ohne Prefix" : p);
          g.appendChild(td);
          tbody.insertBefore(g, r.tr);
          last = p;
        }
      });
    }

    function render() {
      const q = (input ? input.value : '').toLowerCase().trim();
      const group = !!(groupToggle && groupToggle.checked);

      // filter + highlight + count
      let visible = [];
      rows.forEach(r => {
        const hit = (!q || r.baseText.includes(q));
        r.tr.style.display = hit ? "" : "none";
        if (hit) visible.push(r);
        applyHighlights(r, q);
      });

      // sort visible
      visible.sort(cmp);

      // reorder DOM: append in sorted order (keeps others in DOM but display none)
      removeGroupRows();
      visible.forEach(r => tbody.appendChild(r.tr));
      // keep hidden rows at end to avoid reflow jitter
      rows.filter(r => !visible.includes(r)).forEach(r => tbody.appendChild(r.tr));

      if (group) insertGroupRows(visible);

      if (stats) stats.textContent = `${visible.length} / ${rows.length} sichtbar`;
      setSortIndicators();
    }

    // sort header clicks
    table.querySelectorAll('.thbtn[data-sort]').forEach(btn => {
      btn.addEventListener('click', () => {
        const k = btn.getAttribute('data-sort');
        if (!k) return;
        if (sortKey === k) {
          sortDir = (sortDir === "asc") ? "desc" : "asc";
        } else {
          sortKey = k;
          sortDir = "asc";
        }
        render();
      });
    });

    // filter input
    if (input) input.addEventListener('input', render);
    if (groupToggle) groupToggle.addEventListener('change', render);
    if (clearBtn) clearBtn.addEventListener('click', () => {
      if (input) input.value = "";
      render();
      input && input.focus();
    });

    // Modal logic
    const backdrop = document.getElementById('detailBackdrop');
    const closeBtn = document.getElementById('modalClose');
    const copyNameBtn = document.getElementById('modalCopyName');
    const copyCapBtn = document.getElementById('modalCopyCap');
    const copyExampleBtn = document.getElementById('modalCopyExample');
    const openExampleLink = document.getElementById('modalOpenExample');

    const titleEl = document.getElementById('detailTitle');
    const subEl = document.getElementById('detailSub');
    const pillsEl = document.getElementById('detailPills');
    const abstractEl = document.getElementById('detailAbstract');
    const exampleEl = document.getElementById('detailExample');
    const jsonEl = document.getElementById('detailJson');

    let current = null;
    function openModal(r) {
      current = r;
      if (!backdrop) return;
      backdrop.setAttribute('open', 'open');

      const kindLabel = (r.type === "wms_layer") ? "WMS Layer" : "WFS FeatureType";
      if (titleEl) titleEl.textContent = (r.localName || r.name || "Details");
      if (subEl) subEl.textContent = `${kindLabel} · ${r.name}`;

      // pills
      if (pillsEl) {
        pillsEl.innerHTML = "";
        const addPill = (txt) => {
          const s = document.createElement('span');
          s.className = "pill";
          s.textContent = txt;
          pillsEl.appendChild(s);
        };
        addPill(`Prefix: ${r.prefix || "—"}`);
        if (r.type === "wms_layer") {
          addPill(`Styles: ${(r.styles || []).length}`);
          addPill(`CRS: ${(r.crs && r.crs.length) ? r.crs[0] : "—"}`);
          if (r.bbox && ("minx" in r.bbox)) addPill(`BBOX: ${r.bbox.minx},${r.bbox.miny},${r.bbox.maxx},${r.bbox.maxy}`);
          if (r.queryable) addPill(`Queryable: ${r.queryable}`);
        } else {
          addPill(`DefaultCRS: ${r.defaultCrs || "—"}`);
          if (r.bbox && ("minx" in r.bbox)) addPill(`BBOX: ${r.bbox.minx},${r.bbox.miny},${r.bbox.maxx},${r.bbox.maxy}`);
          if (outputFormats && outputFormats.length) addPill(`OutputFormats: ${outputFormats.length}`);
        }
      }

      // abstract
      if (abstractEl) abstractEl.textContent = (r.abstract && r.abstract.trim()) ? r.abstract.trim() : "—";

      // example
      const ex = buildExampleForRow(r);
      if (exampleEl) exampleEl.textContent = ex;

      if (openExampleLink) {
        // for WFS example contains 2 urls; open first
        const first = ex.split("\n")[0].trim();
        openExampleLink.href = first || "#";
      }

      // detail json (row + service)
      if (jsonEl) {
        const payload = {
          service: {
            kind: svcKind,
            url: svcUrl,
            version: svcVersion,
            capabilities_url: capUrl,
            output_formats: outputFormats,
          },
          item: {
            type: r.type,
            name: r.name,
            prefix: r.prefix,
            local_name: r.localName,
            title: r.title,
            abstract: r.abstract,
            queryable: r.queryable,
            default_crs: r.defaultCrs,
            crs: r.crs,
            bbox_wgs84: r.bbox,
            styles: r.styles,
          }
        };
        jsonEl.textContent = JSON.stringify(payload, null, 2);
      }
    }

    function closeModal() {
      if (!backdrop) return;
      backdrop.removeAttribute('open');
      current = null;
    }

    if (closeBtn) closeBtn.addEventListener('click', closeModal);
    if (backdrop) backdrop.addEventListener('click', (e) => {
      if (e.target === backdrop) closeModal();
    });
    document.addEventListener('keydown', (e) => {
      if (e.key === "Escape" && backdrop && backdrop.hasAttribute('open')) closeModal();
    });

    async function copyToClipboard(text) {
      try {
        await navigator.clipboard.writeText(text);
        window.__toast && window.__toast("Kopiert.");
      } catch(e) {
        window.__toast && window.__toast("Kopieren nicht möglich (Browser/Permission).");
      }
    }

    if (copyNameBtn) copyNameBtn.addEventListener('click', () => current && copyToClipboard(current.name));
    if (copyCapBtn) copyCapBtn.addEventListener('click', () => copyToClipboard(capUrl));
    if (copyExampleBtn) copyExampleBtn.addEventListener('click', () => current && copyToClipboard(buildExampleForRow(current)));

    // Row actions + row click
    rows.forEach(r => {
      const tr = r.tr;

      // click row => details
      tr.addEventListener('click', () => openModal(r));

      // action buttons
      const btnCopy = tr.querySelector('.act-copy');
      const btnExample = tr.querySelector('.act-example');
      const btnDetails = tr.querySelector('.act-details');

      if (btnCopy) btnCopy.addEventListener('click', (e) => {
        e.stopPropagation();
        copyToClipboard(r.name);
      });

      if (btnExample) btnExample.addEventListener('click', (e) => {
        e.stopPropagation();
        const ex = buildExampleForRow(r);
        copyToClipboard(ex);
      });

      if (btnDetails) btnDetails.addEventListener('click', (e) => {
        e.stopPropagation();
        openModal(r);
      });
    });

    // Initial sort + stats
    render();
  })();
  </script>
</body>
</html>
"""

# ------------------------------------------------------------
# Flask app
# ------------------------------------------------------------

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
        # API always returns full items (no UI soft-limit)
        data["cache"] = {"ttl_seconds": CACHE_TTL_SECONDS, "refresh_bypass": bool(refresh)}
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

    # Grouped services for <optgroup>
    service_groups = _services_grouped()

    has_data = bool(data and isinstance(data, dict))
    svc = (data or {}).get("service", {}) if has_data else {}
    counts = (data or {}).get("counts", {}) if has_data else {}
    rows = (data or {}).get("items", []) if has_data else []
    counts_items = counts.get("items", 0) if isinstance(counts, dict) else 0
    counts_styles = counts.get("styles", None) if isinstance(counts, dict) else None
    fetched_at = (data or {}).get("fetched_at", None) if has_data else None
    fetch_ms = (data or {}).get("fetch_ms", None) if has_data else None

    fetched_at_dt = None
    if fetched_at:
        try:
            fetched_at_dt = datetime.fromtimestamp(int(fetched_at)).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            fetched_at_dt = None

    fetched_in_s = None
    if fetch_ms is not None:
        try:
            fetched_in_s = f"{(int(fetch_ms) / 1000.0):.2f}"
        except Exception:
            fetched_in_s = None

    # UI soft-limit (HTML only)
    ui_truncated = False
    rows_ui = rows
    if isinstance(rows, list) and UI_SOFT_LIMIT > 0 and len(rows) > UI_SOFT_LIMIT:
        ui_truncated = True
        rows_ui = rows[:UI_SOFT_LIMIT]

    return render_template_string(
        HTML_TEMPLATE,
        meta=APP_META,
        landing_url=LANDING_URL,
        nav_links=_nav_links_html(),
        service_groups=service_groups,
        selected=service_key or None,
        refresh=refresh,
        error=error,
        has_data=has_data,
        svc=svc,
        counts_items=counts_items,
        counts_styles=counts_styles,
        fetched_at_dt=fetched_at_dt,
        fetched_in_s=fetched_in_s,
        ui_truncated=ui_truncated,
        ui_limit=UI_SOFT_LIMIT,
        rows_ui=rows_ui,
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
