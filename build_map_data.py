"""
build_map_data.py

Orchestrator: ties temp_decoder + compute_kpis + synop_decoder + mfc +
sst_data + severity_index together into the exact map_data.json payload
the panel's two HTML files embed (script id="kpimapDataJson" in index.html,
script id="mapDataJson" in mapa_kpis_prototipo.html use the same shape,
keyed 'temp_stations'/'mfc_stations'/'meta' as already used on the live
site -- see CONTEXT.md), plus a companion JSON with everything needed to
refresh the two other data-dependent bits of index.html that live outside
that JSON blob:
  - the severityStations summary (for the "Indice de severidad compuesto"
    card's lvlbar chips + body text, written by hand each day)
  - the 14 SYNOP-derived rows of the RIESGO DE INCENDIO card's fireStations
    array (Castellon, Almeria, Zaragoza, Albacete, Ceuta, Melilla, Lisboa/
    Geofisico, Faro, Perpignan, Montpellier, Marseille, Nice, Ajaccio,
    Bastia -- these happen to be 14 of the same 22 MFC/SYNOP stations).

Usage:
    python3 build_map_data.py raw_ttaa_YYYYMMDD.txt raw_synop_YYYYMMDD.txt \
        --out map_data.json --fire-out fire_synop_update.json
"""
from __future__ import annotations
import argparse
import json
import math

from temp_decoder import split_stations as split_ttaa, parse_station_block, merged_profile
from compute_kpis import compute_station_kpis
from synop_decoder import split_stations as split_synop, decode_station_latest
from mfc import compute_mfc_for_all
from sst_data import marine_fuel_for_station
from severity_index import severity_score

TEMP_STATIONS = {
    '08190': ('Barcelona (08190)', 41.297, 2.083),
    '08302': ('Palma/Son Bonet (08302)', 39.599, 2.703),
    '08430': ('Murcia (08430)', 37.775, -0.812),
    '07645': ('Nimes/Courbessac (07645)', 43.854, 4.416),
    '07761': ('Ajaccio (07761)', 41.923, 8.803),
    '60390': ('Argel/Dar El Beida (60390)', 36.691, 3.215),
    '08001': ('A Coruna (08001)', 43.366, -8.421),
    '08023': ('Santander (08023)', 43.491, -3.801),
    '08221': ('Madrid/Barajas (08221)', 40.467, -3.556),
    '08383': ('Huelva (08383)', 37.278, -6.912),
    '08536': ('Lisboa/Portela (08536)', 38.789, -9.135),
    '07510': ('Bordeaux/Merignac (07510)', 44.831, -0.691),
}

MFC_STATIONS = {
    '08184': ('Girona/Costa Brava (08184)', 41.901, 2.760),
    '08181': ('Barcelona/El Prat (08181)', 41.297, 2.083),
    '08175': ('Reus/Aeropuerto (08175)', 41.147, 1.167),
    '08286': ('Castellon-Almazora (08286)', 39.997, -0.054),
    '08284': ('Valencia/aeropuerto (08284)', 39.489, -0.481),
    '08359': ('Alicante (08359)', 38.282, -0.558),
    '08487': ('Almeria/aeropuerto (08487)', 36.844, -2.358),
    '08301': ('Palma de Mallorca (08301)', 39.553, 2.739),
    '08373': ('Ibiza/Es Codola (08373)', 38.873, 1.373),
    '08314': ('Menorca/Mahon (08314)', 39.862, 4.219),
    '08159': ('Zaragoza (08159)', 41.666, -1.042),
    '08279': ('Albacete (08279)', 38.949, -1.864),
    '60320': ('Ceuta (60320)', 35.900, -5.317),
    '60338': ('Melilla (60338)', 35.280, -2.956),
    '08535': ('Lisboa/Geofisico (08535)', 38.717, -9.150),
    '08554': ('Faro/aeropuerto (08554)', 37.014, -7.966),
    '07747': ('Perpignan (07747)', 42.740, 2.871),
    '07643': ('Montpellier (07643)', 43.576, 3.963),
    '07650': ('Marseille/Marignane (07650)', 43.439, 5.221),
    '07690': ('Nice (07690)', 43.658, 7.215),
    '07761': ('Ajaccio (07761)', 41.923, 8.803),
    '07790': ('Bastia (07790)', 42.552, 9.484),
}

