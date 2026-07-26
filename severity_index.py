"""
severity_index.py

Composite severe-weather severity score (0-100) per sounding station,
implementing the exact formula documented in the "Indice de severidad
compuesto" card's own "QUE MIDE" paragraph in index.html:

  "Combina ... la energia convectiva disponible (CAPE), la cizalla 0-6km y
  el gradiente termico 850-500hPa -- multiplicados por un factor que decae
  si el CIN tapa la columna (e^-|CIN|/150, no un recorte lineal) -- mas un
  termino de superficie ... la convergencia de humedad (MFC) de la estacion
  SYNOP mas cercana, y un 'combustible marino' (anomalia de temperatura del
  mar de hoy x cuanto sopla el viento hacia la costa en esa estacion)."

This module only implements the published formula; it does not re-derive
it, and should be kept in sync with that paragraph if the wording there
ever changes.
"""
from __future__ import annotations
import math


def cin_release_factor(cin_j_kg: float | None) -> float:
    if cin_j_kg is None:
        return 1.0
    return math.exp(-abs(cin_j_kg) / 150.0)


def severity_score(sbcape: float | None, shear_0_6km_ms: float | None,
                    t850_t500: float | None, sbcin: float | None,
                    mfc_1e5: float | None, combustible_marino: float | None) -> tuple[float, str]:
    """
    Returns (score_0_100, category). Weighting/normalisation choices:
      - CAPE term: cape/60 capped at 60 (i.e. CAPE>=3600 J/kg maxes this term)
      - shear term: shear_ms * 1.2 capped at 30
      - T850-T500 term: (grad-20)*2.5 capped at 25 (20C=~climatological floor)
      - all three summed, then multiplied by the CIN release factor
      - + surface term: mfc*8 (clipped +-12) + combustible_marino*2 (clipped +-8)
      - clipped to [0, 100]
    These normalisation constants reproduce the same 0-100 scale and the
    same qualitative station ranking documented in the card (Palma/Baleares
    extreme in a strong marine-heatwave onshore-flow setup, capped/CIN-heavy
    stations like Murcia scored low) -- see CONTEXT.md for the worked
    example this was calibrated against.
    """
    cape_term = min((sbcape or 0) / 60.0, 60.0)
    shear_term = min((shear_0_6km_ms or 0) * 1.2, 30.0)
    grad_term = min(max(((t850_t500 or 20) - 20) * 2.5, 0.0), 25.0)
    release = cin_release_factor(sbcin)
    core = (cape_term + shear_term + grad_term) * release

    surface = 0.0
    if mfc_1e5 is not None:
        surface += max(-12.0, min(12.0, mfc_1e5 * 8.0))
    if combustible_marino is not None:
        surface += max(-8.0, min(8.0, combustible_marino * 2.0))

    score = max(0.0, min(100.0, core + surface))

    if score >= 75:
        cat = 'Extremo'
    elif score >= 50:
        cat = 'Alto'
    elif score >= 25:
        cat = 'Moderado'
    else:
        cat = 'Bajo'
    return round(score, 1), cat


if __name__ == '__main__':
    # sanity check against the documented Palma example: CAPE 5390, shear 32,
    # CIN~0, high combustible marino -> should land "extremo" (>=75)
    s, c = severity_score(5390, 32, 30, 0, 0.1, 3.0)
    print(f'Palma-like: {s} ({c})')
    s, c = severity_score(3885, 15, 25, -2192, 0.0, 0.0)
    print(f'Murcia-like (heavily capped): {s} ({c})')
