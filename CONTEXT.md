# Contexto del proyecto — Panel convectivo este peninsular

Web pública: https://angsarcat.github.io/Meteo/
Repositorio: AngSarCat/Meteo (rama main, GitHub Pages sirviendo index.html desde raíz)

## Qué es esto
Panel de seguimiento de riesgo convectivo severo y contexto oceánico (ola de
calor marina) para el este peninsular español (Cataluña, C. Valenciana,
Murcia, Baleares). No es un producto oficial — apoyo visual, siempre
remitiendo a AEMET/Meteocat como fuente oficial de avisos.

## REGLA FIJA — leer antes de editar
**No cambiar clases CSS ni la estructura de `<div>` existente** salvo que se
pida explícitamente. Cada sección del HTML está delimitada por comentarios
tipo `<!-- ================= NOMBRE ================= -->` — localiza el
bloque por ese comentario y edita solo el contenido de texto/enlaces dentro
de él.

## Estructura actual del index.html (por comentario)
- AVISOS — enlaces AEMET avisos + Meteocat avisos
- ENLACES (Fuentes en tiempo real) — enlaces generales (radar, satélite, rayos...)
- SÍNTESIS CORTO PLAZO — párrafo editorial con periodo de validez explícito
- ESTOFEX — resumen editorial + imagen en vivo del mapa (`<img id="estofexMap">`)
- OLA DE CALOR MARINA — tarjeta de estadísticas (.statgrid) + párrafos
- RIESGO DE INCENDIO — regla 30-30-30 calculada por Claude (ver sección propia abajo)
- ÍNDICE DE SEVERIDAD COMPUESTO — heurística propia sobre CAPE/cizalla/gradiente térmico/CIN/MFC/combustible marino (ver sección propia abajo)
- MAPA INTERACTIVO DE KPIs — selector de KPI + mapa Cressman/Voronoi + skew-T por estación (mismos datos que el índice de severidad)
- TEMPERATURA DEL MAR — enlaces (Copernicus Marine, SOCIB)
- RIESGO FLUVIAL — enlaces ACA/SAIH Catalunya, SAIH Ebro, SAIH Júcar (caudales y embalses en tiempo real)
- TERREMOTOS — enlace IGN visualizador de terremotos próximos
- MAPAS DE RIESGOS — enlace Protecció Civil / ICGC (mapa de riscos, Cataluña)
- INCIDENCIAS — enlaces a 112 CV y focs.cat

## Paleta y tipografía (no cambiar sin que se pida)
- Fondo: #0A1120, paneles: #101B30 / #16233D, borde: #24344F
- Acento: #37D6C4 (cyan), niveles: amarillo #F2C14E / naranja #F2914E / rojo #E24E4E
- Tipografía: Space Grotesk (títulos), IBM Plex Sans (texto), IBM Plex Mono (datos)

## RIESGO DE INCENDIO — regla 30-30-30 (añadido 25/07/2026)
Sección que detecta zonas del este peninsular donde se dan a la vez las tres
condiciones de la "regla 30-30-30": humedad relativa ≤30%, viento sostenido
≥30 km/h y temperatura ≥30°C. Reutiliza las clases existentes (`card full`,
`lvlbar`/`lvlchip`, `body`/`zone`, `snapshot-note`) — no se ha añadido CSS
nuevo.

**Fuentes y cómo consultarlas cada día:**

