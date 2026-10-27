"""Distance and transport-time helpers."""
import math

EARTH_RADIUS_KM = 6371.0088
ROAD_SPEED_KMH = 50.0
AIR_SPEED_KMH = 500.0
AIR_OVERHEAD_H = 2.5       # airport transfers and boarding
ROAD_LIMIT_KM = 250.0      # beyond this we assume air transport
RETRIEVAL_BUFFER_H = 1.0   # organ retrieval and packing


def haversine_km(lat1, lng1, lat2, lng2):
    """Great-circle distance between two points in kilometres."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def transport_hours(distance_km):
    """Door-to-door hours for an organ, including the retrieval buffer."""
    if distance_km <= ROAD_LIMIT_KM:
        travel = distance_km / ROAD_SPEED_KMH
    else:
        travel = distance_km / AIR_SPEED_KMH + AIR_OVERHEAD_H
    return travel + RETRIEVAL_BUFFER_H
