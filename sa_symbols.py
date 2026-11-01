#!/usr/bin/env python3
"""
sa_symbols.py - Analisis de volcados de simbolos de S.A. Signals Analyzer
(Phase Plane, casilla "Output Dem as N").

QUE HACE
    1. Lee el texto copiado de la ventana verde de salida de S.A. (uno o varios
       volcados concatenados) y extrae la tabla de codificacion y la cadena Data:.
    2. Cuenta la frecuencia de cada valor (histograma de simbolos).
    3. Busca tramos de sincronismo: tramos largos en que solo aparecen dos valores
       opuestos (v y v + M/2, p. ej. 0 y 4 en 8-PSK), como corresponde a BPSK.
    4. Mide la periodicidad de trama: fraccion de simbolos iguales a los de
       'lag' posiciones antes (aleatorio con M valores = 1/M).
    5. Perfil modulo P: fraccion de simbolos "de sincronismo" segun la posicion
       dentro de la trama (P = 256 para STANAG 4285).

USO
    python sa_symbols.py volcado.txt                 # informe en texto
    python sa_symbols.py volcado.txt --json r.json   # ademas, resultado en JSON
    python sa_symbols.py volcado.txt --frame 256 --minrun 40 --lags 31 32 256 512

COMO LIMITAR LO QUE SE AFIRMA
    - Todo esto sale de la demodulacion de S.A., que depende de PLL, Carrier y BR.
      Un cambio de ejecucion puede cambiar el desfase (0/4 pasa a 2/6).
    - La deteccion de tramos usa un umbral de longitud minima (--minrun). Con ruido
      los tramos de sincronismo salen mas cortos que 80 simbolos.
    - La coincidencia a lag L solo indica periodicidad; no identifica el codigo.

El mismo algoritmo esta implementado en el visualizador HTML (Visor de simbolos S.A.).
"""
import argparse
import json
import re
from collections import Counter

HEAD_RE = re.compile(r"<<<\s*Dem of Signals Analyzer\s*>>>")
TABLE_RE = re.compile(r"^\s*(\d+)\s*==>\s*(-?[\d.,]+)\s*$")


def parse_dump(text):
    """Devuelve una lista de volcados: {'n_ary','angles','symbols'(list[int])}."""
    parts = HEAD_RE.split(text)
    dumps = []
    for part in parts:
        if "Data:" not in part:
            continue
        head, data = part.split("Data:", 1)
        m = re.search(r"n-Ary:\s*(\d+)", head)
        n_ary = int(m.group(1)) if m else None
        angles = {}
        for line in head.splitlines():
            t = TABLE_RE.match(line)
            if t:
                angles[int(t.group(1))] = float(t.group(2).replace(",", "."))
        digits = re.sub(r"[^0-9]", "", data.split("\n\n")[0] if False else data)
        symbols = [int(c) for c in digits]
        dumps.append({"n_ary": n_ary or (max(angles) + 1 if angles else 8),
                      "angles": angles, "symbols": symbols})
    return dumps


def histogram(symbols, m):
    c = Counter(symbols)
    return [c.get(i, 0) for i in range(m)]


def sync_runs(symbols, m, minrun=40):
    """Tramos con solo dos valores opuestos {v, v+m/2}. Devuelve lista de
    (inicio, longitud, v) sin solapes, ordenada por inicio."""
    half = m // 2
    cand = []
    for v in range(half):
        run_start = None
        for i, s in enumerate(symbols + [-1]):
            ok = s in (v, v + half)
            if ok and run_start is None:
                run_start = i
            elif not ok and run_start is not None:
                if i - run_start >= minrun:
                    cand.append((run_start, i - run_start, v))
                run_start = None
    cand.sort(key=lambda r: -r[1])
    taken, out = [], []
    for st, ln, v in cand:
        if all(st + ln <= a or st >= a + b for a, b, _ in taken):
            taken.append((st, ln, v))
            out.append((st, ln, v))
    return sorted(out)


def lag_equality(symbols, lags):
    """Fraccion de simbolos iguales a los de 'lag' posiciones antes."""
    res = {}
    for lag in lags:
        n = len(symbols) - lag
        if n <= 0:
            continue
        eq = sum(1 for i in range(n) if symbols[i + lag] == symbols[i])
        res[lag] = eq / n
    return res


def frame_profile(symbols, m, frame=256, skip=0):
    """Por cada posicion dentro de la trama, fraccion de simbolos que valen 0 o m/2
    en cualquiera de los dos pares posibles (se toma el par dominante)."""
    half = m // 2
    x = symbols[skip:]
    nfr = len(x) // frame
    best = None
    for v in range(half):
        col = [0] * frame
        for f in range(nfr):
            for k in range(frame):
                if x[f * frame + k] in (v, v + half):
                    col[k] += 1
        mean = sum(col) / (nfr * frame) if nfr else 0
        if best is None or mean > best[0]:
            best = (mean, v, [c / nfr for c in col] if nfr else col)
    return {"pair": best[1], "profile": best[2]} if best else None


def analyze(dump, frame=256, minrun=40, lags=(31, 32, 48, 256, 512)):
    s, m = dump["symbols"], dump["n_ary"]
    runs = sync_runs(s, m, minrun)
    return {
        "n_ary": m,
        "n_symbols": len(s),
        "angles": dump["angles"],
        "histogram": histogram(s, m),
        "sync_runs": runs,
        "lag_equality": lag_equality(s[:200000], lags),
        "random_level": 1.0 / m,
        "frame_profile": frame_profile(s, m, frame, skip=0),
    }


def report(res, frame):
    L = []
    L.append(f"{res['n_symbols']} simbolos, n-Ary {res['n_ary']}")
    L.append("Histograma: " + "  ".join(f"{i}:{c}" for i, c in enumerate(res["histogram"])))
    L.append(f"Coincidencia a lag L (azar = {res['random_level']:.3f}):")
    for lag, v in res["lag_equality"].items():
        L.append(f"  L={lag:<5} {v:.3f}")
    runs = res["sync_runs"]
    L.append(f"Tramos de sincronismo (>= minrun): {len(runs)}")
    for st, ln, v in runs[:25]:
        L.append(f"  inicio {st:<8} longitud {ln:<6} valores {{{v},{v + res['n_ary'] // 2}}}  pos. en trama {st % frame}")
    if len(runs) > 25:
        L.append(f"  ... {len(runs) - 25} mas")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("--json")
    ap.add_argument("--frame", type=int, default=256)
    ap.add_argument("--minrun", type=int, default=40)
    ap.add_argument("--lags", type=int, nargs="+", default=[31, 32, 48, 256, 512])
    a = ap.parse_args()
    text = open(a.file, encoding="utf-8", errors="ignore").read()
    out = []
    for k, d in enumerate(parse_dump(text), 1):
        r = analyze(d, a.frame, a.minrun, tuple(a.lags))
        print(f"=== volcado {k} ===")
        print(report(r, a.frame))
        out.append(r)
    if a.json:
        json.dump(out, open(a.json, "w"), indent=1)


if __name__ == "__main__":
    main()
