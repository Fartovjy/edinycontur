import math
import logging

import requests as http_requests

log = logging.getLogger(__name__)

OSRM_URL = "http://router.project-osrm.org"
YANDEX_GEOCODE_URL = "https://geocode-maps.yandex.ru/1.x/"
REQUEST_TIMEOUT = 5
KM_PER_DAY = 500

DIRECTION_MAP = {
    "dir-n":  ("С",  "↑"),
    "dir-ne": ("СВ", "↗"),
    "dir-e":  ("В",  "→"),
    "dir-se": ("ЮВ", "↘"),
    "dir-s":  ("Ю",  "↓"),
    "dir-sw": ("ЮЗ", "↙"),
    "dir-w":  ("З",  "←"),
    "dir-nw": ("СЗ", "↖"),
}


def geocode_yandex(address, api_key):
    """Возвращает (lat, lon) или None."""
    try:
        r = http_requests.get(
            YANDEX_GEOCODE_URL,
            params={"apikey": api_key, "geocode": address, "format": "json", "results": 1},
            timeout=REQUEST_TIMEOUT,
        )
        r.raise_for_status()
        pos = (
            r.json()["response"]["GeoObjectCollection"]
            ["featureMember"][0]["GeoObject"]["Point"]["pos"]
        )
        lon, lat = map(float, pos.split())
        return lat, lon
    except Exception as exc:
        log.warning("geocode_yandex failed for %r: %s", address, exc)
        return None


def geocode_nominatim(address):
    """Fallback геокодер через OpenStreetMap Nominatim. Без API-ключа, бесплатно."""
    try:
        r = http_requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": address, "format": "json", "limit": 1, "accept-language": "ru"},
            headers={"User-Agent": "ediny-kontur-logistics/1.0"},
            timeout=REQUEST_TIMEOUT,
        )
        r.raise_for_status()
        results = r.json()
        if not results:
            return None
        return float(results[0]["lat"]), float(results[0]["lon"])
    except Exception as exc:
        log.warning("geocode_nominatim failed for %r: %s", address, exc)
        return None


def geocode(address, api_key=""):
    """Яндекс если ключ есть и работает, иначе Nominatim."""
    if api_key:
        coords = geocode_yandex(address, api_key)
        if coords:
            return coords
    return geocode_nominatim(address)


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def osrm_km(lat1, lon1, lat2, lon2):
    """Расстояние по дорогам через публичный OSRM. Возвращает км или None."""
    try:
        r = http_requests.get(
            f"{OSRM_URL}/route/v1/driving/{lon1},{lat1};{lon2},{lat2}",
            params={"overview": "false"},
            timeout=REQUEST_TIMEOUT,
        )
        r.raise_for_status()
        return r.json()["routes"][0]["distance"] / 1000
    except Exception:
        return None


def road_distance_km(lat1, lon1, lat2, lon2):
    """OSRM с фоллбэком Хаверсин × 1.3."""
    dist = osrm_km(lat1, lon1, lat2, lon2)
    if dist is not None:
        return dist
    return haversine_km(lat1, lon1, lat2, lon2) * 1.3


def bearing_to_direction_css(lat1, lon1, lat2, lon2):
    dlon = math.radians(lon2 - lon1)
    x = math.sin(dlon) * math.cos(math.radians(lat2))
    y = (math.cos(math.radians(lat1)) * math.sin(math.radians(lat2))
         - math.sin(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.cos(dlon))
    bearing = (math.degrees(math.atan2(x, y)) + 360) % 360
    idx = int((bearing + 22.5) / 45) % 8
    return ["dir-n", "dir-ne", "dir-e", "dir-se", "dir-s", "dir-sw", "dir-w", "dir-nw"][idx]


def compute_route_info(warehouse_address, client_address, api_key):
    """
    Вычисляет расстояние, направление и дни для маршрута склад→клиент.
    Возвращает dict с ключами: route_distance_km, route_direction_css,
    route_direction_label, route_direction_arrow, route_days.
    При любой ошибке возвращает all-None/blank dict.
    """
    empty = {
        "route_distance_km": None,
        "route_direction_css": "",
        "route_direction_label": "",
        "route_direction_arrow": "",
        "route_days": None,
    }
    wh = geocode(warehouse_address, api_key)
    if not wh:
        return empty

    cl = geocode(client_address, api_key)
    if not cl:
        return empty

    one_way = road_distance_km(*wh, *cl)
    total_km = round(one_way * 2, 1)
    css = bearing_to_direction_css(*wh, *cl)
    label, arrow = DIRECTION_MAP[css]

    return {
        "route_distance_km": total_km,
        "route_direction_css": css,
        "route_direction_label": label,
        "route_direction_arrow": arrow,
        "route_days": max(1, math.ceil(total_km / KM_PER_DAY)),
    }
