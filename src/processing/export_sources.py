"""
Vuelca cada fuente cruda a un Excel, ciudad completa (todas las localidades),
agregado a nivel puesto x partido x candidato (sin mesa, para caber en una
hoja de Excel y quedar al grano correcto para el EDA).

Salida: output/files/<fuente>.xlsx
"""
import io
import shutil
import tempfile
import zipfile

import pandas as pd

from geo_utils import DATA_DIR, load_puestos

OUT_DIR = "output/files"


def presidenciales_2022():
    df = pd.read_csv(
        f"{DATA_DIR}/MMV_XXX_16_001_XXX_XX_XX_XXX_2558.csv",
        sep=";",
        dtype=str,
    )
    df["VOTOS"] = pd.to_numeric(df["VOTOS"])
    key = ["ZONA", "COMUNOMBRE", "PUESTO", "PUESNOMBRE", "PARNOMBRE", "CANNOMBRE"]
    agg = df.groupby(key, dropna=False)["VOTOS"].sum().reset_index()
    agg = agg.rename(columns={
        "ZONA": "codigo_localidad", "COMUNOMBRE": "localidad", "PUESTO": "puesto",
        "PUESNOMBRE": "nombre_puesto", "PARNOMBRE": "partido", "CANNOMBRE": "candidato", "VOTOS": "votos",
    })
    return agg.sort_values(["codigo_localidad", "puesto", "votos"], ascending=[True, True, False])


def territoriales_2023(corporacion):
    chunks = pd.read_csv(f"{DATA_DIR}/MMV_2023_16_BOGOTA DC.csv", dtype=str, chunksize=300_000)
    key = ["Código Comuna", "Nombre Comuna", "Código Puesto", "Nombre Puesto", "Nombre Partido", "Nombre Candidato"]
    partials = []
    for chunk in chunks:
        sub = chunk[chunk["Nombre Corporación"] == corporacion].copy()
        sub["Total Votos"] = pd.to_numeric(sub["Total Votos"])
        partials.append(sub.groupby(key, dropna=False)["Total Votos"].sum())
    agg = pd.concat(partials).groupby(level=key).sum().reset_index()
    agg = agg.rename(columns={
        "Código Comuna": "codigo_localidad", "Nombre Comuna": "localidad", "Código Puesto": "puesto",
        "Nombre Puesto": "nombre_puesto", "Nombre Partido": "partido", "Nombre Candidato": "candidato",
        "Total Votos": "votos",
    })
    return agg.sort_values(["codigo_localidad", "puesto", "votos"], ascending=[True, True, False])


def divipole_censo_bogota():
    df = pd.read_csv(f"{DATA_DIR}/DIVIPOLE_PRESIDENTE_31_MAYO.csv", dtype=str)
    df = df[df["Municipio"].str.contains("bogota", case=False, na=False)]
    cols = ["Comuna", "Puesto", "Dirección ", "Latitud", "Longitud", "Mujeres", "Hombres", "Total",
            "TOTAL CENSO "]
    return df[cols].rename(columns={
        "Comuna": "localidad", "Puesto": "nombre_puesto", "Dirección ": "direccion",
        "Latitud": "latitud", "Longitud": "longitud", "Mujeres": "censo_mujeres",
        "Hombres": "censo_hombres", "Total": "censo_total", "TOTAL CENSO ": "censo_total_general",
    })


def _read_zip_entry(outer_path, inner_zip_path, entry_matcher):
    """Lee un archivo dentro de un zip anidado (zip dentro de zip), en memoria.
    `entry_matcher` filtra por substring el nombre del archivo a leer dentro
    del zip interno (los nombres traen timestamp, ej. DIVIPOL_20260526_*)."""
    outer = zipfile.ZipFile(outer_path)
    inner = zipfile.ZipFile(io.BytesIO(outer.read(inner_zip_path)))
    name = next(n for n in inner.namelist() if entry_matcher in n)
    return inner.read(name)


