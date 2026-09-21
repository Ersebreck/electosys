# Electosys

Sistema de Análisis de Elecciones — procesamiento y visualización de resultados
electorales de Bogotá, con foco en el desempeño del Pacto Histórico (PH).

App en vivo (Streamlit Community Cloud): _agregar link una vez desplegado_.

## Qué incluye

- **Presidencial 2022** (1ra vuelta), **Territoriales 2023** (Alcaldía, Concejo, JAL) y
  **Presidencial/Cámara/Senado 2026** (1ra vuelta, ESCRUTINIO oficial), ciudad completa,
  a nivel de puesto de votación.
- Consejos de Juventud: pendiente (elección local aparte, sin archivo fuente). Consultas
  internas de partidos y CITREP (curules de paz) de Congreso 2026: fuera de alcance, no
  son corporaciones de elección popular general.

## Estructura

```
app.py                      # app de Streamlit (mapas, barras, dispersión)
src/processing/
  geo_utils.py               # lee puesto_de_votacion.gpkg y une votos<->geometría por nombre
  export_sources.py          # vuelca cada fuente cruda a Excel, ciudad completa
  build_analysis_dataset.py  # junta las 4 elecciones en un dataset PH por puesto
  build_geojson_localidades.py # convierte el shapefile de localidades a GeoJSON
  ph_bosa.py                  # resultados PH en Bosa por puesto (encargo original)
output/
  files/    # Excels y CSV procesados que consume la app y que se pueden compartir
            # (excepto congreso_2026_camara/senado_bogota.csv: 55-120MB a nivel
            # candidato, no versionados por tamaño, regenerables con export_sources.py)
  maps/     # localidades.geojson para el choropleth
data/       # fuentes crudas (Registraduría/IDECA), no versionado, ver abajo
```

## Correr localmente

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

La app solo lee `output/files/` y `output/maps/` (ya procesados y versionados).
No necesita `data/` para correr.

## Regenerar los datos procesados

Requiere los archivos crudos en `data/` (no versionados por tamaño): los CSV
`MMV_*`/`DIVIPOLE_*` de la Registraduría, `MMV_CONGRESO_2026.zip` y
`MMV_Presidente1V_2026.zip` (formato "auditor" de Registraduría, ESCRUTINIO),
el `puesto_de_votacion.gpkg` de IDECA, y `loca.zip` (shapefile de localidades).
Con eso en su lugar:

```bash
python3 src/processing/export_sources.py   # Congreso 2026 tarda ~4 min: CSV nacional de 9.75GB sin comprimir
python3 src/processing/build_analysis_dataset.py
python3 src/processing/build_geojson_localidades.py
python3 src/processing/ph_bosa.py
```

## Notas de calidad de datos

- **Geometría**: el número de puesto del gpkg de IDECA no coincide con el
  código de puesto de la Registraduría — se une por nombre de puesto
  normalizado (~85-95% de match, el resto son sitios nuevos/renombrados).
- **Etiqueta de PH**: en territoriales 2023 la coalición de PH usa nombres
  distintos por corporación y hasta por localidad (`PACTO HISTÓRICO`,
  `PACTO HISTÓRICO BOGOTÁ`, `PACTO HISTÓRICO COLOMBIA PUEDE`, `COALICIÓN
  PACTO POR USME`, etc.) — se cuenta como PH cualquier partido cuyo nombre
  contenga "PACTO".
- **Participación/abstención**: Presidencial 2022, Presidencial 2026, Cámara 2026 y
  Senado 2026 usan su propio censo real (cruzado por código exacto de puesto —
  mismo DIVIPOL de cada elección — no por nombre, 0% sin match). Territoriales 2023
  no tiene censo publicado en los archivos de la Registraduría, así que se usa como
  proxy el censo de Presidencial 2026 (`MMV_Presidente1V_2026.zip`, archivo
  `DIVIPOL_*`) cruzado por nombre — el censo de Bogotá varía poco de una elección a
  otra. Quedan sin dato los puestos especiales/institucionales (cárceles, PUESTO
  CENSO) y un ~7% de puestos sin match por nombre (mismo problema de la geometría,
  ver arriba).
- **2026 (Presidencial/Cámara/Senado)**: formato ESCRUTINIO oficial de Registraduría
  (`;`-separado, sin encabezado, códigos numéricos), decodificado contra las tablas
  DIVIPOL/PARTIDOS/CANDIDATOS de cada elección (ver `Estructuras Basicas.pdf` dentro
  de cada zip). El DIVIPOL de Congreso no publica el nombre de localidad por puesto
  (solo el código); se completa con un mapa fijo de las 20 localidades de Bogotá.
  **Dato curioso sin explicar**: los totales de Presidencial 2026 (4,128,330 votos,
  1,705,455 de PH) coinciden exactamente con los de Presidencial 2022 pese a tener
  candidatos y partidos distintos — posible indicio de que el archivo es un
  simulacro/dato de prueba de la Registraduría, no un resultado real. Tratar estas
  cifras de 2026 con cautela.