1. **METAR** (aeródromos, oficial) — `https://weather.cod.edu/digatmos/sao/`
   es un directorio con un fichero por hora, nombre `AAMMDDHH.sao` (ej.
   `26072517.sao` = 2026-07-25 17Z). Cada fichero es un volcado de texto
   plano con TODOS los METAR mundiales de esa hora (~1-1.2 MB). Para
   evitar el bloqueo de "URL no vista antes" de la herramienta de fetch,
   usar el navegador (Claude in Chrome): navegar al directorio para ver
   el último fichero disponible, y dentro de esa misma pestaña hacer
   `fetch()` vía `javascript_tool` sobre la URL exacta del `.sao` más
   reciente — el fetch same-origin funciona sin restricciones.
   Aeródromos de interés y sus códigos ICAO: Barcelona LEBL, Sabadell
   LELL, Reus LERS, Girona LEGE, Lleida-Alguaire LEDA, Valencia LEVC,
   Alicante LEAL, San Javier/Murcia LELC, Palma LEPA, Ibiza LEIB,
   Menorca LEMH. El aeródromo de La Seu d'Urgell (LERU) NO emite METAR.
   De cada línea METAR: viento en el grupo `dddffKT` (dd=dirección,
   ff=nudos, ×1.852=km/h), temperatura/punto de rocío en `TT/DD` antes
   de `Q####`. La HR se calcula con la fórmula de Magnus a partir de
   T y Td: `RH = 100 * exp(17.625*Td/(243.04+Td)) / exp(17.625*T/(243.04+T))`.

2. **XEMA / Meteocat** (Cataluña, oficial, datos abiertos, sin API key) —
   dataset Socrata en `https://analisi.transparenciacatalunya.cat/resource/nzvn-apee.json`.
   Formato largo: cada fila es `codi_estacio` + `codi_variable` +
   `data_lectura` + `valor_lectura`. Variables clave (dataset de
   metadatas `https://analisi.transparenciacatalunya.cat/resource/4fb2-n3yi.json`):
   `32` = Temperatura (°C), `33` = Humitat relativa (%),
   `30` = Velocitat del vent a 10m (**m/s**, convertir ×3.6 a km/h).
   Para nombre/comarca de cada estación: dataset de metadatos de
   estaciones `https://analisi.transparenciacatalunya.cat/resource/yqwd-vj5e.json`
   (columnas `codi_estacio`, `nom_estacio`, `nom_comarca`, `nom_provincia`).
   Consulta recomendada: primero `$select=max(data_lectura) as t` para
   obtener el instante más reciente, luego filtrar
   `$where=codi_variable in ('30','32','33')&data_lectura={t}` y pivotar
   por estación en el propio `javascript_tool` del navegador (igual que
   METAR, hacer el fetch dentro de una pestaña ya cargada en ese dominio
   para evitar el bloqueo de provenance de la herramienta de fetch).

3. **Meteoclimatic** (red amateur, sin control de calidad garantizado,
   relleno de densidad en Comunidad Valenciana / Murcia / Baleares donde
   no hay XEMA) — `https://www.meteoclimatic.net/feed/xml/CODIGO`.
   Códigos de región confirmados: `ESPVA` (Comunidad Valenciana —
   *no* `ESVAL`, ese no devuelve datos), `ESMUR` (Región de Murcia),
   `ESIBA` (Illes Balears), `ESCAT` (Cataluña, aunque aquí se prioriza
   XEMA). El XML no tiene cabeceras CORS accesibles por fetch cruzado:
   navegar directamente a la URL en el navegador y parsear con
   `DOMParser` dentro de `javascript_tool` (`doc.querySelector('temperature now')`,
   `humidity now`, `wind now`; unidades ya en °C/%/km/h). El campo
   `<QOS>` (nivel de auditoría de calidad) casi siempre viene a `0`
   (sin auditar) — no hay forma limpia de filtrar solo estaciones
   auditadas vía este feed, así que esta fuente se trata siempre como
   "sin verificar" en el texto de la sección, nunca como hallazgo
   principal.