# Nombre de localidad, para cuando el DIVIPOL no lo trae (el de Congreso deja
# ese campo en blanco; el código de zona sí viene bien en ambos). Tomado del
# propio DIVIPOL de Presidencial 2026, que sí lo publica completo.
BOGOTA_LOCALIDADES = {
    "01": "LOCALIDAD 1 USAQUEN", "02": "LOCALIDAD 2 CHAPINERO", "03": "LOCALIDAD 3 SANTA FE",
    "04": "LOCALIDAD 4 SAN CRISTOBAL", "05": "LOCALIDAD 5 USME", "06": "LOCALIDAD 6 TUNJUELITO",
    "07": "LOCALIDAD 7 BOSA", "08": "LOCALIDAD  8 KENNEDY", "09": "LOCALIDAD 9 FONTIBON",
    "10": "LOCALIDAD 10 ENGATIVA", "11": "LOCALIDAD 11 SUBA", "12": "LOCALIDAD 12 BARRIOS UNIDOS",
    "13": "LOCALIDAD 13 TEUSAQUILLO", "14": "LOCALIDAD 14 MARTIRES", "15": "LOCALIDAD 15 ANTONIO NARIÑO",
    "16": "LOCALIDAD 16 PUENTE ARANDA", "17": "LOCALIDAD 17 CANDELARIA",
    "18": "LOCALIDAD 18 RAFAEL URIBE URIB", "19": "LOCALIDAD 19 CIUDAD BOLIVAR", "20": "LOCALIDAD 20 SUMAPAZ",
}


def _parse_divipol(raw_bytes):
    """Archivo DIVIPOL (ancho fijo, ver 'Estructuras Basicas.pdf' de Registraduría),
    filtrado a Bogotá D.C. (dep=16). Un renglón por puesto, con código y censo.
    Layout de línea (146 car.): dep[0:2] mun[2:5] zona[5:7] puesto[7:9]
    depnombre[9:21] mununombre[21:51] puestonombre[51:91] indicador[91:92]
    potencial_hombres[92:100] potencial_mujeres[100:108] mesas[108:114]
    localidad_cod[114:116] localidad_nombre[116:146] (el de Congreso deja
    estos dos últimos en blanco, se completa con BOGOTA_LOCALIDADES).
    """
    lines = raw_bytes.decode("latin1").splitlines()
    rows = [
        {
            "codigo_localidad": line[5:7],
            "puesto": line[7:9],
            "nombre_puesto": line[51:91].strip(),
            "censo_mujeres": int(line[100:108]),
            "censo_hombres": int(line[92:100]),
            "mesas": int(line[108:114]),
            "localidad": line[116:146].strip() or BOGOTA_LOCALIDADES.get(line[5:7], ""),
        }
        for line in lines if line[0:2] == "16"  # 16 = Bogotá D.C. en la codificación de Registraduría
    ]
    df = pd.DataFrame(rows)
    df["censo_total"] = df["censo_mujeres"] + df["censo_hombres"]
    return df


def _parse_partidos(raw_bytes):
    """Archivo PARTIDOS (ancho fijo): código[0:5] + nombre[5:205]."""
    lines = raw_bytes.decode("latin1").splitlines()
    return {line[0:5]: line[5:205].strip() for line in lines if line.strip()}


def _parse_candidatos(raw_bytes):
    """Archivo CANDIDATOS (ancho fijo, 138 car.): partido[11:16] + candidato[16:19]
    + preferente[19:20] + nombre[20:70] + apellido[70:120] (+ cédula/género/sorteo,
    no usados). candidato='000' es cabecera de lista (voto solo al partido)."""
    lines = raw_bytes.decode("latin1").splitlines()
    rows = [
        {
            "partido": line[11:16],
            "candidato": line[16:19],
            "nombre_candidato": f"{line[20:70].strip()} {line[70:120].strip()}".strip(),
        }
        for line in lines if line.strip()
    ]
    return pd.DataFrame(rows).drop_duplicates(["partido", "candidato"])


SPECIAL_CANDIDATOS = {"996": "VOTOS EN BLANCO", "997": "VOTOS NULOS", "998": "VOTOS NO MARCADOS"}

ESCRUTINIO_COLS = ["fijo", "dep", "mun", "zona", "puesto", "mesa", "comuna",
                    "corporacion", "circunscripcion", "partido", "candidato", "votos", "_trail"]


