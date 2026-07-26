"""
synop_decoder.py

Thin wrapper around the `pymetdecoder` library (PyPI, BAS/antarctica-maintained,
unit-tested) to decode our own '===STATION_xxx_START===' wrapped dumps of raw
AAXX SYNOP bulletins (as fetched from Ogimet's display_synops.php, fmt=txt)
into simple per-station dicts: temp_c, dewpoint_c, pressure_hpa (station
level), wind_dir_deg, wind_speed_ms.

We deliberately reuse pymetdecoder instead of hand-rolling SYNOP decoding --
unlike TTAA/TTBB, a solid maintained SYNOP decoder already exists on PyPI.
"""
from __future__ import annotations
import re
from pymetdecoder import synop as pmd_synop


def split_stations(raw_text: str) -> dict:
    blocks = {}
    for m in re.finditer(r'===STATION_(\w+)_START===(.*?)===STATION_\1_END===', raw_text, re.S):
        blocks[m.group(1)] = m.group(2).strip()
    return blocks


def _reassemble_bulletins(block_text: str) -> list:
    """Each bulletin: '<12-digit ts> <station> AAXX ... ==' possibly wrapped
    over several lines. Returns list of (ts, raw_synop_text_without_ts_prefix)."""
    out = []
    for bm in re.finditer(r'(\d{12})\s+(\d{5})\s+(AAXX.*?)(?:==|\n\n|\Z)', block_text, re.S):
        ts, station, body = bm.group(1), bm.group(2), bm.group(3)
        out.append((ts, body.strip()))
    return out


def decode_station_latest(block_text: str) -> dict | None:
    """Decode the most recent bulletin in a station's block. Returns a dict
    with temp_c, dewpoint_c, pressure_hpa, wind_dir_deg, wind_speed_ms,
    valid_time -- or None if nothing usable decoded."""
    bulletins = _reassemble_bulletins(block_text)
    if not bulletins:
        return None
    bulletins.sort(key=lambda b: b[0])
    for ts, body in reversed(bulletins):  # try most recent first, fall back older
        decoded = None
        try:
            decoded = pmd_synop.SYNOP().decode(body)
        except Exception:
            # Some national/regional section-3 groups (radiation, evaporation
            # codes etc.) aren't in pymetdecoder's table set and abort the
            # whole decode. We only need section 0/1 (temp/dewpoint/pressure/
            # wind), so retry with everything from '333' onward stripped.
            main_section = re.split(r'\s333\b', body)[0]
            try:
                decoded = pmd_synop.SYNOP().decode(main_section)
            except Exception:
                continue
        if decoded is None:
            continue
        t = decoded.get('air_temperature', {}).get('value') if decoded.get('air_temperature') else None
        td = decoded.get('dewpoint_temperature', {}).get('value') if decoded.get('dewpoint_temperature') else None
        p = None
        if decoded.get('station_pressure'):
            p = decoded['station_pressure'].get('value')
        elif decoded.get('sea_level_pressure'):
            p = decoded['sea_level_pressure'].get('value')
        wd = ws = None
        sw = decoded.get('surface_wind')
        if sw:
            if sw.get('direction') and not sw['direction'].get('calm') and not sw['direction'].get('varAllUnknown'):
                wd = sw['direction'].get('value')
            ws = sw.get('speed', {}).get('value') if sw.get('speed') else None
            if wd == 0 and ws == 0:
                wd = None  # calm, direction not meaningful
        if t is None:
            continue
        yyyy, mm, dd, hh = ts[0:4], ts[4:6], ts[6:8], ts[8:10]
        return {
            'temp_c': t, 'dewpoint_c': td, 'pressure_hpa': p,
            'wind_dir_deg': wd, 'wind_speed_ms': ws,
            'valid_time': f'{yyyy}-{mm}-{dd} {hh}:00 UTC',
        }
    return None


if __name__ == '__main__':
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else 'raw_synop_20260726.txt'
    raw = open(path, encoding='utf-8').read()
    blocks = split_stations(raw)
    for sid, block in blocks.items():
        r = decode_station_latest(block)
        if r is None:
            print(f'{sid}: NO DATA')
        else:
            print(f"{sid} [{r['valid_time']}]: T={r['temp_c']}C Td={r['dewpoint_c']}C "
                  f"P={r['pressure_hpa']}hPa wind={r['wind_dir_deg']}/{r['wind_speed_ms']}m/s")
