"""
compute_kpis.py

Takes a decoded sounding profile (list[LevelObs] from temp_decoder.merged_profile,
pressure-descending, surface first) and computes the severe-weather KPIs shown
on the panel's "Mapa interactivo de KPIs" / "Indice de severidad compuesto" cards.

Base set (existing): SBCAPE, SBCIN, LCL_hPa, T500, deltaT_sfc_500, lapse_850_500,
T850_T500, shear_0_3km, shear_0_6km, nivel_cong_m (freezing level), PWAT_mm,
wind850_dir/ms, plus profile_p/profile_t/profile_td/parcel_trace arrays for the
skew-T diagram.

Extended set (added 06/08/2026, after reviewing RAOB's Sounding Indices manual
section, see CONTEXT.md): K, TT, CT, VT, LI, SI (Showalter), Boyden, VGP, Tc/CCL,
Haines Index, SWEAT, plus a full wind_profile (height/dir/speed at every mandatory
level with wind data) for the new hodograph panel, storm motion (Bunkers method,
right-mover), SRH 0-1/0-2/0-3km, EHI, BRN, and SCP/STP approximations.

Uses MetPy for the thermodynamics AND for most of the classic indices (K, TT, CT,
VT, SWEAT, Showalter, LI, CCL, Bunkers storm motion, storm-relative helicity,
supercell composite) since MetPy ships tested implementations of all of these --
reserving hand-rolled formulas for the handful RAOB documents that MetPy doesn't
provide (Boyden, VGP, Haines, EHI, BRN, STP), which are implemented directly from
the formulas in RAOB70UserManual.pdf section 15.

CAVEAT (important, carried through to the UI): our TTAA/TTBB decoder only reports
mandatory levels (+ some TTBB significant levels), not a continuous high-resolution
profile. Indices that integrate over a wind/height layer (SRH, Bunkers storm motion,
BRN, EHI, SCP, STP) are therefore coarser than what a real forecasting workstation
like RAOB computes from the full-resolution sounding, especially in the lowest 1-3 km
where our only points are typically the surface and 850 hPa (~1.2-1.5 km). Treat
these five as directional/approximate, not precise.
"""
from __future__ import annotations
import math
import numpy as np
import metpy.calc as mpcalc
from metpy.units import units


# Approximate station elevations (m AGL reference for the sounding site itself,
# not necessarily the same as the co-located airport's METAR elevation). Used
# only for the Haines Index elevation-tier lookup (15.16 in the RAOB manual).
# Source: WMO station metadata (public), rounded to the nearest metre.
STATION_ELEV_M = {
    'Barcelona (08190)': 4,
    'Palma/Son Bonet (08302)': 9,
    'Murcia (08430)': 4,
    'Nimes/Courbessac (07645)': 59,
    'Ajaccio (07761)': 5,
    'Argel/Dar El Beida (60390)': 25,
    'A Coruna (08001)': 58,
    'Santander (08023)': 5,
    'Madrid/Barajas (08221)': 609,
    'Huelva (08383)': 19,
    'Lisboa/Portela (08536)': 104,
    'Bordeaux/Merignac (07510)': 47,
}


def _height_agl_interp(levels, target_hpa: float):
    """Interpolate a station-relative height (m) for a pressure that has no
    reported height, from the two bracketing mandatory levels that do."""
    with_h = [lv for lv in levels if lv.height_m is not None]
    if len(with_h) < 2:
        return None
    ps = [lv.pressure_hpa for lv in with_h]
    hs = [lv.height_m for lv in with_h]
    order = np.argsort(ps)
    ps_sorted = np.array(ps)[order]
    hs_sorted = np.array(hs)[order]
    if target_hpa < ps_sorted[0] or target_hpa > ps_sorted[-1]:
        return None
    return float(np.interp(target_hpa, ps_sorted, hs_sorted))


def _lookup(levels, target_hpa, attr, p_arr=None, v_arr=None):
    """Exact match within 1 hPa, else linear interpolation on (p, attr) pairs."""
    for lv in levels:
        if abs(lv.pressure_hpa - target_hpa) < 1:
            val = getattr(lv, attr)
            if val is not None:
                return val
    if p_arr is None:
        pairs = [(lv.pressure_hpa, getattr(lv, attr)) for lv in levels if getattr(lv, attr) is not None]
        if len(pairs) < 2:
            return None
        p_arr = np.array([p for p, _ in pairs])
        v_arr = np.array([v for _, v in pairs])
    order = np.argsort(p_arr)
    ps, vs = p_arr[order], v_arr[order]
    if target_hpa < ps[0] or target_hpa > ps[-1]:
        return None
    return float(np.interp(target_hpa, ps, vs))


