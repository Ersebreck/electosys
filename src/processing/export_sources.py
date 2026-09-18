"""
Vuelca cada fuente cruda a un Excel, ciudad completa (todas las localidades),
agregado a nivel puesto x partido x candidato (sin mesa, para caber en una
hoja de Excel y quedar al grano correcto para el EDA).

Salida: output/files/<fuente>.xlsx
"""
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


if __name__ == "__main__":
    main()