def _escrutinio_bogota(csv_stream, corporaciones):
    """Suma votos por (zona, puesto, corporación, partido, candidato) para Bogotá
    (dep=16), leyendo el CSV de escrutinio (';'-separado, sin encabezado, ver
    'Estructuras Basicas.pdf') en chunks para no cargarlo completo en memoria."""
    chunks = pd.read_csv(
        csv_stream, sep=";", header=None, names=ESCRUTINIO_COLS, dtype=str, chunksize=500_000,
    )
    key = ["zona", "puesto", "corporacion", "partido", "candidato"]
    partials = []
    for chunk in chunks:
        sub = chunk[(chunk["dep"] == "16") & chunk["corporacion"].isin(corporaciones)]
        if sub.empty:
            continue
        sub = sub.copy()
        sub["votos"] = pd.to_numeric(sub["votos"])
        partials.append(sub.groupby(key, dropna=False)["votos"].sum())
    agg = pd.concat(partials).groupby(level=key).sum().reset_index()
    agg["codigo_localidad"] = agg["zona"].astype(int).astype(str).str.zfill(2)
    # el campo partido del ESCRUTINIO viene a 4 dígitos, pero PARTIDOS/CANDIDATOS lo indexan a 5
    agg["partido"] = agg["partido"].str.zfill(5)
    return agg.drop(columns="zona")


def _with_nombres(agg, divipol, partidos, candidatos):
    """Pega nombre de puesto (por código exacto, mismo archivo DIVIPOL de la
    elección), nombre de partido y nombre de candidato/voto especial. Devuelve
    solo columnas legibles (los códigos de partido/candidato se descartan)."""
    df = agg.merge(divipol[["codigo_localidad", "puesto", "nombre_puesto", "localidad"]],
                    on=["codigo_localidad", "puesto"], how="left")
    df = df.merge(candidatos, on=["partido", "candidato"], how="left")
    especial = df["candidato"].map(SPECIAL_CANDIDATOS)
    df["nombre_candidato"] = df["nombre_candidato"].where(df["nombre_candidato"].notna(), especial)
    df["nombre_partido"] = df["partido"].map(partidos).fillna("")
    df = df.drop(columns=["partido", "candidato"])
    return df.rename(columns={"nombre_partido": "partido", "nombre_candidato": "candidato"})


def presidenciales_2026():
    outer_path = f"{DATA_DIR}/MMV_Presidente1V_2026.zip"
    basicos_path = "MMV_Presidente1V_2026/MMV_Presidente1V_2026/ARCHIVOSBASICOS_AUDITORES_PRESIDENTE_2026_V3.zip"
    divipol = _parse_divipol(_read_zip_entry(outer_path, basicos_path, "DIVIPOL_"))
    partidos = _parse_partidos(_read_zip_entry(outer_path, basicos_path, "PARTIDOS_"))
    candidatos = _parse_candidatos(_read_zip_entry(outer_path, basicos_path, "CANDIDATOS_"))

    outer = zipfile.ZipFile(outer_path)
    csv_name = "MMV_Presidente1V_2026/MMV_Presidente1V_2026/_ficheros_MMV_4_MMV_9999_ESCRUTINIO.csv"
    with outer.open(csv_name) as stream:
        agg = _escrutinio_bogota(stream, corporaciones={"001"})

    df = _with_nombres(agg, divipol, partidos, candidatos)
    df = df[["codigo_localidad", "localidad", "puesto", "nombre_puesto", "partido", "candidato", "votos"]]
    return df.sort_values(["codigo_localidad", "puesto", "votos"], ascending=[True, True, False])


CONGRESO_CORPORACIONES = {"002": "Camara", "001": "Senado"}


def congreso_2026_todas():
    """Cámara y Senado 2026 en una sola pasada del CSV nacional de escrutinio
    (9.75GB descomprimidos) -- leerlo dos veces (una por corporación) dobla un
    proceso que ya toma ~4 minutos. Devuelve {"Camara": df, "Senado": df}."""
    outer_path = f"{DATA_DIR}/MMV_CONGRESO_2026.zip"
    basicos_path = "MMV_CONGRESO_2026/ArchivosBasicosDiaElectoralCOngreso2026.zip"
    divipol = _parse_divipol(_read_zip_entry(outer_path, basicos_path, "DIVIPOL_"))
    partidos = _parse_partidos(_read_zip_entry(outer_path, basicos_path, "PARTIDOS_"))
    candidatos = _parse_candidatos(_read_zip_entry(outer_path, basicos_path, "CANDIDATOS_"))

    # mmvESCRUTINIOCongreso2026.zip es un zip dentro del zip (necesita ser un
    # archivo real en disco para poder abrirlo como zip, no cabe en memoria).
    outer = zipfile.ZipFile(outer_path)
    with tempfile.NamedTemporaryFile(suffix=".zip") as tmp:
        with outer.open("MMV_CONGRESO_2026/mmvESCRUTINIOCongreso2026.zip") as src:
            shutil.copyfileobj(src, tmp)
        tmp.flush()
        inner = zipfile.ZipFile(tmp.name)
        with inner.open("MMV_9999.csv") as stream:
            agg = _escrutinio_bogota(stream, corporaciones=set(CONGRESO_CORPORACIONES))

    resultado = {}
    for codigo, nombre in CONGRESO_CORPORACIONES.items():
        sub = agg[agg["corporacion"] == codigo].drop(columns="corporacion")
        df = _with_nombres(sub, divipol, partidos, candidatos)
        df = df[["codigo_localidad", "localidad", "puesto", "nombre_puesto", "partido", "candidato", "votos"]]
        resultado[nombre] = df.sort_values(["codigo_localidad", "puesto", "votos"], ascending=[True, True, False])
    return resultado


