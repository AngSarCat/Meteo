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
- SÍNTESIS CORTO PLAZO — párrafo editorial con periodo de validez explícito
- ESTOFEX — resumen editorial + imagen en vivo del mapa (`<img id="estofexMap">`)
- OLA DE CALOR MARINA — tarjeta de estadísticas (.statgrid) + párrafos
- TEMPERATURA DEL MAR — enlaces (Copernicus Marine, SOCIB)
- RIESGO FLUVIAL — enlaces ACA/SAIH Catalunya, SAIH Ebro, SAIH Júcar (caudales y embalses en tiempo real)
- ENLACES (Fuentes en tiempo real) — enlaces generales (radar, satélite, rayos...)
- INCIDENCIAS — enlaces a 112 CV y focs.cat

## Paleta y tipografía (no cambiar sin que se pida)
- Fondo: #0A1120, paneles: #101B30 / #16233D, borde: #24344F
- Acento: #37D6C4 (cyan), niveles: amarillo #F2C14E / naranja #F2914E / rojo #E24E4E
- Tipografía: Space Grotesk (títulos), IBM Plex Sans (texto), IBM Plex Mono (datos)

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

## Tarea programada existente
Nombre: "meteo-panel-actualizacion-diaria"
Cadencia: diaria 11:00 hora local (+ ejecutable a demanda con "Run now")
Qué hace: lee este CONTEXT.md, actualiza SÍNTESIS CORTO PLAZO, ESTOFEX 
(texto) y OLA DE CALOR MARINA consultando fuentes web, y publica el cambio 
**directamente en `main`** subiendo el `index.html` completo vía 
"Upload files" (sin Pull Request — el usuario desactivó el paso de revisión 
el 25/07/2026). Si alguna fuente no responde, dejar esa sección tal cual y 
anotarlo en la descripción del commit.

## Convención para añadir enlaces nuevos
Formato de cada enlace en las secciones de tipo "linklist":
<a href="URL" target="_blank" rel="noopener">Nombre — descripción corta<small>Detalle</small></a>
