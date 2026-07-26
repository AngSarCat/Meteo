"""
mfc.py

Moisture Flux Convergence (MFC) at each SYNOP station, from the same 22-
station surface network used across the panel (Girona..Bastia).

MFC = -div(q * V) = -(q * div(V) + V . grad(q))

Computed with a local least-squares planar fit (u, v, q each as a linear
function of local east/north distance in km from the target station) over
each station's nearest neighbours, which is the standard practical way to
estimate spatial derivatives from an irregular station network.

q (specific humidity, kg/kg) is derived from T/Td/P via the Magnus formula
for saturation vapour pressure and the standard mixing-ratio relation.

Output units: MFC is reported ×10^-5 s^-1, matching the original card's
domain (roughly -1.5 .. 1.5) so downstream code / colour scale can be
reused unchanged.
"""
from __future__ import annotations
import math
import numpy as np


def specific_humidity(temp_c: float, dewpoint_c: float | None, pressure_hpa: float) -> float | None:
    if dewpoint_c is None or pressure_hpa is None:
        return None
    # Magnus formula for saturation vapour pressure at the dewpoint (= actual vapour pressure)
    e_hpa = 6.112 * math.exp(17.62 * dewpoint_c / (243.12 + dewpoint_c))
    w = 0.622 * e_hpa / (pressure_hpa - e_hpa)  # mixing ratio, kg/kg
    q = w / (1 + w)
    return q


def _local_xy_km(lat0, lon0, lat, lon):
    """Equirectangular approx, good enough at this network's scale (<1500km)."""
    R = 6371.0
    x = math.radians(lon - lon0) * R * math.cos(math.radians((lat + lat0) / 2.0))
    y = math.radians(lat - lat0) * R
    return x, y


def _planar_fit(xs, ys, vals):
    """Least-squares fit val = a + b*x + c*y -> returns (a, dval/dx, dval/dy)."""
    A = np.column_stack([np.ones(len(xs)), xs, ys])
    v = np.array(vals)
    coef, *_ = np.linalg.lstsq(A, v, rcond=None)
    return coef  # a, b, c


def compute_mfc_for_all(stations: dict, n_neighbors: int = 7) -> dict:
    """
    stations: {id: {'lat':.., 'lon':.., 'temp_c':.., 'dewpoint_c':.., 'pressure_hpa':..,
                     'wind_dir_deg':.., 'wind_speed_ms':..}}
    Returns {id: mfc_value_1e-5_per_s or None}
    """
    ids = list(stations.keys())
    prepared = {}
    for sid, s in stations.items():
        q = specific_humidity(s['temp_c'], s.get('dewpoint_c'), s.get('pressure_hpa') or 1013.0)
        wd, ws = s.get('wind_dir_deg'), s.get('wind_speed_ms')
        if wd is None or ws is None:
            u = v = 0.0
        else:
            u = -ws * math.sin(math.radians(wd))
            v = -ws * math.cos(math.radians(wd))
        prepared[sid] = {'lat': s['lat'], 'lon': s['lon'], 'q': q, 'u': u, 'v': v}

    out = {}
    for sid in ids:
        tgt = prepared[sid]
        if tgt['q'] is None:
            out[sid] = None
            continue
        others = [(oid, o) for oid, o in prepared.items() if oid != sid and o['q'] is not None]
        others.sort(key=lambda o: (o[1]['lat'] - tgt['lat']) ** 2 + (o[1]['lon'] - tgt['lon']) ** 2)
        neighbors = [tgt] + [o for _, o in others[:n_neighbors]]
        if len(neighbors) < 4:
            out[sid] = None
            continue
        xs, ys = [], []
        us, vs, qs = [], [], []
        for n in neighbors:
            x, y = _local_xy_km(tgt['lat'], tgt['lon'], n['lat'], n['lon'])
            xs.append(x * 1000.0)  # -> metres
            ys.append(y * 1000.0)
            us.append(n['u'])
            vs.append(n['v'])
            qs.append(n['q'])
        try:
            _, du_dx, _ = _planar_fit(xs, ys, us)
            _, _, dv_dy = _planar_fit(xs, ys, vs)
            _, dq_dx, dq_dy = _planar_fit(xs, ys, qs)
        except Exception:
            out[sid] = None
            continue
        div_v = du_dx + dv_dy
        mfc = -(tgt['q'] * div_v + tgt['u'] * dq_dx + tgt['v'] * dq_dy)  # s^-1
        out[sid] = round(mfc * 1e5, 2)
    return out


if __name__ == '__main__':
    import sys
    sys.path.insert(0, '.')
    from synop_decoder import split_stations, decode_station_latest

    COORDS = {
        '08184': (41.901, 2.760), '08181': (41.297, 2.083), '08175': (41.147, 1.167),
        '08286': (39.997, -0.054), '08284': (39.489, -0.481), '08359': (38.282, -0.558),
        '08487': (36.844, -2.358), '08301': (39.553, 2.739), '08373': (38.873, 1.373),
        '08314': (39.862, 4.219), '08159': (41.666, -1.042), '08279': (38.949, -1.864),
        '60320': (35.900, -5.317), '60338': (35.280, -2.956), '08535': (38.717, -9.150),
        '08554': (37.014, -7.966), '07747': (42.740, 2.871), '07643': (43.576, 3.963),
        '07650': (43.439, 5.221), '07690': (43.658, 7.215), '07761': (41.923, 8.803),
        '07790': (42.552, 9.484),
    }
    raw = open(sys.argv[1] if len(sys.argv) > 1 else 'raw_synop_20260726.txt', encoding='utf-8').read()
    blocks = split_stations(raw)
    stations = {}
    for sid, block in blocks.items():
        d = decode_station_latest(block)
        if d is None or sid not in COORDS:
            continue
        lat, lon = COORDS[sid]
        stations[sid] = {**d, 'lat': lat, 'lon': lon}
    mfc = compute_mfc_for_all(stations)
    for sid, val in sorted(mfc.items(), key=lambda kv: (kv[1] is None, kv[1] if kv[1] is not None else 0)):
        print(f'{sid}: MFC={val}')