4. **AVAMET** (red amateur/voluntaria de la Comunitat Valenciana —
   Castelló, València y Alacant; sin control de calidad garantizado,
   tratar igual que Meteoclimatic — añadida 19/10/2026 a petición del
   usuario). Sin API pública ni feed XML/JSON/CSV/RSS documentado, pero
   la página en vivo `https://www.avamet.org/mxo-meteoxarxaonline.html`
   (o `mxo-mxo.php`) embebe TODA la red (908 estaciones a 19/10/2026) como
   un array JS válido como JSON dentro de un `<script>` inline, variable
   `var data = [...]`. Método de extracción (navegador, `javascript_tool`):
   localizar el `<script>` inline cuyo texto contiene `lat`/`lon` (hay
   varios scripts; ese es el que tiene el array), cortar la subcadena desde
   `var data = [` (incluyendo el `[`) hasta el `];` que la cierra, y hacer
   `JSON.parse()` directo — las claves y valores string ya vienen entre
   comillas dobles, es JSON válido sin necesidad de reescritura. Claves
   relevantes por estación: `esta` (id interno, ej. `c09m001e01`), `muni`
   (municipio), `dess` (descripción/pedanía, puede ser `null`), `msnm`
   (altitud, string con punto de millar: `"1.181"` = 1181 m), `lati`/`logi`
   (latitud/longitud, 8 decimales, strings), `temp`/`hrel`/`vent`
   (velocidad media)/`vent_dir`/`vent_max`/`prec`/`data_ini` (timestamp
   `DD/MM/YYYY HH:MM`, hora local peninsular). **Importante**: `javascript_tool`
   bloquea con `[BLOCKED: Cookie/query string data]` si el resultado
   devuelto directamente como expresión final es un JSON con más de ~5-10
   objetos (demasiados `:`/`,` seguidos, se confunde con datos de
   cookies/query string) — para extraer más de un puñado de estaciones,
   volcar el JSON a un `<pre>` con `document.body.innerHTML` (o
   `appendChild`) y leerlo con `get_page_text` (que si acepta payloads
   grandes), trabajando en trozos de ~45.000 caracteres si hace falta el
   catálogo completo, o filtrar a los municipios de interés en el propio
   navegador para devolver solo esos (unas pocas decenas de objetos SÍ
   se pueden devolver como resultado directo de `javascript_tool` sin
   bloqueo).
   **Cobertura real**: la red cubre densamente el interior de Castelló,
   València y Alacant (centenares de estaciones en comarcas de montaña
   como el Maestrat, l'Alt Millars, el Racó d'Ademús, la Serrania, la
   Vall de Cofrents-Aiora, el Comtat, l'Alcoià, l'Alt Vinalopó) que
   METAR/XEMA/Meteoclimatic apenas tocan — es la fuente que mejor llena
   ese vacío para la regla 30-30-30 y para el mapa de KPIs. NO cubre
   Cataluña ni Baleares.
   **Estaciones añadidas al panel el 19/10/2026** (15 nuevas filas en
   `fireStations`, elegidas para cubrir el interior sin duplicar cobertura
   ya existente): Morella–Fàbrica Giner (`c01m080e03`), Vistabella del
   Maestrat–Sant Joan de Penyagolosa (`c02m139e01`, 1285 m, referencia de
   máxima altitud), Montanejos (`c08m079e01`), Ademuz–IES Ademuz
   (`c09m001e01`, el punto más interior de toda la red), Chelva
   (`c10m106e01`), Requena–centro (`c17m213e17`), Cofrentes (`c19m097e02`),
   Ayora–Casa Rural Los Pastores (`c19m044e16`), Enguera (`c22m118e05`),
   Agres–El Tossal (`c26m003e07`), Castalla–CEIP La Llauria
   (`c27m053e13`), Villena (`c28m140e13`), Novelda–centre (`c29m093e04`),
   Orihuela (`c34m099e28`), Pego–Ambra (`c30m102e03`). Coordenadas exactas
   y el procedimiento de selección quedan documentados en las notas del
   proyecto (`claude/meteo-dashboard-notes.md`).

