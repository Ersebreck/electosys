"""
Procesa el ZIP crudo de 2019 (Alcaldía de Bogotá) y lo integra a los datasets
existentes (dataset_elecciones.csv y dataset_elecciones_largo.csv).

El archivo MMV_TERRITORIALES2019_BOGOTÁ.zip contiene el CSV original de 395MB.
"""
import pandas as pd
import zipfile
import sys

sys.path.insert(0, "src/processing")
from geo_utils import load_puestos

KEY = ["eleccion", "codigo_localidad", "nombre_puesto"]


def process_2019():
    print("Leyendo ZIP de 2019...")
    with zipfile.ZipFile('/home/moribundo/Descargas/MMV_TERRITORIALES2019_BOGOTÁ.zip', 'r') as z:
        csv_name = [n for n in z.namelist() if n.endswith('.csv')][0]
        print(f"  CSV interno: {csv_name}")
        with z.open(csv_name) as f:
            df = pd.read_csv(f, dtype=str)

    df["Total Votos"] = pd.to_numeric(df["Total Votos"])

    # Agregar a nivel puesto x partido (sin mesa)
    key = ["Código Zona", "Código Puesto", "Nombre Puesto", "Código Comuna",
           "Nombre Comuna", "Nombre Partido", "Nombre Candidato"]
    agg = df.groupby(key, dropna=False)["Total Votos"].sum().reset_index()

    agg = agg.rename(columns={
        "Código Zona": "codigo_localidad",
        "Código Puesto": "puesto",
        "Nombre Puesto": "nombre_puesto",
        "Código Comuna": "codigo_localidad_alt",
        "Nombre Comuna": "localidad",
        "Nombre Partido": "partido",
        "Nombre Candidato": "candidato",
        "Total Votos": "votos",
    })

    agg["codigo_localidad"] = agg["codigo_localidad"].str.zfill(2)
    agg["eleccion"] = "Alcaldía 2019"

    agg = agg[["eleccion", "codigo_localidad", "localidad", "puesto",
               "nombre_puesto", "partido", "candidato", "votos"]]

    print(f"  Filas agregadas: {len(agg)}")
    print(f"  Partidos: {agg['partido'].nunique()}")
    print(f"  Puestos: {agg.groupby(['eleccion', 'codigo_localidad', 'nombre_puesto']).ngroups}")

    return agg


def build_resumen_2019(largo_2019):
    """Construye el resumen por puesto (votos totales, PH, etc.) para 2019."""
    tot = (
        largo_2019.groupby(["eleccion", "codigo_localidad", "localidad", "puesto", "nombre_puesto"], as_index=False)["votos"]
        .sum()
        .rename(columns={"votos": "votos_totales"})
    )

    ph = largo_2019[largo_2019["partido"].str.contains("PACTO", case=False, na=False)]
    ph_agg = (
        ph.groupby(["eleccion", "codigo_localidad", "nombre_puesto"], as_index=False)["votos"]
        .sum()
        .rename(columns={"votos": "votos_ph"})
    )

    resumen = tot.merge(ph_agg, on=["eleccion", "codigo_localidad", "nombre_puesto"], how="left")
    resumen["votos_ph"] = resumen["votos_ph"].fillna(0).astype(int)
    resumen["pct_ph"] = (resumen["votos_ph"] * 100 / resumen["votos_totales"]).round(2)

    print("  Cargando geometría de puestos...")
    geo = pd.read_excel("output/files/puestos_votacion_geo.xlsx")

    resumen["nombre_puesto_norm"] = resumen["nombre_puesto"].str.strip().str.upper()
    geo["nombre_puesto_norm"] = geo["nombre_puesto"].str.strip().str.upper()

    geo_cols = ["nombre_puesto_norm", "latitud", "longitud", "sitio_oficial", "direccion"]
    resumen = resumen.merge(
        geo[geo_cols].drop_duplicates("nombre_puesto_norm"),
        on="nombre_puesto_norm",
        how="left",
    )

    print("  Usando censo proxy de 2022...")
    censo_2022 = pd.read_excel("output/files/divipole_censo_2022_bogota.xlsx")
    censo_2022["nombre_puesto_norm"] = censo_2022["nombre_puesto"].str.strip().str.upper()

    resumen = resumen.merge(
        censo_2022[["nombre_puesto_norm", "censo_total"]].drop_duplicates("nombre_puesto_norm"),
        on="nombre_puesto_norm",
        how="left",
    ).drop(columns=["nombre_puesto_norm"])

    resumen["participacion_pct"] = (resumen["votos_totales"] * 100 / resumen["censo_total"]).round(2)
    resumen["abstencion_pct"] = (100 - resumen["participacion_pct"]).round(2)

    resumen = resumen[["eleccion", "codigo_localidad", "localidad", "nombre_puesto",
                       "votos_totales", "votos_ph", "pct_ph", "sitio_oficial", "direccion",
                       "latitud", "longitud", "censo_total", "participacion_pct", "abstencion_pct"]]

    return resumen


def main():
    largo_2019 = process_2019()
    resumen_2019 = build_resumen_2019(largo_2019)

    print("Cargando datasets existentes...")
    resumen_existente = pd.read_csv("output/files/dataset_elecciones.csv", dtype={"codigo_localidad": str, "puesto": str})
    largo_existente = pd.read_csv("output/files/dataset_elecciones_largo.csv", dtype={"codigo_localidad": str, "puesto": str})

    if "Alcaldía 2019" in resumen_existente["eleccion"].values:
        print("  Alcaldía 2019 ya existe en el resumen, omitiendo...")
    else:
        resumen_nuevo = pd.concat([resumen_existente, resumen_2019], ignore_index=True)
        resumen_nuevo.to_csv("output/files/dataset_elecciones.csv", index=False)
        print(f"  Resumen actualizado: {len(resumen_nuevo)} filas")

    if "Alcaldía 2019" in largo_existente["eleccion"].values:
        print("  Alcaldía 2019 ya existe en el largo, omitiendo...")
    else:
        largo_nuevo = pd.concat([largo_existente, largo_2019], ignore_index=True)
        largo_nuevo.to_csv("output/files/dataset_elecciones_largo.csv", index=False)
        print(f"  Largo actualizado: {len(largo_nuevo)} filas")

    print("\n¡2019 integrado exitosamente!")


if __name__ == "__main__":
    main()
