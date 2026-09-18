"""
Electosys - resultados electorales Bogotá (Presidencial 2022, Territoriales 2023).
Consume los datasets ya procesados en output/ (ver src/processing/*.py).
"""
import json
import sys

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, "src/processing")
from geo_utils import norm_key  # noqa: E402

st.set_page_config(page_title="Electosys Bogotá", layout="wide")

BOGOTA_CENTER = {"lat": 4.65, "lon": -74.1}
BOSA_CENTER = {"lat": 4.616, "lon": -74.19}
BOSA_CODIGO_LOCALIDAD = "07"
ELECCIONES = ["Presidencial 2022", "Alcaldía 2023", "Concejo 2023", "JAL 2023"]


@st.cache_data
def load_data():
    resumen = pd.read_csv("output/files/dataset_elecciones.csv", dtype={"codigo_localidad": str})
    largo = pd.read_csv("output/files/dataset_elecciones_largo.csv", dtype={"codigo_localidad": str})
    with open("output/maps/localidades.geojson", encoding="utf-8") as f:
        geojson = json.load(f)
    censo = pd.read_excel("output/files/divipole_censo_2022_bogota.xlsx")
    censo["_key"] = censo["nombre_puesto"].map(norm_key)
    return resumen, largo, geojson, censo


resumen, largo, geojson, censo = load_data()


def with_porcentaje(df):
    df = df.copy()
    df["Porcentaje"] = df["pct_ph"].map(lambda v: f"{v:.1f} %")
    return df

st.title("Electosys")
st.caption("Sistema de Análisis de Elecciones — resultados Pacto Histórico en Bogotá")
st.caption("Presidencial 2022 y Territoriales 2023 (Alcaldía/Concejo/JAL). Cámara, Senado y "
           "Consejos de Juventud pendientes (sin archivo fuente todavía).")

with st.sidebar:
    eleccion = st.radio("Elección", ELECCIONES, index=0)
    localidades_disp = sorted(resumen["localidad"].dropna().unique())
    localidades_sel = st.multiselect("Localidad", localidades_disp, default=localidades_disp)

df = resumen[(resumen["eleccion"] == eleccion) & (resumen["localidad"].isin(localidades_sel))]
df_geo = df.dropna(subset=["latitud", "longitud"])
long_sel = largo[(largo["eleccion"] == eleccion) & (largo["localidad"].isin(localidades_sel))]

tab_puntos, tab_bosa, tab_localidad, tab_barras, tab_dispersion = st.tabs(
    ["Mapa de puntos", "Mapa Bosa", "Mapa por localidad", "Partidos", "Dispersión"]
)

with tab_puntos:
    st.caption(f"{len(df_geo)} de {len(df)} puestos con coordenada "
               f"({len(df) - len(df_geo)} sin match de geometría — ver Notas).")
    fig = px.scatter_map(
        with_porcentaje(df_geo), lat="latitud", lon="longitud", size="votos_ph", color="pct_ph",
        hover_name="nombre_puesto",
        hover_data={"votos_ph": True, "votos_totales": True, "pct_ph": False, "Porcentaje": True,
                    "latitud": False, "longitud": False},
        color_continuous_scale="RdYlGn", size_max=22, zoom=10, center=BOGOTA_CENTER,
        height=650,
    )
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0))
    st.plotly_chart(fig, use_container_width=True)

with tab_bosa:
    df_bosa = resumen[(resumen["eleccion"] == eleccion) & (resumen["codigo_localidad"] == BOSA_CODIGO_LOCALIDAD)]
    df_bosa_geo = df_bosa.dropna(subset=["latitud", "longitud"])
    st.caption(f"{len(df_bosa_geo)} de {len(df_bosa)} puestos de Bosa con coordenada.")
    fig = px.scatter_map(
        with_porcentaje(df_bosa_geo), lat="latitud", lon="longitud", size="votos_ph", color="pct_ph",
        hover_name="nombre_puesto",
        hover_data={"votos_ph": True, "votos_totales": True, "pct_ph": False, "Porcentaje": True,
                    "latitud": False, "longitud": False},
        color_continuous_scale="RdYlGn", size_max=28, zoom=12.5, center=BOSA_CENTER,
        height=650,
    )
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0))
    st.plotly_chart(fig, use_container_width=True)

with tab_localidad:
    agg = df.groupby(["codigo_localidad", "localidad"], as_index=False)[["votos_ph", "votos_totales"]].sum()
    agg["pct_ph"] = (agg["votos_ph"] * 100 / agg["votos_totales"]).round(2)
    fig = px.choropleth_map(
        with_porcentaje(agg), geojson=geojson, locations="codigo_localidad",
        featureidkey="properties.codigo_localidad", color="pct_ph",
        hover_name="localidad",
        hover_data={"votos_ph": True, "votos_totales": True, "pct_ph": False, "Porcentaje": True,
                    "codigo_localidad": False},
        color_continuous_scale="RdYlGn", zoom=9.5, center=BOGOTA_CENTER, height=650, opacity=0.8,
    )
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0))
    st.plotly_chart(fig, use_container_width=True)

with tab_barras:
    top_n = st.slider("Top N partidos", 5, 20, 10)
    top = long_sel.groupby("partido", as_index=False)["votos"].sum().sort_values("votos", ascending=False).head(top_n)
    fig = px.bar(top, x="votos", y="partido", orientation="h",
                 title=f"Votos por partido — {eleccion}", height=500)
    fig.update_layout(yaxis=dict(categoryorder="total ascending"))
    st.plotly_chart(fig, use_container_width=True)

with tab_dispersion:
    if eleccion == "Presidencial 2022":
        d = df.copy()
        d["_key"] = d["nombre_puesto"].map(norm_key)
        d = d.merge(censo[["_key", "censo_total"]], on="_key", how="inner")
        d["participacion_pct"] = (d["votos_totales"] * 100 / d["censo_total"]).round(2)
        x_col, x_label = "participacion_pct", "% participación (votos / censo)"
    else:
        d = df.copy()
        x_col, x_label = "votos_totales", "Votos totales del puesto (no hay censo 2023 disponible)"

    fig = px.scatter(
        d, x=x_col, y="pct_ph", hover_name="nombre_puesto", hover_data=["localidad"],
        labels={x_col: x_label, "pct_ph": "% voto PH"}, height=550,
        title=f"% voto PH vs. {x_label} — {eleccion}",
    )
    st.plotly_chart(fig, use_container_width=True)

with st.expander("Notas y limitaciones"):
    st.markdown("""
- **Cámara, Senado y Consejos de Juventud**: sin archivo fuente en `data/`, no incluidos.
- **Geometría**: se une por nombre de puesto normalizado (el número de puesto del gpkg de IDECA no
  coincide con el código de puesto de la Registraduría). ~10-15% de los puestos no tienen coordenada
  porque son sitios nuevos/renombrados que el gpkg no tiene.
- **Alcaldía 2023**: PH corrió bajo la marca "PACTO HISTÓRICO BOGOTÁ", distinta de "PACTO HISTÓRICO"
  usado en Concejo/JAL — cada corporación usa su propia etiqueta exacta.
- **Participación real (% sobre censo)** solo está disponible para Presidencial 2022 (único censo que
  tenemos, `DIVIPOLE_PRESIDENTE_31_MAYO.csv`); para 2023 se usa el total de votos del puesto como proxy.
""")