def divipole_censo_2026_bogota():
    """Censo de la Presidencial 2026, usado como proxy del censo de
    Territoriales 2023: la Registraduría no publicó un DIVIPOLE para esa
    elección en estos archivos. El censo de Bogotá cambia poco de una
    elección a otra, así que sirve para estimar participación/abstención
    aunque no sea el censo exacto de 2023."""
    outer_path = f"{DATA_DIR}/MMV_Presidente1V_2026.zip"
    basicos_path = "MMV_Presidente1V_2026/MMV_Presidente1V_2026/ARCHIVOSBASICOS_AUDITORES_PRESIDENTE_2026_V3.zip"
    df = _parse_divipol(_read_zip_entry(outer_path, basicos_path, "DIVIPOL_"))
    key = ["codigo_localidad", "nombre_puesto"]
    return df.groupby(key, as_index=False)[["censo_mujeres", "censo_hombres", "censo_total", "mesas"]].sum()


def divipole_censo_congreso_2026_bogota():
    """Censo propio de Congreso 2026 (su DIVIPOL es un archivo aparte del de
    Presidencial, aunque del mismo año) -- usado para participación/abstención
    de Cámara/Senado 2026."""
    outer_path = f"{DATA_DIR}/MMV_CONGRESO_2026.zip"
    basicos_path = "MMV_CONGRESO_2026/ArchivosBasicosDiaElectoralCOngreso2026.zip"
    df = _parse_divipol(_read_zip_entry(outer_path, basicos_path, "DIVIPOL_"))
    key = ["codigo_localidad", "nombre_puesto"]
    return df.groupby(key, as_index=False)[["censo_mujeres", "censo_hombres", "censo_total", "mesas"]].sum()


def puestos_votacion_geo():
    return load_puestos()  # toda la ciudad


def main():
    exports = {
        "presidenciales_2022_bogota": {"Resultados": presidenciales_2022()},
        "territoriales_2023_bogota": {
            "Alcaldia": territoriales_2023("ALCALDE"),
            "Concejo": territoriales_2023("CONCEJO"),
            "JAL": territoriales_2023("JAL"),
        },
        "divipole_censo_2022_bogota": {"Censo_Puestos": divipole_censo_bogota()},
        "divipole_censo_2026_bogota": {"Censo_Puestos": divipole_censo_2026_bogota()},
        "divipole_censo_congreso_2026_bogota": {"Censo_Puestos": divipole_censo_congreso_2026_bogota()},
        "presidenciales_2026_bogota": {"Resultados": presidenciales_2026()},
        "puestos_votacion_geo": {"Puestos": puestos_votacion_geo()},
    }

    for filename, sheets in exports.items():
        path = f"{OUT_DIR}/{filename}.xlsx"
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            for sheet_name, df in sheets.items():
                df.to_excel(writer, sheet_name=sheet_name, index=False)
        print(f"OK -> {path}")
        for sheet_name, df in sheets.items():
            print(f"  {sheet_name}: {len(df)} filas")

    # Congreso (Cámara/Senado con voto preferente) supera el límite de filas
    # por hoja de Excel (~1M) -- se exporta a CSV, como dataset_elecciones_largo.
    for corporacion, df in congreso_2026_todas().items():
        path = f"{OUT_DIR}/congreso_2026_{corporacion.lower()}_bogota.csv"
        df.to_csv(path, index=False)
        print(f"OK -> {path} ({len(df)} filas)")


if __name__ == "__main__":
    main()