def _wind_uv(wind_dir_deg, wind_kt):
    """Meteorological wind (blowing FROM dir) -> (u, v) in m/s."""
    ws_ms = wind_kt * 0.5144
    u = -ws_ms * math.sin(math.radians(wind_dir_deg))
    v = -ws_ms * math.cos(math.radians(wind_dir_deg))
    return u, v


def _haines_index(t_low, td_low_or_dep, t_mid_or_high, dep_mid_or_high, tier):
    """
    Generic 2-term Haines Index (15.16): stability term (1-3) + moisture term (1-3),
    tier is 'low' | 'mid' | 'high' selecting the RAOB threshold table.
    For 'low': stability = T950-T850, moisture = 850 dewpoint depression.
    For 'mid': stability = T850-T700, moisture = 850 dewpoint depression.
    For 'high': stability = T700-T500, moisture = 700 dewpoint depression.
    """
    thresholds = {
        'low':  ((3, 7), (5, 9)),
        'mid':  ((5, 10), (5, 12)),
        'high': ((17, 21), (14, 20)),
    }
    (s_lo, s_hi), (m_lo, m_hi) = thresholds[tier]
    stab = t_low
    if stab <= s_lo:
        s_term = 1
    elif stab <= s_hi:
        s_term = 2
    else:
        s_term = 3
    dep = td_low_or_dep
    if dep <= m_lo:
        m_term = 1
    elif dep <= m_hi:
        m_term = 2
    else:
        m_term = 3
    return s_term + m_term