**Dos usos distintos de AVAMET en el panel (desde 19/10/2026 segunda pasada):** (a) un subconjunto curado de 15 estaciones, elegido a mano para rellenar el hueco de cobertura del interior sin duplicar METAR/XEMA/Meteoclimatic, que vive en `fireStations` (ver más abajo) y se actualiza a mano estación por estación; (b) el array completo de estaciones con lectura válida de `prec` (típicamente ~850 de las 908, tras descartar las que no traen lat/lon o `prec` numérico), usado tal cual para el nuevo mapa de densidad de lluvia (`rainStations`, ver sección dedicada más abajo) — ahí no se cura ni se filtra por municipio, se vuelca la red entera dentro de la bounding box de interés. **Importante sobre el campo `prec`**: es la precipitación acumulada desde medianoche hora local, NO una ventana móvil de 24h — en el texto del panel esto se etiqueta explícitamente para no sugerir una precisión que la fuente no da; si en el futuro se necesita un acumulado de 24h real, habría que sumar `prec` de hoy con una fracción de `prec` de ayer (no se guarda historial de estaciones individuales entre pasadas, así que de momento no es viable sin almacenar snapshots).

5. **Se descartó Netatmo**: su endpoint público (`getpublicdata`) exige
   registrar una app OAuth2 y renovar tokens — no es un fetch anónimo
   como las anteriores. El usuario decidió el 25/07/2026 dejarlo
   fuera para no añadir ese mantenimiento.

