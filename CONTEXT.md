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

4. **Se descartó Netatmo**: su endpoint público (`getpublicdata`) exige
   registrar una app OAuth2 y renovar tokens — no es un fetch anónimo
   como las tres anteriores. El usuario decidió el 25/07/2026 dejarlo
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
estación** (mismas fuentes METAR/XEMA/Meteoclimatic que el texto de la
sección) — el índice y el color se recalculan solos en el navegador, no
hace falta tocar esa parte del script. Si se añade o quita una estación de
la lista de texto, añadir/quitar también su entrada en `fireStations` para
que el mapa y el texto no diverjan.

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
Qué hace: lee este CONTEXT.md, actualiza SÍNTESIS CORTO PLAZO, ESTOFEX
(texto), OLA DE CALOR MARINA y RIESGO DE INCENDIO (regla 30-30-30)
consultando fuentes web, y publica el cambio **directamente en `main`**
subiendo el `index.html` completo vía "Upload files" (sin Pull Request —
el usuario desactivó el paso de revisión el 25/07/2026). Si alguna fuente
no responde, dejar esa sección tal cual y anotarlo en la descripción del
commit.

## Convención para añadir enlaces nuevos
Formato de cada enlace en las secciones de tipo "linklist":
<a href="URL" target="_blank" rel="noopener">Nombre — descripción corta<small>Detalle</small></a>
