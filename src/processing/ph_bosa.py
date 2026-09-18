"""
Resultados del Pacto Histórico (PH) en Bosa por puesto de votación.

Cubre lo que hay datos para hoy: Presidenciales 2022 y Territoriales 2023
(Alcaldía, Concejo, JAL). Cámara, Senado y Consejos de Juventud quedan fuera
hasta que se agreguen esos CSV a data/ (mismo formato MMV/DIVIPOLE).

Salida: output/PH_Bosa_resultados.xlsx, una hoja por elección/corporación.
"""
import pandas as pd

from geo_utils import DATA_DIR, load_puestos, merge_with_geo, strip_accents

OUT_PATH = "output/files/PH_Bosa_resultados.xlsx"

BOSA_LOCALIDAD_CODE = "07"       # gpkg / presidenciales ZONA
BOSA_COMUNA_LABEL = "LOCALIDAD 7 BOSA"  # territoriales 2023 "Nombre Comuna"

PH_PRESIDENCIALES = "MOVIMIENTO POLÍTICO PACTO HISTÓRICO"
# Match exacto (tras quitar tildes/mayúsculas) por corporación: en Alcaldía la
# coalición de PH se registró bajo un nombre distinto al de Concejo/JAL.
PH_TERRITORIALES_NORM = {
    "CONCEJO": "PACTO HISTORICO",
    "JAL": "PACTO HISTORICO",
    "ALCALDE": "PACTO HISTORICO BOGOTA",
}


def presidenciales_2022(geo_bosa):
    df = pd.read_csv(
        f"{DATA_DIR}/MMV_XXX_16_001_XXX_XX_XX_XXX_2558.csv",
        sep=";",
        dtype=str,
        usecols=["ZONA", "PUESNOMBRE", "PARNOMBRE", "VOTOS"],
    )
    df = df[df["ZONA"] == BOSA_LOCALIDAD_CODE].copy()
    df["VOTOS"] = pd.to_numeric(df["VOTOS"])

    total = df.groupby("PUESNOMBRE")["VOTOS"].sum().rename("votos_totales")
    ph = (
        df[df["PARNOMBRE"] == PH_PRESIDENCIALES]
        .groupby("PUESNOMBRE")["VOTOS"]
        .sum()
        .rename("votos_ph")
    )

    result = total.to_frame().join(ph, how="left").reset_index()
    result["votos_ph"] = result["votos_ph"].fillna(0).astype(int)
    result["codigo_localidad"] = BOSA_LOCALIDAD_CODE
    result = merge_with_geo(result, geo_bosa, puesto_col="PUESNOMBRE")
    result["pct_ph"] = (result["votos_ph"] * 100 / result["votos_totales"]).round(2)
    return result[["PUESNOMBRE", "votos_ph", "votos_totales", "pct_ph", "latitud", "longitud"]].rename(
        columns={"PUESNOMBRE": "nombre_puesto"}
    )


def territoriales_2023(geo_bosa, corporacion):
    chunks = pd.read_csv(
        f"{DATA_DIR}/MMV_2023_16_BOGOTA DC.csv",
        dtype=str,
        usecols=[
            "Nombre Puesto", "Nombre Comuna",
            "Nombre Corporación", "Nombre Partido", "Total Votos",
        ],
        chunksize=200_000,
    )
    frames = [c[(c["Nombre Comuna"] == BOSA_COMUNA_LABEL) & (c["Nombre Corporación"] == corporacion)] for c in chunks]
    df = pd.concat(frames, ignore_index=True)
    df["Total Votos"] = pd.to_numeric(df["Total Votos"])
    df["partido_norm"] = df["Nombre Partido"].map(strip_accents).str.upper()

    total = df.groupby("Nombre Puesto")["Total Votos"].sum().rename("votos_totales")
    ph = (
        df[df["partido_norm"] == PH_TERRITORIALES_NORM[corporacion]]
        .groupby("Nombre Puesto")["Total Votos"]
        .sum()
        .rename("votos_ph")
    )

    result = total.to_frame().join(ph, how="left").reset_index()
    result["votos_ph"] = result["votos_ph"].fillna(0).astype(int)
    result["codigo_localidad"] = BOSA_LOCALIDAD_CODE
    result = merge_with_geo(result, geo_bosa, puesto_col="Nombre Puesto")
    result["pct_ph"] = (result["votos_ph"] * 100 / result["votos_totales"]).round(2)
    return result[["Nombre Puesto", "votos_ph", "votos_totales", "pct_ph", "latitud", "longitud"]].rename(
        columns={"Nombre Puesto": "nombre_puesto"}
    )


NOTAS = pd.DataFrame({
    "Nota": [
        "Presidenciales 2022: coincide con el 1er round (total PH en Bogotá ~1.7M votos, consistente con el resultado real de Petro). "
        "El campo CANNOMBRE del archivo fuente trae mal el nombre de candidato (dice 'IVÁN CEPEDA CASTRO'); no afecta el total por partido usado aquí.",
        "Territoriales 2023: match exacto (sin tildes/mayúsculas) por corporación: 'PACTO HISTÓRICO' en Concejo y JAL, "
        "'PACTO HISTÓRICO BOGOTÁ' en Alcaldía (la coalición de Bolívar se registró con ese nombre distinto). "
        "Otras variantes como 'PACTO HISTORICO COLOMBIA PUEDE' o 'COALICIÓN PACTO POR USME' siguen excluidas.",
        "Cámara, Senado y Consejos de Juventud: NO incluidos, no hay archivo fuente en data/ para esas elecciones todavía.",
        "Geometría (lat/lon): se une por nombre de puesto normalizado (el número de puesto del gpkg no coincide "
        "con el de la Registraduría). ~10-15% de los puestos no tienen match porque son sitios nuevos/renombrados "
        "que el gpkg no tiene; esas filas quedan con lat/lon vacío.",
    ]
})


def main():
    geo_bosa = load_puestos(BOSA_LOCALIDAD_CODE)

    sheets = {
        "Presidenciales_2022": presidenciales_2022(geo_bosa),
        "Concejo_2023": territoriales_2023(geo_bosa, "CONCEJO"),
        "JAL_2023": territoriales_2023(geo_bosa, "JAL"),
        "Alcaldia_2023": territoriales_2023(geo_bosa, "ALCALDE"),
    }

    with pd.ExcelWriter(OUT_PATH, engine="openpyxl") as writer:
        for name, df in sheets.items():
            df.sort_values("votos_ph", ascending=False).to_excel(writer, sheet_name=name, index=False)
        NOTAS.to_excel(writer, sheet_name="Notas", index=False)

    print(f"OK -> {OUT_PATH}")
    for name, df in sheets.items():
        print(f"  {name}: {len(df)} puestos, {df['votos_ph'].sum()} votos PH")


if __name__ == "__main__":
    main()
