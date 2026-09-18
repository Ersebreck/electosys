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

# Etiqueta de PH por elección/corporación, ya normalizada (sin tildes, mayúsculas)
# porque el archivo de territoriales 2023 mezcla 'PACTO HISTORICO'/'PACTO HISTÓRICO'
# según la corporación (ver notas en ph_bosa.py sobre Alcaldía con nombre distinto).
PH_LABEL_NORM = {
    "Presidencial 2022": norm_key("MOVIMIENTO POLÍTICO PACTO HISTÓRICO"),
    "Alcaldía 2023": norm_key("PACTO HISTÓRICO BOGOTÁ"),
    "Concejo 2023": norm_key("PACTO HISTÓRICO"),
    "JAL 2023": norm_key("PACTO HISTÓRICO"),
}


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

    partido_norm = long_df["partido"].map(norm_key)
    ph_target_norm = long_df["eleccion"].map(PH_LABEL_NORM)
    ph_rows = long_df[partido_norm == ph_target_norm]
    ph = ph_rows.groupby(["eleccion", "codigo_localidad", "nombre_puesto"])["votos"].sum().rename("votos_ph")

    summary = total.merge(ph, on=["eleccion", "codigo_localidad", "nombre_puesto"], how="left")
    summary["votos_ph"] = summary["votos_ph"].fillna(0).astype(int)
    summary["pct_ph"] = (summary["votos_ph"] * 100 / summary["votos_totales"]).round(2)
    return merge_with_geo(summary, geo)


def main():
    geo = load_puestos()
    long_df = build_long_table()
    long_df.to_csv("output/files/dataset_elecciones_largo.csv", index=False)

    summary = build_puesto_summary(long_df, geo)
    summary.to_csv(OUT_PATH, index=False)

    print(f"OK -> output/files/dataset_elecciones_largo.csv ({len(long_df)} filas, todos los partidos)")
    print(f"OK -> {OUT_PATH} ({len(summary)} filas, resumen PH por puesto)")
    for eleccion, g in summary.groupby("eleccion"):
        print(f"  {eleccion}: {len(g)} puestos, {g['latitud'].isna().sum()} sin geometría, "
              f"{int(g['votos_ph'].sum())} votos PH")


if __name__ == "__main__":
    main()