def compute_station_kpis(levels, station_name: str, lat: float, lon: float) -> dict | None:
    if len(levels) < 4:
        return None

    p = np.array([lv.pressure_hpa for lv in levels])
    t = np.array([lv.temp_c for lv in levels])
    td_real = np.array([lv.dewpoint_c if lv.dewpoint_c is not None else np.nan for lv in levels])
    td = np.array([lv.dewpoint_c if lv.dewpoint_c is not None else lv.temp_c - 30 for lv in levels])

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

    t500 = _lookup(levels, 500, 'temp_c')
    t850 = _lookup(levels, 850, 'temp_c')
    t700 = _lookup(levels, 700, 'temp_c')
    td850 = _lookup(levels, 850, 'dewpoint_c')
    td700 = _lookup(levels, 700, 'dewpoint_c')

    delta_t_sfc_500 = (t[0] - t500) if t500 is not None else None
    t850_t500 = (t850 - t500) if (t850 is not None and t500 is not None) else None

    h850 = _height_agl_interp(levels, 850)
    h500 = _height_agl_interp(levels, 500)
    if h850 is not None and h500 is not None and h500 > h850:
        lapse_850_500 = (t850 - t500) / ((h500 - h850) / 1000.0)
    else:
        lapse_850_500 = None

    # --- wind profile: every level with both dir+speed, with a resolved AGL height ---
    wind_profile = []
    for lv in levels:
        if lv.wind_dir is None or lv.wind_kt is None:
            continue
        h = lv.height_m if lv.height_m is not None else _height_agl_interp(levels, lv.pressure_hpa)
        if h is None and lv is levels[0]:
            h = 0.0
        if h is None:
            continue
        wind_profile.append({'p': lv.pressure_hpa, 'h_m': round(h), 'dir': lv.wind_dir,
                              'speed_kt': lv.wind_kt, 'speed_ms': round(lv.wind_kt * 0.5144, 1)})
    wind_profile.sort(key=lambda w: -w['p'])

    sfc_h = levels[0].height_m if levels[0].height_m is not None else (wind_profile[0]['h_m'] if wind_profile else 0.0)
    sfc_wd, sfc_ws = None, None
    for lv in levels:
        if lv.wind_dir is not None:
            sfc_wd, sfc_ws = lv.wind_dir, lv.wind_kt
            break

    def _shear_to(top_km):
        if sfc_wd is None or not wind_profile:
            return None
        target_h = sfc_h + top_km * 1000.0
        cands = sorted(wind_profile, key=lambda w: abs(w['h_m'] - target_h))
        top = cands[0]
        if abs(top['h_m'] - target_h) > 1500:
            return None
        u0, v0 = _wind_uv(sfc_wd, sfc_ws)
        u1, v1 = _wind_uv(top['dir'], top['speed_kt'])
        return float(np.hypot(u1 - u0, v1 - v0))

    shear_0_3km = _shear_to(3)
    shear_0_6km = _shear_to(6)

    try:
        real_mask = ~np.isnan(td_real)
        if real_mask.sum() >= 2:
            pwat = mpcalc.precipitable_water(p_q[real_mask], td_q[real_mask])
            pwat_mm = float(pwat.to('mm').magnitude)
        else:
            pwat_mm = None
    except Exception:
        pwat_mm = None

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

    # ================= EXTENDED INDICES (added 06/08/2026) =================

    # --- K / TT / CT / VT / SWEAT / SI / LI / CCL-Tc: all via MetPy on the
    #     real-dewpoint-masked profile (these formulas are undefined with the
    #     -30C CAPE sentinel, and MetPy's helpers do their own level lookup) ---
    k_index = tt_index = ct_index = vt_index = sweat = si = li = None
    tc_c = ccl_hpa = None
    try:
        real_mask = ~np.isnan(td_real)
        if real_mask.sum() >= 3:
            p_r = p_q[real_mask]
            t_r = t_q[real_mask]
            td_r = td_q[real_mask]
            k_index = float(mpcalc.k_index(p_r, t_r, td_r).magnitude)
            tt_index = float(mpcalc.total_totals_index(p_r, t_r, td_r).magnitude)
            ct_index = float(mpcalc.cross_totals(p_r, t_r, td_r).magnitude)
            vt_index = float(mpcalc.vertical_totals(p_r, t_r).magnitude)
            si = float(np.atleast_1d(mpcalc.showalter_index(p_r, t_r, td_r).magnitude)[0])
            try:
                ccl_p, ccl_t, tc = mpcalc.ccl(p_r, t_r, td_r)
                ccl_hpa = float(ccl_p.to('hPa').magnitude)
                tc_c = float(tc.to('degC').magnitude)
            except Exception:
                pass
            wp = [w for w in wind_profile]
            wp_ps = [w['p'] for w in wp]
            # SWEAT needs real wind AND dewpoint data bracketing both 850 and
            # 500 hPa; with only surface wind reported (happens on ~2/12
            # stations on a given day) the interpolation would run out of
            # bounds, so skip it rather than extrapolate nonsense.
            if len(wp) >= 3 and max(wp_ps) >= 850 and min(wp_ps) <= 500 and td850 is not None:
                p_w = np.array(wp_ps) * units.hPa
                spd_w = np.array([w['speed_kt'] for w in wp]) * units.knots
                dir_w = np.array([w['dir'] for w in wp]) * units.degrees
                try:
                    t_w = np.interp(p_w.magnitude, p[::-1], t[::-1]) * units.degC
                    td_w = np.array([_lookup(levels, pp, 'dewpoint_c') or -30 for pp in p_w.magnitude]) * units.degC
                    sweat_val = mpcalc.sweat_index(p_w, t_w, td_w, spd_w, dir_w).magnitude
                    sweat_val = float(np.atleast_1d(sweat_val)[0])
                    sweat = sweat_val if not math.isnan(sweat_val) else None
                except Exception:
                    sweat = None
    except Exception:
        pass

    if prof is not None and t500 is not None:
        try:
            parcel_t500 = float(np.interp(500, p[::-1], prof.magnitude[::-1]))
            li = round(t500 - parcel_t500, 1)
        except Exception:
            li = None

    # --- Boyden Index (15.1): (1000-700mb thickness / 10) - T700 - 200/10 simplified
    #     to RAOB's stated form: Boyden = (h700-h1000)/10 - T700 - 20 (empirical const) ---
    boyden = None
    h1000 = _height_agl_interp(levels, 1000)
    if h1000 is None and abs(p[0] - 1000) < 15:
        h1000 = levels[0].height_m if levels[0].height_m is not None else 0.0
    if h1000 is not None and h500 is not None and t700 is not None:
        h700 = _height_agl_interp(levels, 700)
        if h700 is not None:
            thickness = h700 - h1000
            boyden = round(thickness / 10.0 - t700 - 200.0, 1)

    # --- VGP (15.44): S * sqrt(CAPE), S = mean 0-6km shear / 6 ---
    vgp = None
    if shear_0_6km is not None and sbcape is not None and sbcape > 0:
        vgp = round((shear_0_6km / 6.0) * math.sqrt(sbcape), 3)

    # --- Haines Index (15.16), elevation-tiered ---
    haines = None
    elev = STATION_ELEV_M.get(station_name)
    if elev is not None:
        try:
            if elev < 305:
                t950 = _lookup(levels, 950, 'temp_c')
                if t950 is not None and t850 is not None and td850 is not None:
                    dep850 = t850 - td850
                    haines = _haines_index(t950 - t850, dep850, None, None, 'low')
            elif elev < 914:
                if t850 is not None and t700 is not None and td850 is not None:
                    dep850 = t850 - td850
                    haines = _haines_index(t850 - t700, dep850, None, None, 'mid')
            else:
                if t700 is not None and t500 is not None and td700 is not None:
                    dep700 = t700 - td700
                    haines = _haines_index(t700 - t500, dep700, None, None, 'high')
        except Exception:
            haines = None

    # --- Storm motion (Bunkers right-mover) + SRH 0-1/0-2/0-3km + EHI + BRN + SCP/STP ---
    storm_motion = None
    srh_0_1km = srh_0_2km = srh_0_3km = None
    ehi = brn = scp = stp = None
    if len(wind_profile) >= 3:
        try:
            hs = np.array([w['h_m'] - sfc_h for w in wind_profile])
            order = np.argsort(hs)
            hs = hs[order]
            us = np.array([_wind_uv(wind_profile[i]['dir'], wind_profile[i]['speed_kt'])[0] for i in order])
            vs = np.array([_wind_uv(wind_profile[i]['dir'], wind_profile[i]['speed_kt'])[1] for i in order])
            ps_w = np.array([wind_profile[i]['p'] for i in order])
            # de-duplicate identical heights (metpy needs strictly increasing)
            _, uniq_idx = np.unique(hs, return_index=True)
            hs, us, vs, ps_w = hs[uniq_idx], us[uniq_idx], vs[uniq_idx], ps_w[uniq_idx]
            if len(hs) >= 3 and hs.max() >= 3000:
                h_q = hs * units.meter
                u_q = us * units('m/s')
                v_q = vs * units('m/s')
                p_wq = ps_w * units.hPa

                rm, lm, mean_w = mpcalc.bunkers_storm_motion(p_wq, u_q, v_q, h_q)
                storm_u, storm_v = float(rm[0].magnitude), float(rm[1].magnitude)
                storm_spd_ms = math.hypot(storm_u, storm_v)
                storm_dir = (math.degrees(math.atan2(-storm_u, -storm_v))) % 360
                storm_motion = {'dir': round(storm_dir), 'speed_ms': round(storm_spd_ms, 1),
                                 'speed_kt': round(storm_spd_ms / 0.5144)}

                def _srh(depth_km):
                    try:
                        val, *_ = mpcalc.storm_relative_helicity(
                            h_q, u_q, v_q, depth=depth_km * 1000 * units.meter,
                            storm_u=storm_u * units('m/s'), storm_v=storm_v * units('m/s'))
                        return float(val.magnitude)
                    except Exception:
                        return None

                srh_0_1km = _srh(1)
                srh_0_2km = _srh(2)
                srh_0_3km = _srh(3)

                if srh_0_2km is not None and sbcape is not None:
                    ehi = round((max(srh_0_2km, 0) * sbcape) / 160000.0, 2)

                # BRN: CAPE / (0.5 * |mean_wind_0-6km - mean_wind_0-500m|^2), simple
                # (non-density-weighted) layer means -- see module docstring caveat.
                def _mean_uv(top_m):
                    mask = hs <= top_m
                    if mask.sum() < 1:
                        return None
                    return float(np.mean(us[mask])), float(np.mean(vs[mask]))

                mean_low = _mean_uv(500)
                mean_deep = _mean_uv(6000)
                if mean_low is not None and mean_deep is not None and sbcape is not None and sbcape > 0:
                    brn_shr = math.hypot(mean_deep[0] - mean_low[0], mean_deep[1] - mean_low[1])
                    if brn_shr > 0.5:
                        brn = round(sbcape / (0.5 * brn_shr ** 2), 1)

                if srh_0_3km is not None and sbcape is not None and shear_0_6km is not None:
                    try:
                        scp_val = mpcalc.supercell_composite(
                            sbcape * units('J/kg'), max(srh_0_3km, 0) * units('m^2/s^2'),
                            shear_0_6km * units('m/s'))
                        scp = round(float(np.atleast_1d(scp_val.magnitude)[0]), 2)
                    except Exception:
                        scp = None

                # STP (fixed-layer, Thompson et al 2003), approximated with
                # SBCAPE/SBCIN standing in for mixed-layer values (see caveat).
                if (srh_0_1km is not None and shear_0_6km is not None and sbcape is not None
                        and lcl_hpa is not None and h500 is not None):
                    lcl_h_agl = _height_agl_interp(levels, lcl_hpa)
                    if lcl_h_agl is not None:
                        cape_term = sbcape / 1500.0
                        if lcl_h_agl < 1000:
                            lcl_term = 1.0
                        elif lcl_h_agl > 2000:
                            lcl_term = 0.0
                        else:
                            lcl_term = (2000 - lcl_h_agl) / 1000.0
                        srh_term = srh_0_1km / 150.0
                        if shear_0_6km < 12.5:
                            shr_term = 0.0
                        elif shear_0_6km > 30:
                            shr_term = 1.5
                        else:
                            shr_term = shear_0_6km / 20.0
                        if sbcin is None or sbcin > -50:
                            cin_term = 1.0
                        elif sbcin < -200:
                            cin_term = 0.0
                        else:
                            cin_term = (200 + sbcin) / 150.0
                        stp = round(max(cape_term, 0) * max(lcl_term, 0) * srh_term * max(shr_term, 0) * max(cin_term, 0), 2)
        except Exception:
            pass

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
        # --- extended (06/08/2026) ---
        'K_index': None if k_index is None else round(k_index, 1),
        'TT_index': None if tt_index is None else round(tt_index, 1),
        'CT_index': None if ct_index is None else round(ct_index, 1),
        'VT_index': None if vt_index is None else round(vt_index, 1),
        'LI': li,
        'SI': None if si is None else round(si, 1),
        'SWEAT': None if sweat is None else round(sweat, 1),
        'Boyden': boyden,
        'VGP': vgp,
        'Tc': None if tc_c is None else round(tc_c, 1),
        'CCL_hPa': None if ccl_hpa is None else round(ccl_hpa, 1),
        'Haines': haines,
        'storm_motion': storm_motion,
        'SRH_0_1km': None if srh_0_1km is None else round(srh_0_1km, 1),
        'SRH_0_2km': None if srh_0_2km is None else round(srh_0_2km, 1),
        'SRH_0_3km': None if srh_0_3km is None else round(srh_0_3km, 1),
        'EHI': ehi,
        'BRN': brn,
        'SCP': scp,
        'STP': stp,
        'wind_profile': wind_profile,
    }


