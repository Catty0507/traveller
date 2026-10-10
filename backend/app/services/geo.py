"""地理计算工具。"""

import math


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> int:
    """两点间大圆距离(km,四舍五入取整)。"""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(2 * r * math.asin(math.sqrt(a)))
