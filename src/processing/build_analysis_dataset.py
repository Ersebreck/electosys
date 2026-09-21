"""
Junta las 4 elecciones (Presidencial 2022, Alcaldía/Concejo/JAL 2023) en una
sola tabla larga: eleccion x localidad x puesto x partido x votos, con lat/lon
pegada por nombre de puesto (ver geo_utils). Esta es la tabla que consume la
app de Streamlit para mapas, barras, slope chart y dispersión.

Reusa los excels ya generados por export_sources.py en vez de releer los CSV
crudos otra vez.

Salida: output/files/dataset_elecciones.csv
"""
import pandas as pd

from geo_utils import load_puestos, merge_with_geo, norm_key

OUT_PATH = "output/files/dataset_elecciones.csv"

# Presidencial 2022 tiene un solo partido nacional, match exacto.
# Territoriales 2023: cada corporación (y en JAL, cada localidad) registró la
# coalición de PH con un nombre distinto -- 'PACTO HISTÓRICO', 'PACTO HISTÓRICO
# BOGOTÁ', 'PACTO HISTÓRICO COLOMBIA PUEDE', 'COALICIÓN PACTO HISTÓRICO',
# 'COALICIÓN PACTO POR USME' (confirmado que también es PH), etc.
# Match: contiene "PACTO" (sin tildes) como subcadena -- se revisó el listado
# completo de partidos de territoriales 2023 y todos los que contienen "PACTO"
# son variantes de esta misma coalición.
PH_PRESIDENCIAL_EXACTO = norm_key("MOVIMIENTO POLÍTICO PACTO HISTÓRICO")
PH_TERRITORIAL_SUBSTRING = norm_key("PACTO")


def ph_mask(long_df):
    partido_norm = long_df["partido"].map(norm_key)
    es_presidencial = long_df["eleccion"] == "Presidencial 2022"
    return (es_presidencial & (partido_norm == PH_PRESIDENCIAL_EXACTO)) | (
        ~es_presidencial & partido_norm.str.contains(PH_TERRITORIAL_SUBSTRING, regex=False)
    )


def load_election(eleccion, path, sheet):
    df = pd.read_excel(path, sheet_name=sheet)
    df["eleccion"] = eleccion
    df["codigo_localidad"] = df["codigo_localidad"].astype(str).str.zfill(2)
    return df[["eleccion", "codigo_localidad", "localidad", "puesto", "nombre_puesto", "partido", "votos"]]


def build_long_table():
    frames = [
        load_election("Presidencial 2022", "output/files/presidenciales_2022_bogota.xlsx", "Resultados"),
        load_election("Alcaldía 2023", "output/files/territoriales_2023_bogota.xlsx", "Alcaldia"),
        load_election("Concejo 2023", "output/files/territoriales_2023_bogota.xlsx", "Concejo"),
        load_election("JAL 2023", "output/files/territoriales_2023_bogota.xlsx", "JAL"),
    ]
    return pd.concat(frames, ignore_index=True)


def build_puesto_summary(long_df, geo):
    """Un renglón por (eleccion, puesto): votos totales, votos PH, % PH, lat/lon."""
    total = long_df.groupby(["eleccion", "codigo_localidad", "localidad", "nombre_puesto"])["votos"].sum()
    total = total.rename("votos_totales").reset_index()

    ph_rows = long_df[ph_mask(long_df)]
    ph = ph_rows.groupby(["eleccion", "codigo_localidad", "nombre_puesto"])["votos"].sum().rename("votos_ph")

    summary = total.merge(ph, on=["eleccion", "codigo_localidad", "nombre_puesto"], how="left")
    summary["votos_ph"] = summary["votos_ph"].fillna(0).astype(int)
    summary["pct_ph"] = (summary["votos_ph"] * 100 / summary["votos_totales"]).round(2)
    return merge_with_geo(summary, geo)


def add_participacion(summary):
    """Suma columnas censo_total / participacion_pct / abstencion_pct.

    Presidencial 2022 usa su propio censo (divipole_censo_2022_bogota, único
    censo real que tenemos). Territoriales 2023 no tiene censo publicado en
    los archivos de la Registraduría, así que se usa como proxy el censo de
    la Presidencial 2026 (divipole_censo_2026_bogota) -- el censo de Bogotá
    varía poco de una elección a otra.
    """
    censo_2022 = pd.read_excel("output/files/divipole_censo_2022_bogota.xlsx")
    censo_2022["_key"] = censo_2022["nombre_puesto"].map(norm_key)
    censo_2022 = censo_2022[["_key", "censo_total"]]

    censo_terr = pd.read_excel("output/files/divipole_censo_2026_bogota.xlsx")
    censo_terr["_key"] = (
        censo_terr["codigo_localidad"].astype(str).str.zfill(2) + "|" + censo_terr["nombre_puesto"].map(norm_key)
    )
    censo_terr = censo_terr[["_key", "censo_total"]]

    pres = summary[summary["eleccion"] == "Presidencial 2022"].copy()
    pres["_key"] = pres["nombre_puesto"].map(norm_key)
    pres = pres.merge(censo_2022, on="_key", how="left").drop(columns="_key")

    terr = summary[summary["eleccion"] != "Presidencial 2022"].copy()
    terr["_key"] = terr["codigo_localidad"] + "|" + terr["nombre_puesto"].map(norm_key)
    terr = terr.merge(censo_terr, on="_key", how="left").drop(columns="_key")

    out = pd.concat([pres, terr], ignore_index=True)
    out["participacion_pct"] = (out["votos_totales"] * 100 / out["censo_total"]).round(2)
    out["abstencion_pct"] = (100 - out["participacion_pct"]).round(2)
    return out


def main():
    geo = load_puestos()
    long_df = build_long_table()
    long_df.to_csv("output/files/dataset_elecciones_largo.csv", index=False)

    summary = build_puesto_summary(long_df, geo)
    summary = add_participacion(summary)
    summary.to_csv(OUT_PATH, index=False)

    print(f"OK -> output/files/dataset_elecciones_largo.csv ({len(long_df)} filas, todos los partidos)")
    print(f"OK -> {OUT_PATH} ({len(summary)} filas, resumen PH por puesto)")
    for eleccion, g in summary.groupby("eleccion"):
        print(f"  {eleccion}: {len(g)} puestos, {g['latitud'].isna().sum()} sin geometría, "
              f"{g['censo_total'].isna().sum()} sin censo, {int(g['votos_ph'].sum())} votos PH")


if __name__ == "__main__":
    main()