if __name__ == '__main__':
    import sys
    sys.path.insert(0, '.')
    from temp_decoder import split_stations, parse_station_block, merged_profile
    path = sys.argv[1] if len(sys.argv) > 1 else 'raw_ttaa_20260806.txt'
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
        r = sorted(reports, key=lambda r: r.valid_time)[-1]
        prof = merged_profile(r)
        kpis = compute_station_kpis(prof, name, lat, lon)
        if kpis is None:
            print(f'{name}: profile too sparse')
            continue
        sm = kpis['storm_motion']
        sm_s = f"{sm['dir']}/{sm['speed_kt']}kt" if sm else 'n/a'
        print(f"{name}: SBCAPE={kpis['SBCAPE']} K={kpis['K_index']} TT={kpis['TT_index']} "
              f"LI={kpis['LI']} SI={kpis['SI']} SWEAT={kpis['SWEAT']} Boyden={kpis['Boyden']} "
              f"VGP={kpis['VGP']} Haines={kpis['Haines']} Tc={kpis['Tc']} CCL={kpis['CCL_hPa']} "
              f"storm={sm_s} SRH1={kpis['SRH_0_1km']} SRH3={kpis['SRH_0_3km']} EHI={kpis['EHI']} "
              f"BRN={kpis['BRN']} SCP={kpis['SCP']} STP={kpis['STP']}")
