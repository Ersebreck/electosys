"""
Helpers compartidos: leer puesto_de_votacion.gpkg (sqlite3+shapely, sin GDAL)
y unir resultados de votación con su geometría.

IMPORTANTE: el "Número_del_puesto" del gpkg (IDECA) NO es el mismo código que
el "PUESTO"/"Código Puesto" de los archivos de la Registraduría (MMV/DIVIPOLE)
- son numeraciones independientes que coinciden en cantidad pero no en
identidad. La llave que sí coincide (~88-95% de los puestos, el resto son
sitios nuevos/renombrados que el gpkg no tiene) es el NOMBRE: el
"Nombre_del_Sitio" del gpkg contra el "PUESNOMBRE"/"Nombre Puesto" de los
archivos de votos. Todo merge geo<->votos debe usar esa llave por nombre,
nunca el número de puesto.
"""
import sqlite3
import unicodedata

import pandas as pd
from shapely import wkb as shapely_wkb

DATA_DIR = "data"


def strip_accents(text):
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def norm_key(text):
    return strip_accents(str(text)).strip().upper()


def _parse_point(blob):
    flags = blob[3]
    envelope_sizes = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}
    header_len = 8 + envelope_sizes[(flags >> 1) & 0x07]
    point = shapely_wkb.loads(blob[header_len:])
    return point.y, point.x  # lat, lon


def load_puestos(localidad_code=None):
    """Puestos con lat/lon. `nombre_puesto` = Nombre_del_Sitio (llave de unión con
    los votos); `sitio_oficial` = Nombre_del_puesto (nombre oficial del colegio/sede).
    Si localidad_code es None, trae toda la ciudad."""
    con = sqlite3.connect(f"{DATA_DIR}/puesto_de_votacion.gpkg")
    query = """SELECT Código_de_localidad AS codigo_localidad, Nombre_de_localidad AS localidad,
                      Nombre_del_Sitio AS nombre_puesto, Nombre_del_puesto AS sitio_oficial,
                      Dirección AS direccion, Shape
               FROM temp_wfs_layer"""
    params = ()
    if localidad_code is not None:
        query += " WHERE Código_de_localidad = ?"
        params = (localidad_code,)
    df = pd.read_sql_query(query, con, params=params)
    con.close()

    df["latitud"], df["longitud"] = zip(*df["Shape"].map(_parse_point))
    df["_key"] = df["codigo_localidad"] + "|" + df["nombre_puesto"].map(norm_key)
    return df.drop(columns="Shape")


def merge_with_geo(votes_df, geo_df, localidad_col="codigo_localidad", puesto_col="nombre_puesto"):
    """Une un df de votos (con columnas de localidad + nombre de puesto) a la
    geometría por nombre normalizado. Localidad se rellena a 2 dígitos porque
    los archivos de votos a veces la traen sin ceros a la izquierda."""
    votes_df = votes_df.copy()
    votes_df["_key"] = (
        votes_df[localidad_col].astype(str).str.zfill(2) + "|" + votes_df[puesto_col].map(norm_key)
    )
    geo_cols = ["_key", "nombre_puesto", "sitio_oficial", "direccion", "latitud", "longitud"]
    merged = votes_df.merge(
        geo_df[geo_cols].rename(columns={"nombre_puesto": "_nombre_puesto_geo"}),
        on="_key", how="left",
    )
    return merged.drop(columns=["_key", "_nombre_puesto_geo"])
