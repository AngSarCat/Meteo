"""
compute_kpis.py

Takes a decoded sounding profile (list[LevelObs] from temp_decoder.merged_profile,
pressure-descending, surface first) and computes the severe-weather KPIs shown
on the panel's "Mapa interactivo de KPIs" / "Indice de severidad compuesto" cards:

  SBCAPE, SBCIN, LCL_hPa, T500, deltaT_sfc_500, lapse_850_500, T850_T500,
  shear_0_3km, shear_0_6km, nivel_cong_m (freezing level), PWAT_mm,
  wind850_dir/ms, plus profile_p/profile_t/profile_td/parcel_trace arrays
  for the skew-T diagram.

Uses MetPy for the thermodynamics (parcel_profile, cape_cin, lcl, mixing
ratio / precipitable water) instead of hand-rolled physics, since MetPy's
implementations are unit-tested community code -- reserving the from-scratch
effort in this pipeline for the TTAA/TTBB decoder, where no ready-made
library exists.
"""
from __future__ import annotations
import numpy as np
import metpy.calc as mpcalc
from metpy.units import units


def _height_agl_interp(levels, target_hpa: float):
    """Interpolate a station-relative height (m) for a pressure that has no
    reported height, from the two bracketing mandatory levels that do."""
    with_h = [lv for lv in levels if lv.height_m is not None]
    if len(with_h) < 2:
        return None
    ps = [lv.pressure_hpa for lv in with_h]
    hs = [lv.height_m for lv in with_h]
    # np.interp needs increasing x; our levels are pressure-descending
    order = np.argsort(ps)
    ps_sorted = np.array(ps)[order]
    hs_sorted = np.array(hs)[order]
    if target_hpa < ps_sorted[0] or target_hpa > ps_sorted[-1]:
        return None
    return float(np.interp(target_hpa, ps_sorted, hs_sorted))


