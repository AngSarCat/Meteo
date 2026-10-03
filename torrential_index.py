"""
torrential_index.py

Indice de riesgo de lluvia torrencial por convergencia (distinto del indice
de severidad compuesta de severity_index.py, que mide inestabilidad
convectiva clasica CAPE/cizalla). Este indice captura el mecanismo de
lluvia persistente/torrencial por convergencia de humedad en una capa
profunda ya saturada -- el patron tipico de una DANA -- que puede dar
lluvias extremas con CAPE bajo (ver nota de Barcelona, 2026-10-03).

Componentes (cada uno normalizado 0-100 antes de combinar):
  - PWAT (agua precipitable, mm): mas agua disponible en la columna =
    mas lluvia potencial. Rango de normalizacion 15-55 mm.
  - MFC (convergencia de flujo de humedad en superficie, estacion SYNOP
    mas cercana): a mas convergencia, mas alimentacion de humedad hacia
    el nucleo de precipitacion. Rango de normalizacion -0.02 a 0.10.
  - Profundidad de la capa saturada (hPa, contigua desde la superficie
    hacia arriba, |T-Td|<=1 C): una columna saturada en una capa profunda
    es la firma de ascenso sinoptico sostenido (lluvia estratiforme
    persistente), no de convencion diurna aislada. Rango 0-600 hPa.
  - Bono de viento en niveles bajos (850 hPa) de componente favorable al
    transporte de humedad hacia la costa (sector ENE-S, 45-200 grados):
    hasta 10 puntos adicionales, escalado por la velocidad (0-15 m/s).

Formula: score = 0.35*PWAT_norm + 0.30*MFC_norm + 0.25*profundidad_norm
                 + bono_viento (0-10)
         categoria: <25 Bajo, 25-50 Moderado, 50-75 Alto, >=75 Extremo

Limitaciones conocidas (documentar en el texto del dashboard):
  - MFC se toma de la estacion SYNOP superficial mas cercana al sondeo,
    no es un perfil vertical de convergencia.
  - La "profundidad de capa saturada" depende de que el sondeo reporte
    depresion del punto de rocio en los niveles estandar FM-35; un sondeo
    con huecos de datos puede subestimarla.
  - No sustituye al QPF oficial (AEMET/Meteocat) ni a radar/satelite.
"""
from __future__ import annotations


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def saturated_layer_depth_hpa(profile_p, profile_t, profile_td) -> float:
    """Espesor (hPa) de la capa saturada contigua desde la superficie."""
    if not profile_p or not profile_t or not profile_td:
        return 0.0
    surface_p = profile_p[0]
    top_p = profile_p[0]
    for p, t, td in zip(profile_p, profile_t, profile_td):
        if t is None or td is None:
            break
        if abs(t - td) <= 1.0:
            top_p = p
        else:
            break
    return max(0.0, surface_p - top_p)


def _onshore_wind_bonus(wind_dir_deg, wind_speed_ms) -> float:
    if wind_dir_deg is None or wind_speed_ms is None:
        return 0.0
    if 45 <= wind_dir_deg <= 200:
        return _clamp(wind_speed_ms / 15.0, 0, 1) * 10.0
    return 0.0


def torrential_score(pwat_mm, mfc, profile_p, profile_t, profile_td,
                      wind850_dir=None, wind850_ms=None):
    """
    Devuelve (score 0-100, categoria, detalle dict) a partir de los
    mismos insumos ya calculados por compute_kpis.py / mfc.py para cada
    estacion de sondeo TEMP.
    """
    pwat = pwat_mm or 0.0
    mfc_v = mfc if mfc is not None else 0.0
    depth = saturated_layer_depth_hpa(profile_p, profile_t, profile_td)

    pwat_norm = _clamp((pwat - 15.0) / (55.0 - 15.0) * 100.0)
    mfc_norm = _clamp((mfc_v - (-0.02)) / (0.10 - (-0.02)) * 100.0)
    depth_norm = _clamp(depth / 600.0 * 100.0)
    bonus = _onshore_wind_bonus(wind850_dir, wind850_ms)

    score = _clamp(0.35 * pwat_norm + 0.30 * mfc_norm + 0.25 * depth_norm + bonus)

    if score >= 75:
        categoria = 'Extremo'
    elif score >= 50:
        categoria = 'Alto'
    elif score >= 25:
        categoria = 'Moderado'
    else:
        categoria = 'Bajo'

    detalle = {
        'pwat_mm': pwat,
        'mfc': mfc_v,
        'sat_depth_hpa': round(depth, 0),
        'wind850_dir': wind850_dir,
        'wind850_ms': wind850_ms,
        'pwat_norm': round(pwat_norm, 1),
        'mfc_norm': round(mfc_norm, 1),
        'depth_norm': round(depth_norm, 1),
        'wind_bonus': round(bonus, 1),
    }
    return round(score, 1), categoria, detalle