# WMO ids of the 14 MFC/SYNOP stations that double as fireStations rows
FIRE_SYNOP_IDS = ['08286', '08487', '08159', '08279', '60320', '60338',
                   '08535', '08554', '07747', '07643', '07650', '07690', '07761', '07790']
FIRE_SYNOP_NAMES = {
    '08286': 'Castellón-Almazora (08286, SYNOP)',
    '08487': 'Almería/aeropuerto (08487, SYNOP)',
    '08159': 'Zaragoza (08159, SYNOP)',
    '08279': 'Albacete (08279, SYNOP)',
    '60320': 'Ceuta (60320, SYNOP)',
    '60338': 'Melilla (60338, SYNOP)',
    '08535': 'Lisboa/Geofísico (08535, SYNOP)',
    '08554': 'Faro/aeropuerto (08554, SYNOP)',
    '07747': 'Perpignan (07747, SYNOP)',
    '07643': 'Montpellier (07643, SYNOP)',
    '07650': 'Marseille/Marignane (07650, SYNOP)',
    '07690': 'Nice (07690, SYNOP)',
    '07761': 'Ajaccio (07761, SYNOP)',
    '07790': 'Bastia (07790, SYNOP)',
}


def _haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def relative_humidity(temp_c: float, dewpoint_c: float | None) -> float | None:
    if dewpoint_c is None:
        return None
    es_t = 6.112 * math.exp(17.62 * temp_c / (243.12 + temp_c))
    es_td = 6.112 * math.exp(17.62 * dewpoint_c / (243.12 + dewpoint_c))
    return round(100.0 * es_td / es_t)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('ttaa_file')
    ap.add_argument('synop_file')
    ap.add_argument('--out', default='map_data.json')
    ap.add_argument('--fire-out', default='fire_synop_update.json')
    ap.add_argument('--severity-out', default='severity_summary.json')
    args = ap.parse_args()

    raw_ttaa = open(args.ttaa_file, encoding='utf-8').read()
    raw_synop = open(args.synop_file, encoding='utf-8').read()

    ttaa_blocks = split_ttaa(raw_ttaa)
    synop_blocks = split_synop(raw_synop)

    # -- decode SYNOP network, compute MFC --
    synop_decoded = {}
    for sid in MFC_STATIONS:
        block = synop_blocks.get(sid)
        if not block:
            continue
        d = decode_station_latest(block)
        if d is None:
            continue
        name, lat, lon = MFC_STATIONS[sid]
        synop_decoded[sid] = {**d, 'lat': lat, 'lon': lon, 'name': name}
    mfc_values = compute_mfc_for_all(synop_decoded)

    mfc_stations_out = []
    for sid, s in synop_decoded.items():
        mfc_stations_out.append({
            'name': s['name'], 'lat': s['lat'], 'lon': s['lon'],
            'MFC': mfc_values.get(sid), 'temp_c': s['temp_c'], 'dewpoint_c': s.get('dewpoint_c'),
            'wind_dir': s.get('wind_dir_deg'), 'wind_ms': s.get('wind_speed_ms'),
            'valid_time': s['valid_time'],
        })

    # -- decode soundings, compute KPIs + severity per station --
    temp_stations_out = []
    severity_rows = []
    temp_times = {}
    for sid, (name, lat, lon) in TEMP_STATIONS.items():
        block = ttaa_blocks.get(sid)
        if not block:
            continue
        reports = parse_station_block(block)
        if not reports:
            continue
        r = sorted(reports, key=lambda rr: rr.valid_time)[-1]
        prof = merged_profile(r)
        kpis = compute_station_kpis(prof, name, lat, lon)
        if kpis is None:
            continue
        temp_times[name] = r.valid_time

        # nearest MFC/SYNOP station
        nearest_id, nearest_dist = None, None
        for msid, s in synop_decoded.items():
            d = _haversine_km(lat, lon, s['lat'], s['lon'])
            if nearest_dist is None or d < nearest_dist:
                nearest_id, nearest_dist = msid, d
        mfc_nearest = mfc_values.get(nearest_id) if nearest_id else None
        mfc_scaled = (mfc_nearest / 100.0) if mfc_nearest is not None else None  # back to raw s^-1-ish small unit used in severity formula

        sfc_wd = kpis.get('wind850_dir')  # fallback if no surface wind captured
        # prefer the lowest-level wind actually present in the profile
        low_wd, low_ws = None, None
        for lv in prof:
            if lv.wind_dir is not None:
                low_wd, low_ws = lv.wind_dir, lv.wind_kt * 0.5144
                break
        sst_c, sst_anom_c, combustible = marine_fuel_for_station(sid, low_wd, low_ws)

        score, cat = severity_score(
            kpis['SBCAPE'], kpis['shear_0_6km'], kpis['T850_T500'], kpis['SBCIN'],
            mfc_nearest, combustible,
        )

        kpis['severity_score'] = score
        kpis['severity_categoria'] = cat
        kpis['sst_c'] = sst_c
        kpis['sst_anom_c'] = sst_anom_c
        kpis['combustible_marino'] = combustible
        kpis['mfc_cercano'] = mfc_nearest
        kpis['mfc_estacion'] = synop_decoded[nearest_id]['name'] if nearest_id else None
        kpis['mfc_dist_km'] = round(nearest_dist) if nearest_dist is not None else None

        temp_stations_out.append(kpis)
        severity_rows.append({'name': name, 'score': score, 'categoria': cat,
                               'sbcape': kpis['SBCAPE'], 'sbcin': kpis['SBCIN'],
                               'shear_0_6km': kpis['shear_0_6km'], 'combustible_marino': combustible,
                               'mfc_cercano': mfc_nearest})

    meta = {
        'temp_times_by_station': temp_times,
        'synop_reference_time': max((s['valid_time'] for s in synop_decoded.values()), default=None),
        'generated_note': 'Generado por scripts/build_map_data.py (Ogimet TTAA/TTBB + SYNOP, fetch via navegador).',
    }
    map_data = {'temp_stations': temp_stations_out, 'mfc_stations': mfc_stations_out, 'meta': meta}
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(map_data, f, ensure_ascii=False, indent=0)

    # -- fireStations SYNOP rows (14 stations) --
    fire_rows = []
    for sid in FIRE_SYNOP_IDS:
        s = synop_decoded.get(sid)
        if not s:
            continue
        hr = relative_humidity(s['temp_c'], s.get('dewpoint_c'))
        wind_kmh = round((s.get('wind_speed_ms') or 0) * 3.6, 1)
        fire_rows.append({
            'id': sid, 'name': FIRE_SYNOP_NAMES[sid],
            't': round(s['temp_c'], 1), 'hr': hr, 'wind': wind_kmh,
        })
    with open(args.fire_out, 'w', encoding='utf-8') as f:
        json.dump(fire_rows, f, ensure_ascii=False, indent=1)

    severity_rows.sort(key=lambda r: -r['score'])
    with open(args.severity_out, 'w', encoding='utf-8') as f:
        json.dump(severity_rows, f, ensure_ascii=False, indent=1)

    print(f'Wrote {args.out}: {len(temp_stations_out)} temp stations, {len(mfc_stations_out)} mfc stations')
    print(f'Wrote {args.fire_out}: {len(fire_rows)} fire/SYNOP rows')
    print(f'Wrote {args.severity_out}: severity ranking')
    for r in severity_rows:
        print(f"  {r['name']}: {r['score']} ({r['categoria']}) CAPE={r['sbcape']} CIN={r['sbcin']} shear6={r['shear_0_6km']}")


if __name__ == '__main__':
    main()
