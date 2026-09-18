# Electosys

Sistema de Análisis de Elecciones — procesamiento y visualización de resultados
electorales de Bogotá, con foco en el desempeño del Pacto Histórico (PH).

App en vivo (Streamlit Community Cloud): _agregar link una vez desplegado_.

## Qué incluye

- **Presidencial 2022** (1ra vuelta) y **Territoriales 2023** (Alcaldía, Concejo, JAL),
  ciudad completa, a nivel de puesto de votación.
- Cámara, Senado y Consejos de Juventud: pendientes, faltan los archivos fuente.

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
`MMV_*`/`DIVIPOLE_*` de la Registraduría, el `puesto_de_votacion.gpkg` de IDECA,
y `loca.zip` (shapefile de localidades). Con eso en su lugar:

```bash
python3 src/processing/export_sources.py
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
- **Participación real** (% sobre censo) solo está disponible para
  Presidencial 2022, único censo que tenemos.