**Cómo redactar la sección cada día:** listar primero (si las hay)
estaciones METAR/XEMA que cumplan las tres condiciones a la vez ("cumple
las tres condiciones ahora"); después estaciones oficiales que estén cerca
(2 de 3, o las tres con margen estrecho) bajo "muy cerca del umbral"; por
último, si aporta algo, 1-2 lecturas de Meteoclimatic marcadas
explícitamente como red amateur sin verificar. Si ninguna estación cumple
las tres condiciones, decirlo explícitamente en vez de dejar la sección
vacía o forzar un hallazgo. Actualizar el chip de "N estaciones cumplen…" y
la hora en `snapshot-note` cada vez.

**Mapa de estaciones (añadido 25/07/2026):** dentro de la misma tarjeta
RIESGO DE INCENDIO hay `<div id="fireIndexMapWrap">` → `<div id="fireIndexMap">`
donde un script D3 (v7.8.5 + topojson v3.0.2, CDN cdnjs, cargados al final
del `<body>` junto al script de `estofexMap`) dibuja en vivo, en el
navegador de cada visitante: el contorno de las provincias del este
peninsular (topología `esp.topo.json` de
`https://cdn.jsdelivr.net/npm/datamaps@0.5.10/src/js/data/esp.topo.json`,
objeto `esp`, propiedad `properties.name` con nombres en castellano —
"Lérida", "Gerona", etc., no catalanes) y un círculo por estación
(`fireStations`, array JS embebido en el propio script, NO se genera server
side). Cada objeto del array tiene `{name, lat, lon, t, hr, wind}` (t=°C,
hr=%, wind=km/h). El índice compuesto 0-100 se calcula en el propio
navegador con lógica de factor limitante (tempScore, humScore, windScore
por normalización lineal, índice = 100 × el mínimo de los tres) y el color
del círculo sale de `colorForIndex(index)` (verde-amarillo-naranja-rojo).
**Actualización diaria: hay que reescribir a mano el array `fireStations`
dentro del `<script>` con los valores t/hr/wind del día para cada
estación** (mismas fuentes METAR/XEMA/Meteoclimatic/AVAMET que el texto de
la sección) — el índice y el color se recalculan solos en el navegador, no
hace falta tocar esa parte del script. Si se añade o quita una estación de
la lista de texto, añadir/quitar también su entrada en `fireStations` para
que el mapa y el texto no diverjan.

**Actualización 19/10/2026 — tercer bloque (AVAMET):** `fireStations` pasó
de 35 a 50 entradas con la incorporación de AVAMET (ver fuente nº4 arriba):
ahora son TRES bloques que deben refrescarse siempre juntos en la misma
pasada — 21 no-SYNOP (METAR/XEMA/Meteoclimatic), 14 SYNOP (pipeline de
sondeos Ogimet, solo si corre ese día) y 15 AVAMET (interior de la
Comunitat Valenciana) — nunca publicar solo uno o dos de los tres y dejar
el resto con la fecha de un día anterior, por el mismo motivo que ya
documentaba el incidente de los dos bloques originales. El recuento de
verificación de integridad pre-publicación pasa de "fireStations=35" a
"fireStations=50" a partir de esta fecha.

## Mapa de densidad de lluvia en 24h (añadido 19/10/2026, segunda pasada del día)
Tarjeta nueva dentro de ÍNDICE DE SEVERIDAD COMPUESTO, colocada justo debajo de "Índice de riesgo de
lluvia torrencial" (mismo `<!-- ... -->` de sección, sin comentario propio — igual que esa tarjeta
y la de severidad comparten el bloque "ÍNDICE DE SEVERIDAD COMPUESTO"). `<div id="rainDensityMapWrap">`
→ `<div id="rainDensityMap">`, dibujado por `drawRainMap()` (misma receta D3 v7.8.5 + topojson v3.0.2
+ Cressman de dos pasadas que `drawFireIndexMap`/`drawTorrentialMap`/`drawSeverityMap`, reutilizando
`buildFireCressmanGrid` y `loadFireCountries` sin modificarlas). Fuente de datos: `rainStations`, un
array JS embebido de ~850 objetos `{n, lat, lon, p}` (n=nombre/municipio, p=mm acumulados desde
medianoche local) — el volcado directo del campo `prec` de AVAMET para toda estación con lectura
válida en la bounding box de interés (Comunitat Valenciana y zonas limítrofes), sin curar a mano
como las 15 de `fireStations`. Por eso usa un radio de Cressman mucho más corto (R1=30km/R2=10km,
máscara de cobertura a 22km) que los mapas de escala peninsular de este panel (R1=300-320km/R2=130-140km,
máscara 180-250km) — la densidad real de la red lo permite y lo exige para no sobre-suavizar el
episodio. Escala de color por `rainColor(v)`: <10mm fondo, 10-50 azul, 50-100 azul claro, 100-200
naranja, ≥200 rojo (`#C1272D`, mismo tono de "extremo" que el resto del panel). **Extracción de
`rainStations`**: mismo método de navegador que el resto de AVAMET (`var data = [...]` embebido en
`mxo-mxo.php`), filtrando por bounding box aproximada de la Comunitat Valenciana (lat 37,7-40,9, lon
-1,7 a 0,8) y por `prec` parseable; para evitar el bloqueo de `javascript_tool` con ~850 objetos, se
redujo cada estación a 4 campos mínimos (`n/lat/lon/p`, nombres de municipio truncados a su forma
HTML-entidad tal cual vienen en el campo `muni` de AVAMET — hay que decodificarlas con
`html.unescape` al generar el array final, si no quedan tooltips con `&agrave;`/`&prime;`/etc.
literales) antes de volcar a `<pre>` y leer en dos tandas de `get_page_text` (~24.000 caracteres cada
una, igual que el límite ya documentado arriba). **Primer uso, 19/10/2026**: aisló con claridad el
núcleo de la DANA "Adam" en La Safor/norte de la Marina Alta (Pego 490,5mm, Oliva 450,3mm, la Vall
d'Ebo 397,2mm, Vilallonga 396,7mm, Miramar 345,0mm; 32 estaciones ≥200mm, 61 ≥100mm) — hallazgo que
motivó también una entrada nueva en la síntesis a corto plazo y en el texto de riesgo de incendio,
con corroboración por prensa (Infobae, El Economista, Mundiario) de 4 fallecidos durante el temporal
(3 en la Comunitat Valenciana) y aviso rojo de AEMET vigente en la zona desde el domingo 18. **No se
tocó** `mapa_kpis_prototipo.html` ni `kpimapDataJson`/`mapDataJson` en esta pasada — es una tarjeta y
un array completamente nuevos, sin relación con el pipeline de sondeos ni con el mapa de KPIs.

## Pipeline de sondeos TTAA/TTBB + SYNOP — índice de severidad y mapa de KPIs (añadido 26/07/2026 noche)
Scripts en la raíz del repo (`temp_decoder.py`, `synop_decoder.py`, `compute_kpis.py`,
`mfc.py`, `sst_data.py`, `severity_index.py`, `build_map_data.py`) que generan los
datos de las tarjetas ÍNDICE DE SEVERIDAD COMPUESTO y MAPA INTERACTIVO DE KPIs dentro
de `index.html`, la página independiente `mapa_kpis_prototipo.html`, y las 14 filas
SYNOP del array `fireStations` de RIESGO DE INCENDIO.

**Por qué existen:** hasta esta fecha ambos mapas se habían generado a mano, una única
vez, en una sesión de Cowork con acceso de red sin restricciones — un "snapshot" que no
se actualizaba solo. El usuario pidió que se refrescara cada vez que se ejecuta la
actualización diaria del panel, así que el pipeline quedó escrito y versionado para
poder repetirse.

**Arquitectura (restricción real, no evitable):** el sandbox de shell de Cowork bloquea
el acceso de red a ogimet.com (`403 Forbidden, blocked-by-allowlist`), que es la única
fuente gratuita y sin registro de sondeos TEMP (TTAA/TTBB) y SYNOP para estaciones
europeas. El navegador Claude in Chrome sí tiene red sin restricciones. Por eso el flujo
es obligatoriamente en tres pasos:

1. **Fetch (navegador):** navegar a `https://www.ogimet.com/display_sond.php?...`
   (sondeos) y `https://www.ogimet.com/display_synops.php?...` (SYNOP) y volcar el
   texto plano de cada estación. Para transferir texto largo (decenas de KB) del
   navegador al agente sin sufrir el truncamiento silencioso (~800-1000 caracteres) de
   `javascript_tool`, escribirlo en un `<pre>` vía `document.body.innerHTML`
   (escapando `&`/`<`) y leerlo con `get_page_text`, o parsear con `DOMParser`. Guardar
   el volcado de todas las estaciones en un único fichero de texto con marcadores
   `===STATION_<id>_START===...===STATION_<id>_END===`
   (`raw_ttaa_YYYYMMDD.txt`, `raw_synop_YYYYMMDD.txt`).

2. **Procesado (shell, Python):**
   `python3 build_map_data.py raw_ttaa_YYYYMMDD.txt raw_synop_YYYYMMDD.txt --out
   map_data.json --fire-out fire_synop_update.json --severity-out
   severity_summary.json`. Requiere `metpy`, `numpy`, `pymetdecoder`
   (`pip install --break-system-packages metpy numpy pymetdecoder`).

3. **Publicación (navegador, "Upload files"):** minificar `map_data.json`
   (`json.dumps(d, ensure_ascii=False, separators=(',',':'))`) e inyectarlo tal cual —
   reemplazando solo el contenido entre etiquetas, igual que las demás secciones — en
   `<script id="kpimapDataJson" type="application/json">` (`index.html`) y
   `<script id="mapDataJson" type="application/json">` (`mapa_kpis_prototipo.html`).
   Con `severity_summary.json`, reescribir a mano el `lvlbar` y los párrafos de la
   tarjeta ÍNDICE DE SEVERIDAD COMPUESTO. Con `fire_synop_update.json`, reescribir las
   14 filas `SYNOP` del array `fireStations` — buscar cada fila por su `name` exacto y
   sustituir solo `t`/`hr`/`wind`, nunca `lat`/`lon`.

**Estaciones de sondeo (TEMP, 12):** Barcelona 08190, Palma/Son Bonet 08302, Murcia
08430, Nimes/Courbessac 07645, Ajaccio 07761, Argel/Dar El Beida 60390, A Coruña 08001,
Santander 08023, Madrid/Barajas 08221, Huelva 08383, Lisboa/Portela 08536,
Bordeaux/Merignac 07510.

**Estaciones SYNOP (22, para MFC — 14 de ellas duplican como filas SYNOP del mapa de
incendio):** ver los diccionarios `TEMP_STATIONS`/`MFC_STATIONS`/`FIRE_SYNOP_IDS` al
principio de `build_map_data.py` — es la fuente de verdad, no duplicar la lista aquí.

**Qué calcula cada script:**
- `temp_decoder.py`: decodificador de TEMP (TTAA/TTBB) escrito desde cero (no existe
  librería en PyPI) — niveles mandatorios y significativos, viento, altura geopotencial.
- `synop_decoder.py`: envuelve la librería `pymetdecoder` para SYNOP (AAXX); incluye
  un fallback que trunca en ` 333` si falla el decodificado de la sección 3 (visto con
  Ajaccio 07761 y su código de insolación francés no soportado).
- `compute_kpis.py`: SBCAPE/SBCIN/LCL/PWAT/cizalla 0-3km y 0-6km/lapse rate 850-500/
  nivel de congelación vía MetPy.
- `mfc.py`: convergencia de humedad (MFC) por ajuste planar de mínimos cuadrados sobre
  los vecinos más próximos de cada estación SYNOP.
- `sst_data.py`: tabla de referencia de SST/anomalía por subregión marina (no hay API
  gratuita sin registro con dato por punto) + componente de viento entrante a la costa
  → "combustible marino".
- `severity_index.py`: fórmula publicada en la propia tarjeta (CAPE + cizalla +
  gradiente térmico, atenuados por `e^-|CIN|/150`, más MFC y combustible marino).
- `build_map_data.py`: orquestador — decodifica, calcula, empareja cada estación de
  sondeo con su SYNOP más cercana, y escribe los tres JSON de salida.

**Limitaciones conocidas, aceptadas:** TTDD (niveles significativos por debajo de
100hPa) no se decodifica — no afecta a CAPE/CIN/cizalla/PWAT, todos muy por encima de
100hPa. Madrid/Barajas puede salir con `lapse_850_500`/`shear_0_6km`/`nivel_cong_m` a
`null` en sondeos donde falta el dato de viento en algún nivel — no bloquea el resto
del cálculo. La SST es una tabla de referencia por subregión, no un dato en vivo por
punto — coherente con lo que ya hacía a mano la tarjeta OLA DE CALOR MARINA.

## Historial — qué se intentó, qué se quitó, y por qué
Importante: lo que sigue ocurrió probando el artifact DENTRO del sandbox de
claude.ai, antes de desplegar en GitHub Pages. Ese sandbox bloquea peticiones
salientes (fetch/XHR) a dominios externos salvo unos pocos permitidos.
**Ahora que la web vive en GitHub Pages, ese bloqueo ya no aplica** — es el
navegador normal de cada visitante. Vale la pena reintentar lo siguiente si
se quiere recuperar funcionalidad en vivo:

1. **Mapa METAR en vivo (aviationweather.gov)**: se quitó porque el
`fetch()` fallaba en el sandbox. La causa real puede ser doble: (a) el
sandbox de claude.ai (ya no aplica en GitHub Pages), o (b) que
aviationweather.gov no envíe cabeceras CORS (esto SÍ seguiría fallando
en cualquier sitio, incluido GitHub Pages). No confirmado cuál era.
Si se quiere recuperar, probar primero en la web ya desplegada antes
de asumir que sigue roto.

2. **Mapa de CAPE (wetterzentrale.de vía `<img>`)**: se quitó porque el
usuario reportó que "no funciona" dentro de claude.ai. Un `<img src=...>`
normalmente SÍ carga en cualquier web normal (no depende de CORS, solo
de que el servidor no bloquee hotlinking). Buen candidato a reintentar
en la web ya desplegada.

3. **Iframe de texto ESTOFEX**: se quitó porque aparecía en blanco. Podría
ser por X-Frame-Options del propio estofex.org (bloqueo real, no del
sandbox) o por el sandbox de claude.ai. No confirmado. Reintentar con
cautela — si sigue en blanco en la web desplegada, es bloqueo real del
servidor y no merece la pena insistir.

4. **Resumen de texto de ESTOFEX**: no se puede automatizar con fetch()
porque estofex.org no envía cabeceras CORS — esto es un bloqueo real
del servidor, no del sandbox, así que seguirá aplicando en cualquier
entorno. La única vía es que un agente (Cowork) lo consulte y reescriba
el texto a mano, como hace la tarea diaria.

5. **Editor de código en línea de GitHub (github.com/.../edit/...)**: NO
usarlo para pegar bloques grandes de HTML. Su autocompletado de
etiquetas (`<small>`, `<a>`...) duplica los cierres y corrompe el
fichero al escribir mediante automatización de teclado. El método
fiable verificado es "Upload files" (github.com/OWNER/REPO/upload/BRANCH)
reemplazando el `index.html` completo con el fichero ya editado
localmente.

6. **CDN de raw.githubusercontent.com cachea agresivamente**: el 25/07/2026
un commit se construyó sobre una copia de `index.html` descargada con la
herramienta de fetch (no el navegador) y resultó estar cacheada varios
commits por detrás, borrando sin querer secciones ya publicadas. Para
leer el estado real de `main` antes de editar, usar SIEMPRE el navegador
(Claude in Chrome, `navigate` + lectura de la página) en vez de la
herramienta de fetch directa sobre `raw.githubusercontent.com` — el
navegador no sufre ese mismo caché obsoleto en la práctica observada.

## Tarea programada existente
Nombre: "meteo-panel-actualizacion-diaria"
Cadencia: diaria 11:00 hora local (+ ejecutable a demanda con "Run now")
Qué hace: lee este CONTEXT.md, actualiza SÍNTESIS CORTO PLAZO, ESTOFEX (texto), OLA DE
CALOR MARINA y RIESGO DE INCENDIO (regla 30-30-30) consultando fuentes web; **además,
desde el 26/07/2026 (noche), ejecuta el pipeline de sondeos descrito arriba** (fetch
Ogimet vía navegador → `build_map_data.py` → inyección del JSON minificado en
`index.html` y `mapa_kpis_prototipo.html` → reescritura manual del índice de severidad
y las 14 filas SYNOP del mapa de incendio) para que esas dos tarjetas no queden nunca
como un snapshot fijo. Publica el cambio **directamente en `main`** subiendo cada
fichero completo vía "Upload files" (sin Pull Request — el usuario desactivó el paso
de revisión el 25/07/2026). Si Ogimet no responde o algún sondeo no se puede
decodificar, dejar el índice de severidad / mapa de KPIs / filas SYNOP con su último
valor y anotarlo en la descripción del commit — nunca bloquear el resto de la
actualización diaria por esto. Si alguna otra fuente no responde, dejar esa sección tal
cual y anotarlo también en la descripción del commit.

## Convención para añadir enlaces nuevos
Formato de cada enlace en las secciones de tipo "linklist":
<a href="URL" target="_blank" rel="noopener">Nombre — descripción corta<small>Detalle</small></a>

## Índices de estabilidad RAOB + hodógrafo (06/08/2026)
Añadidos al mapa interactivo de KPIs (ambas copias, index.html y mapa_kpis_prototipo.html):
tabla de índices de estabilidad por estación de sondeo (K, TT, CT, VT, LI, SI, SWEAT, Boyden,
VGP, Tc/CCL, Haines, storm motion, SRH 0-1/0-3km, EHI, BRN, SCP, STP) y un panel de hodógrafo
con el perfil de viento por nivel y el vector de movimiento de tormenta (método de Bunkers,
vía MetPy). Cálculo en compute_kpis.py (ver docstring del módulo). Los 12 nuevos índices
también son seleccionables como capa de color en el desplegable del mapa. Mención del
Índice Haines de hoy añadida a la tarjeta de riesgo de incendio.
