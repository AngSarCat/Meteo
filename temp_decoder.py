"""
temp_decoder.py

Decodes raw WMO TEMP (TTAA/TTBB/TTCC/TTDD) radiosonde bulletins, as returned
in plain text by Ogimet's display_sond.php ("TXT" format), into a clean
per-level atmospheric profile: pressure (hPa), height (m), temperature (C),
dewpoint (C), wind direction (deg) and wind speed (kt).

This is a from-scratch implementation of the WMO FM-35 TEMP code (no
external TTAA-decoding library exists on PyPI), written and validated by
hand-checking real Barcelona (08190) soundings from 2026-07-26 against
physically plausible values before being used in this pipeline. See
CONTEXT.md in the repo root for the data-source notes and known caveats.

Usage:
    blocks = split_stations(raw_text)          # {station_id: raw_text_block}
    reports = parse_station_block(block)        # list of dicts, one per YYGGGG timestamp
    profile = best_report(reports)               # merged/most-recent TTAA+TTBB profile

Only mandatory-level (TTAA/TTCC) data is used for the profile arrays that
feed CAPE/CIN (parcel theory needs a monotonic p/T/Td series with sensible
vertical resolution; TTBB significant levels are folded in too, sorted by
pressure, to improve resolution near the tropopause / inversions).
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field

MANDATORY_TTAA = [1000, 925, 850, 700, 500, 400, 300, 250, 200, 150, 100]
MANDATORY_TTCC = [70, 50, 30, 20, 10]

LEVEL_CODE_TTAA = {
    '00': 1000, '92': 925, '85': 850, '70': 700, '50': 500,
    '40': 400, '30': 300, '25': 250, '20': 200, '15': 150, '10': 100,
}
LEVEL_CODE_TTCC = {
    '70': 70, '50': 50, '30': 30, '20': 20, '10': 10,
}


def _temp_td(group: str):
    """Decode a 5-digit TTTDD group -> (temp_C, dewpoint_depression_C) or (None, None)."""
    if len(group) != 5 or '/' in group:
        return None, None
    ttt = int(group[0:3])
    dd = int(group[3:5])
    temp_c = ttt / 10.0
    if ttt % 10 % 2 == 1:  # tenths digit odd -> negative
        temp_c = -temp_c
    if dd <= 50:
        dep = dd / 10.0
    else:
        dep = dd - 50
    return temp_c, dep


def _wind(group: str):
    """Decode a 5-digit ddfff wind group -> (dir_deg, speed_kt) or (None, None)."""
    if len(group) != 5 or '/' in group:
        return None, None
    val = int(group)
    ddd = val // 100
    ff = val % 100
    if ddd >= 500:
        ddd -= 500
        ff += 100
    if ddd > 360:
        return None, None
    return ddd, ff


def _height_from_code(level_hpa: int, code: str):
    """Decode the 3-digit height code that follows a TTAA/TTCC level indicator."""
    if '/' in code:
        return None
    val = int(code)
    if level_hpa == 1000:
        h = val - 500 if val >= 500 else val
        return float(-h) if val >= 500 else float(val)
    if level_hpa == 925:
        return float(val)
    if level_hpa == 850:
        return float(val + 1000)
    if level_hpa == 700:
        return float(val + 3000) if val < 500 else float(val + 2000)
    if level_hpa in (500, 400, 300):
        return float(val * 10)
    if level_hpa in (250, 200, 150, 100, 70, 50, 30, 20, 10):
        # heights expressed in decametres, >=1000 dam implied for these levels
        return float((val + 1000) * 10) if val < 1000 else float(val * 10)
    return None


def split_stations(raw_text: str) -> dict:
    """Split a multi-station Ogimet dump (our own '===STATION_xxx_START/END===' wrapper) into blocks."""
    blocks = {}
    for m in re.finditer(r'===STATION_(\w+)_START===(.*?)===STATION_\1_END===', raw_text, re.S):
        blocks[m.group(1)] = m.group(2)
    if blocks:
        return blocks
    # fallback: raw text is already a single station's Ogimet dump
    m = re.search(r'#\s*(\d{5}),', raw_text)
    sid = m.group(1) if m else 'UNKNOWN'
    return {sid: raw_text}


@dataclass
class LevelObs:
    pressure_hpa: float
    height_m: float | None = None
    temp_c: float | None = None
    dewpoint_c: float | None = None
    wind_dir: float | None = None
    wind_kt: float | None = None
    source: str = ''  # 'TTAA' | 'TTBB' | 'TTCC' | 'TTDD'


@dataclass
class SoundingReport:
    station_id: str
    valid_time: str  # 'YYYY-MM-DD HH:MM UTC'
    levels: list = field(default_factory=list)  # list[LevelObs], sorted desc by pressure


def _reassemble_groups(block_text: str) -> list:
    """
    Ogimet TXT dumps wrap each bulletin across several lines with leading
    whitespace; a bulletin ends with '=='. Reassemble each bulletin into one
    logical line of whitespace-separated groups, tagged with its header.
    Returns list of (yyyygggg:int, part:'TTAA'|'TTBB'|'TTCC'|'TTDD', station:str, groups:list[str])
    """
    out = []
    # bulletins are like: "202607261100 TTAA 26111 08190 99002 ... 46308 81100=="
    for bm in re.finditer(r'(\d{12})\s+(TTAA|TTBB|TTCC|TTDD)\s+(.*?)==', block_text, re.S):
        ts, part, body = bm.group(1), bm.group(2), bm.group(3)
        groups = body.split()
        out.append((ts, part, groups))
    return out


def _parse_ttaa_or_ttcc(groups: list, level_map: dict, is_ttcc: bool) -> list:
    """groups[0] = day/time/wind-indicator group, groups[1] = station id, rest = data groups."""
    levels = []
    i = 2  # skip YYGGId and IIiii
    n = len(groups)

    if not is_ttcc:
        # surface group: 99PPP
        if i < n and groups[i].startswith('99'):
            ppp = groups[i][2:5]
            if '/' not in ppp:
                pval = int(ppp)
                psfc = pval + 1000 if pval < 500 else float(pval)
                psfc = float(psfc)
            else:
                psfc = None
            i += 1
            t, td = (None, None)
            if psfc is not None and i < n:
                t, dep = _temp_td(groups[i])
                td = (t - dep) if (t is not None and dep is not None) else None
                i += 1
                wd, ws = (None, None)
                if i < n:
                    wd, ws = _wind(groups[i])
                    i += 1
                if psfc is not None:
                    levels.append(LevelObs(psfc, None, t, td, wd, ws, 'TTAA-sfc'))
        # 1000mb group is '00hhh'
        if i < n and groups[i].startswith('00') and len(groups[i]) == 5:
            code = groups[i][2:5]
            h = _height_from_code(1000, code)
            i += 1
            t = td = wd = ws = None
            if i < n and not re.match(r'^\d{2}(92|85|70|50|40|30|25|20|15|10)', groups[i]):
                tt, dep = _temp_td(groups[i])
                if tt is not None:
                    t = tt
                    td = (tt - dep) if dep is not None else None
                    i += 1
                    if i < n:
                        wd, ws = _wind(groups[i])
                        i += 1
            levels.append(LevelObs(1000, h, t, td, wd, ws, 'TTAA'))

    order = MANDATORY_TTCC if is_ttcc else MANDATORY_TTAA[1:]  # skip 1000 already handled
    lvl_prefix = {v: k for k, v in level_map.items()}

    while i < n:
        grp = groups[i]
        if len(grp) != 5:
            i += 1
            continue
        prefix = grp[0:2]
        if prefix not in level_map:
            # not a recognised mandatory-level indicator (e.g. 88=tropopause,
            # 77=max wind, 31313=regional section, wind-shear groups...) -> stop
            break
        level_hpa = level_map[prefix]
        code = grp[2:5]
        h = _height_from_code(level_hpa, code)
        i += 1
        t = td = wd = ws = None
        if i < n:
            tt, dep = _temp_td(groups[i])
            if tt is not None:
                t = tt
                td = (tt - dep) if dep is not None else None
            i += 1
        if i < n:
            wd, ws = _wind(groups[i])
            i += 1
        levels.append(LevelObs(level_hpa, h, t, td, wd, ws, 'TTCC' if is_ttcc else 'TTAA'))

    return levels


def _parse_ttbb_or_ttdd(groups: list) -> list:
    """Significant levels: repeating [PPnn (2-digit seq + 3-digit pressure)] [TTTDD] pairs."""
    levels = []
    i = 2  # skip time group + station id
    n = len(groups)
    while i + 1 < n:
        grp = groups[i]
        if len(grp) != 5:
            i += 1
            continue
        seq = grp[0:2]
        if grp == '21212' or grp == '31313':
            # '21212' marks start of the (unused here) wind section; '31313'
            # marks start of the national/regional data section -> stop.
            break
        if seq not in ('00', '11', '22', '33', '44', '55', '66', '77', '88', '99'):
            i += 1
            continue
        press_code = grp[2:5]
        if '/' in press_code:
            i += 2
            continue
        pval = int(press_code)
        if seq == '00':
            # station-level (surface) significant-level entry: same ambiguity
            # as the TTAA surface group -> values <500 mean 1000+val hPa.
            pressure = float(pval + 1000) if pval < 500 else float(pval)
        else:
            # all other significant levels are strictly below station level,
            # so the 3-digit code is always a direct hPa read (a genuine
            # high-altitude point like 91 hPa is coded "091" and stays 91,
            # it is never ambiguous with 1091 hPa).
            pressure = float(pval)
        i += 1
        t = td = None
        if i < n:
            tt, dep = _temp_td(groups[i])
            if tt is not None:
                t = tt
                td = (tt - dep) if dep is not None else None
            i += 1
        if t is not None:
            levels.append(LevelObs(pressure, None, t, td, None, None, 'TTBB'))
    return levels


def parse_station_block(block_text: str) -> list:
    """Return list[SoundingReport], one per distinct YYGGGG timestamp found in the block."""
    bulletins = _reassemble_groups(block_text)
    by_time = {}
    for ts, part, groups in bulletins:
        by_time.setdefault(ts, {})[part] = groups

    reports = []
    for ts, parts in sorted(by_time.items()):
        station_id = None
        levels = []
        if 'TTAA' in parts:
            station_id = parts['TTAA'][1]
            levels += _parse_ttaa_or_ttcc(parts['TTAA'], LEVEL_CODE_TTAA, is_ttcc=False)
        if 'TTCC' in parts:
            if station_id is None:
                station_id = parts['TTCC'][1]
            levels += _parse_ttaa_or_ttcc(parts['TTCC'], LEVEL_CODE_TTCC, is_ttcc=True)
        if 'TTBB' in parts:
            if station_id is None:
                station_id = parts['TTBB'][1]
            levels += _parse_ttbb_or_ttdd(parts['TTBB'])
        # NOTE: TTDD (significant levels below 100 hPa, i.e. above ~16km) is
        # intentionally NOT parsed. It contributes nothing to CAPE/CIN/shear/
        # PWAT (all bounded well below 100 hPa) and its group structure is
        # more failure-prone to reassemble reliably than the payoff justifies.
        if not levels:
            continue
        yyyy, mm, dd, hh = ts[0:4], ts[4:6], ts[6:8], ts[8:10]
        valid_time = f'{yyyy}-{mm}-{dd} {hh}:00 UTC'
        reports.append(SoundingReport(station_id, valid_time, levels))
    return reports


def merged_profile(report: SoundingReport):
    """
    Merge TTAA(+TTCC) mandatory levels with TTBB significant levels into one
    pressure-sorted profile (highest pressure/surface first), de-duplicating
    by pressure and preferring TTAA temp/dewpoint (has height) over TTBB
    duplicates at the same pressure.
    """
    by_p = {}
    for lv in report.levels:
        if lv.temp_c is None:
            continue
        # sanity bounds: keep only the troposphere/lower stratosphere range
        # actually used downstream (CAPE/CIN/shear/PWAT never need <100 hPa,
        # give a little headroom); reject physically impossible T/Td pairs
        # that would indicate a mis-parsed group.
        if not (90.0 <= lv.pressure_hpa <= 1084.0):
            continue
        if lv.dewpoint_c is not None and lv.dewpoint_c > lv.temp_c + 0.5:
            continue
        if not (-95.0 <= lv.temp_c <= 50.0):
            continue
        key = round(lv.pressure_hpa, 1)
        if key not in by_p or (by_p[key].height_m is None and lv.height_m is not None):
            by_p[key] = lv
        elif lv.source.startswith('TTAA') and not by_p[key].source.startswith('TTAA'):
            by_p[key] = lv
    levels = sorted(by_p.values(), key=lambda l: -l.pressure_hpa)
    return levels


if __name__ == '__main__':
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else '/sessions/confident-happy-cori/mnt/outputs/raw_ttaa_20260726.txt'
    raw = open(path, encoding='utf-8').read()
    blocks = split_stations(raw)
    for sid, block in blocks.items():
        reports = parse_station_block(block)
        print(f'== {sid}: {len(reports)} report(s) ==')
        for r in reports:
            prof = merged_profile(r)
            print(f'  {r.valid_time}: {len(prof)} levels, '
                  f'{prof[0].pressure_hpa if prof else "?"}hPa .. {prof[-1].pressure_hpa if prof else "?"}hPa')