def compute_station_kpis(levels, station_name: str, lat: float, lon: float) -> dict | None:
    """
    levels: list[LevelObs] (temp_decoder.LevelObs), pressure-descending,
            already filtered to entries with temp_c set.
    Returns a dict matching the schema already used in index.html /
    mapa_kpis_prototipo.html's embedded 'temp' station records, or None if
    the profile is too sparse to compute anything meaningful (<4 levels).
    """
    if len(levels) < 4:
        return None

    p = np.array([lv.pressure_hpa for lv in levels])
    t = np.array([lv.temp_c for lv in levels])
    td = np.array([lv.dewpoint_c if lv.dewpoint_c is not None else lv.temp_c - 30 for lv in levels])

    # metpy needs strictly increasing height / decreasing pressure with no
    # duplicate pressures; our decoder already de-duplicates by pressure and
    # sorts descending, which is what metpy's sounding functions expect.
    p_q = p * units.hPa
    t_q = t * units.degC
    td_q = td * units.degC

    try:
        prof = mpcalc.parcel_profile(p_q, t_q[0], td_q[0]).to('degC')
        sbcape, sbcin = mpcalc.cape_cin(p_q, t_q, td_q, prof)
        sbcape = float(sbcape.to('J/kg').magnitude)
        sbcin = float(sbcin.to('J/kg').magnitude)
    except Exception:
        sbcape, sbcin = None, None
        prof = None

    try:
        lcl_p, lcl_t = mpcalc.lcl(p_q[0], t_q[0], td_q[0])
        lcl_hpa = float(lcl_p.to('hPa').magnitude)
    except Exception:
        lcl_hpa = None

    # T500 and deltaT/lapse rate 850-500
    t500 = None
    for lv in levels:
        if abs(lv.pressure_hpa - 500) < 1:
            t500 = lv.temp_c
            break
    if t500 is None and p.min() <= 500 <= p.max():
        t500 = float(np.interp(500, p[::-1], t[::-1]))

    t850 = None
    for lv in levels:
        if abs(lv.pressure_hpa - 850) < 1:
            t850 = lv.temp_c
            break
    if t850 is None and p.min() <= 850 <= p.max():
        t850 = float(np.interp(850, p[::-1], t[::-1]))

    delta_t_sfc_500 = (t[0] - t500) if t500 is not None else None
    t850_t500 = (t850 - t500) if (t850 is not None and t500 is not None) else None

    h850 = _height_agl_interp(levels, 850)
    h500 = _height_agl_interp(levels, 500)
    if h850 is not None and h500 is not None and h500 > h850:
        lapse_850_500 = (t850 - t500) / ((h500 - h850) / 1000.0)
    else:
        lapse_850_500 = None

    # wind shear 0-3km / 0-6km: need heights for wind-bearing levels
    winds = [(lv, _height_agl_interp(levels, lv.pressure_hpa) if lv.height_m is None else lv.height_m)
             for lv in levels if lv.wind_dir is not None and lv.wind_kt is not None]
    sfc_h = levels[0].height_m if levels[0].height_m is not None else 0.0
    sfc_wd, sfc_ws = None, None
    for lv in levels:
        if lv.wind_dir is not None:
            sfc_wd, sfc_ws = lv.wind_dir, lv.wind_kt
            break

    def _shear_to(top_km):
        if sfc_wd is None:
            return None
        target_h = sfc_h + top_km * 1000.0
        candidates = [(h, lv) for lv, h in winds if h is not None]
        if not candidates:
            return None
        candidates.sort(key=lambda c: abs(c[0] - target_h))
        lv_top, h_top = candidates[0][1], candidates[0][0]
        if abs(h_top - target_h) > 1500:  # no data anywhere near that height
            return None
        u0 = -sfc_ws * np.sin(np.radians(sfc_wd))
        v0 = -sfc_ws * np.cos(np.radians(sfc_wd))
        u1 = -lv_top.wind_kt * np.sin(np.radians(lv_top.wind_dir))
        v1 = -lv_top.wind_kt * np.cos(np.radians(lv_top.wind_dir))
        du, dv = (u1 - u0), (v1 - v0)
        return float(np.hypot(du, dv) * 0.5144)  # kt -> m/s

    shear_0_3km = _shear_to(3)
    shear_0_6km = _shear_to(6)

    # PWAT (precipitable water) via metpy, only where dewpoint is real (not
    # the -30C sentinel fallback used above for CAPE robustness)
    try:
        real_mask = np.array([lv.dewpoint_c is not None for lv in levels])
        if real_mask.sum() >= 2:
            pwat = mpcalc.precipitable_water(p_q[real_mask], td_q[real_mask])
            pwat_mm = float(pwat.to('mm').magnitude)
        else:
            pwat_mm = None
    except Exception:
        pwat_mm = None

    # freezing level (0C height), linear interp on the real profile
    nivel_cong_m = None
    for i in range(len(levels) - 1):
        t_a, t_b = levels[i].temp_c, levels[i + 1].temp_c
        h_a = levels[i].height_m if levels[i].height_m is not None else _height_agl_interp(levels, levels[i].pressure_hpa)
        h_b = levels[i + 1].height_m if levels[i + 1].height_m is not None else _height_agl_interp(levels, levels[i + 1].pressure_hpa)
        if h_a is None or h_b is None:
            continue
        if (t_a - 0) * (t_b - 0) <= 0 and t_a != t_b:
            frac = (0 - t_a) / (t_b - t_a)
            nivel_cong_m = h_a + frac * (h_b - h_a)
            break

    wind850_dir, wind850_ms = None, None
    for lv in levels:
        if abs(lv.pressure_hpa - 850) < 1 and lv.wind_dir is not None:
            wind850_dir = lv.wind_dir
            wind850_ms = round(lv.wind_kt * 0.5144)
            break

    profile_p = [round(x, 1) for x in p.tolist()]
    profile_t = [round(x, 2) for x in t.tolist()]
    profile_td = [round(float(lv.dewpoint_c), 2) if lv.dewpoint_c is not None else None for lv in levels]
    parcel_trace = None
    if prof is not None:
        parcel_trace = [[round(pp, 1), round(tt, 2)] for pp, tt in
                         zip(p_q.to('hPa').magnitude.tolist(), prof.magnitude.tolist())]

    capped_no_lfc = sbcape is not None and sbcape < 1.0

    return {
        'name': station_name, 'lat': lat, 'lon': lon,
        'SBCAPE': None if sbcape is None else round(sbcape, 1),
        'SBCIN': None if sbcin is None else round(sbcin, 1),
        'LCL_hPa': None if lcl_hpa is None else round(lcl_hpa, 1),
        'T500': None if t500 is None else round(t500, 1),
        'deltaT_sfc_500': None if delta_t_sfc_500 is None else round(delta_t_sfc_500, 1),
        'lapse_850_500': None if lapse_850_500 is None else round(lapse_850_500, 2),
        'T850_T500': None if t850_t500 is None else round(t850_t500, 1),
        'shear_0_3km': None if shear_0_3km is None else round(shear_0_3km, 1),
        'shear_0_6km': None if shear_0_6km is None else round(shear_0_6km, 1),
        'nivel_cong_m': None if nivel_cong_m is None else round(nivel_cong_m),
        'PWAT_mm': None if pwat_mm is None else round(pwat_mm, 1),
        'capped_no_lfc': capped_no_lfc,
        'wind850_dir': wind850_dir,
        'wind850_ms': wind850_ms,
        'profile_p': profile_p,
        'profile_t': profile_t,
        'profile_td': profile_td,
        'parcel_trace': parcel_trace,
    }


if __name__ == '__main__':
    import sys
    sys.path.insert(0, '.')
    from temp_decoder import split_stations, parse_station_block, merged_profile
    path = sys.argv[1] if len(sys.argv) > 1 else 'raw_ttaa_20260726.txt'
    raw = open(path, encoding='utf-8').read()
    blocks = split_stations(raw)
    STATIONS = {
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
    for sid, (name, lat, lon) in STATIONS.items():
        if sid not in blocks:
            print(f'{name}: NO DATA')
            continue
        reports = parse_station_block(blocks[sid])
        if not reports:
            print(f'{name}: NO REPORTS')
            continue
        r = sorted(reports, key=lambda r: r.valid_time)[-1]  # most recent
        prof = merged_profile(r)
        kpis = compute_station_kpis(prof, name, lat, lon)
        if kpis is None:
            print(f'{name}: profile too sparse')
            continue
        print(f"{name} [{r.valid_time}]: SBCAPE={kpis['SBCAPE']} SBCIN={kpis['SBCIN']} "
              f"LCL={kpis['LCL_hPa']} T500={kpis['T500']} lapse850_500={kpis['lapse_850_500']} "
              f"shear6km={kpis['shear_0_6km']}m/s PWAT={kpis['PWAT_mm']}mm frz_lvl={kpis['nivel_cong_m']}m")
