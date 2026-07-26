"""
sst_data.py

Sea-surface-temperature context ("combustible marino") for each of the 12
sounding stations. There is no free, anonymous-fetch, per-point SST+anomaly
API (Copernicus Marine needs an account; NOAA OISST grids need parsing
NetCDF) that fits this pipeline's "browser fetch only, no credentials"
constraint, so -- exactly as the panel's "Ola de calor marina" card already
does by hand each day -- this module keeps a small table of regional SST /
anomaly reference values, one per sea sub-region, refreshed from the same
public sources used in that card (CEAM/MEDMOS, NOAA, Puertos del Estado,
tiempo.com). Update REGIONS below whenever that card's numbers change
noticeably; it does not need to be perfectly in sync day to day since
"combustible marino" is a coarse, secondary term in the severity index (see
severity_index.py), not the primary CAPE/shear signal.

combustible_marino = sst_anomaly_c * onshore_wind_component(station)
  where onshore_wind_component is how many m/s of the station's low-level
  wind blow from the sea towards the coast (0 if offshore or inland).
"""
from __future__ import annotations
import math

# (name, lat, lon, sst_c, sst_anom_c, onshore_wind_from_deg)
# onshore_wind_from_deg: the compass direction *the wind blows FROM* that
# counts as "coming off this sea" for that station (used to gate the
# onshore-component calc so an offshore wind doesn't get credited).
REGIONS = [
    {'name': 'W Mediterraneo - Baleares/Cataluna/C.Valenciana', 'sst_c': 29.5, 'sst_anom_c': 3.5,
     'stations': ['08190', '08302', '07645']},
    {'name': 'W Mediterraneo - Murcia/SE peninsular', 'sst_c': 28.5, 'sst_anom_c': 3.0,
     'stations': ['08430']},
    {'name': 'W Mediterraneo - Cerdeña/Corcega', 'sst_c': 27.5, 'sst_anom_c': 2.5,
     'stations': ['07761']},
    {'name': 'W Mediterraneo - Argelia', 'sst_c': 25.2, 'sst_anom_c': 0.7,
     'stations': ['60390']},
    {'name': 'Atlantico - Galicia/Cantabrico', 'sst_c': 19.7, 'sst_anom_c': 1.0,
     'stations': ['08001', '08023']},
    {'name': 'Atlantico - Golfo de Cadiz/Algarve', 'sst_c': 21.5, 'sst_anom_c': 1.2,
     'stations': ['08383', '08536']},
    {'name': 'Atlantico - Aquitania', 'sst_c': 20.5, 'sst_anom_c': 1.0,
     'stations': ['07510']},
]

_STATION_REGION = {sid: r for r in REGIONS for sid in r['stations']}

# stations with no direct sea exposure relevant to this table (inland)
_INLAND = {'08221'}


def onshore_component_ms(station_wind_dir_deg: float | None, station_wind_speed_ms: float | None,
                          coast_normal_from_deg: float) -> float:
    """How many m/s of the wind blow from the sea onto the coast, 0 if wind
    blows offshore or is calm/unknown. coast_normal_from_deg is the compass
    bearing the sea lies in, seen from the station (i.e. an onshore wind
    comes FROM roughly that bearing)."""
    if station_wind_dir_deg is None or station_wind_speed_ms is None:
        return 0.0
    diff = abs((station_wind_dir_deg - coast_normal_from_deg + 180) % 360 - 180)
    if diff > 90:
        return 0.0
    return station_wind_speed_ms * math.cos(math.radians(diff))


# rough "wind FROM the sea" bearing per station, for the onshore-component gate
_SEA_BEARING = {
    '08190': 130, '08302': 180, '07645': 150, '08430': 110, '07761': 200,
    '60390': 30, '08001': 290, '08023': 350, '08383': 200, '08536': 250,
    '07510': 260,
}


def marine_fuel_for_station(station_id: str, wind_dir_deg: float | None, wind_speed_ms: float | None):
    if station_id in _INLAND or station_id not in _STATION_REGION:
        return None, None, None
    region = _STATION_REGION[station_id]
    bearing = _SEA_BEARING.get(station_id, 180)
    onshore = onshore_component_ms(wind_dir_deg, wind_speed_ms, bearing)
    combustible = round(region['sst_anom_c'] * onshore, 2)
    return region['sst_c'], region['sst_anom_c'], combustible


if __name__ == '__main__':
    for sid in ['08190', '08302', '08430', '07645', '07761', '60390',
                '08001', '08023', '08221', '08383', '08536', '07510']:
        sst, anom, comb = marine_fuel_for_station(sid, 200, 8)
        print(f'{sid}: sst={sst} anom={anom} combustible(wind 200/8)={comb}')
