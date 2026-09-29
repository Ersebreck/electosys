"""
Electosys - resultados electorales Bogotá.
Pestañas por año -> capas por partido / total, por puesto y por localidad,
en modalidad cantidad y porcentaje. Sub-pestañas de histogramas y correlación.

Consume los datasets ya procesados en output/ (ver src/processing/*.py).
"""
import json
import sys

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, "src/processing")

st.set_page_config(page_title="Electosys Bogotá", layout="wide")

BOGOTA_CENTER = {"lat": 4.65, "lon": -74.1}

# Agrupación de elecciones por año con título descriptivo
ANOS = {
    "2019": {
        "elecciones": ["Alcaldía 2019"],
        "titulo": "Elecciones Territoriales — Alcaldía de Bogotá",
    },
    "2022": {
        "elecciones": ["Presidencial 2022"],
        "titulo": "Elecciones Presidenciales — Primera Vuelta",
    },
    "2023": {
        "elecciones": ["Alcaldía 2023", "Concejo 2023", "JAL 2023"],
        "titulo": "Elecciones Territoriales — Alcaldía, Concejo y JAL",
    },
    "2026": {
        "elecciones": ["Presidencial 2026", "Cámara 2026", "Senado 2026"],
        "titulo": "Elecciones Presidenciales y Congreso — Presidencial, Cámara y Senado",
    },
}

# Color: rojo = mayor intensidad, verde = menor intensidad
COLOR_SCALE = "Picnic"

# Llave de unión entre datasets
KEY = ["eleccion", "codigo_localidad", "nombre_puesto"]


@st.cache_data
def load_data():
    dtypes = {"codigo_localidad": str, "puesto": str}
    resumen = pd.read_csv("output/files/dataset_elecciones.csv", dtype=dtypes)
    largo = pd.read_csv("output/files/dataset_elecciones_largo.csv", dtype=dtypes)
    with open("output/maps/localidades.geojson", encoding="utf-8") as f:
        geojson = json.load(f)
    return resumen, largo, geojson


resumen, largo, geojson = load_data()


# ---------- Helpers -------------------------------------------------------

def format_pct(series):
    return series.map(lambda v: f"{v:.1f} %")


def get_partidos(df_largo):
    """Lista de partidos ordenados por votos totales descendente."""
    return (
        df_largo.groupby("partido")["votos"].sum().sort_values(ascending=False).index.tolist()
    )


def filter_elecciones(df, elecciones):
    return df[df["eleccion"].isin(elecciones)]


def build_puesto_data(df_resumen, df_largo, partido):
    """
    Devuelve DataFrame por puesto con votos del partido, totales y porcentaje.
    Si partido == 'TOTAL', usa votos_totales del resumen.
    """
    if partido == "TOTAL":
        d = df_resumen.copy()
        d["votos_partido"] = d["votos_totales"]
    else:
        lp = (
            df_largo[df_largo["partido"] == partido]
            .groupby(KEY, as_index=False)["votos"]
            .sum()
            .rename(columns={"votos": "votos_partido"})
        )
        d = df_resumen.merge(lp, on=KEY, how="left").fillna({"votos_partido": 0})
    d["pct"] = (d["votos_partido"] * 100 / d["votos_totales"]).round(2)
    return d


def build_localidad_data(df_resumen, df_largo, partido):
    """Agrega votos del partido y totales por localidad."""
    if partido == "TOTAL":
        agg = (
            df_resumen.groupby(["codigo_localidad", "localidad"], as_index=False)
            .agg(votos_partido=("votos_totales", "sum"), votos_totales=("votos_totales", "sum"))
        )
    else:
        lp = (
            df_largo[df_largo["partido"] == partido]
            .groupby(["codigo_localidad", "localidad"], as_index=False)["votos"]
            .sum()
            .rename(columns={"votos": "votos_partido"})
        )
        lt = (
            df_resumen.groupby(["codigo_localidad", "localidad"], as_index=False)["votos_totales"]
            .sum()
        )
        agg = lt.merge(lp, on=["codigo_localidad", "localidad"], how="left").fillna({"votos_partido": 0})
    agg["pct"] = (agg["votos_partido"] * 100 / agg["votos_totales"]).round(2)
    return agg


# ---------- UI ------------------------------------------------------------

st.title("Electosys")
st.caption("Sistema de Análisis de Elecciones — Bogotá por año, partido y nivel geográfico")

tabs_ano = st.tabs(list(ANOS.keys()))

for tab_ano, ano in zip(tabs_ano, ANOS.keys()):
    with tab_ano:
        info = ANOS[ano]
        elecciones = info["elecciones"]

        # Título descriptivo del año
        st.subheader(info["titulo"])

        # Si hay múltiples elecciones en el año, mostrar selector
        if len(elecciones) > 1:
            eleccion_sel = st.radio(
                "Elección",
                elecciones,
                horizontal=True,
                key=f"eleccion_{ano}",
            )
            elecciones_filtro = [eleccion_sel]
        else:
            elecciones_filtro = elecciones

        res_ano = filter_elecciones(resumen, elecciones_filtro)
        lar_ano = filter_elecciones(largo, elecciones_filtro)

        # Filtro de localidades
        localidades_disp = sorted(res_ano["localidad"].dropna().unique())
        localidades_sel = st.multiselect(
            "Filtrar localidades",
            localidades_disp,
            default=localidades_disp,
            key=f"localidades_{ano}",
        )

        res_ano = res_ano[res_ano["localidad"].isin(localidades_sel)]
        lar_ano = lar_ano[lar_ano["localidad"].isin(localidades_sel)]

        # Selector de partido (dropdown) + TOTAL
        partidos = get_partidos(lar_ano)
        partido_sel = st.selectbox(
            "Capa",
            ["TOTAL"] + partidos,
            key=f"partido_{ano}",
        )

        # Sub-pestañas dentro del año
        tab_mapas, tab_hist, tab_dist, tab_corr = st.tabs(
            ["Mapas", "Histogramas Top 5", "Distribución Top 5", "Correlación"]
        )

        # ----- MAPAS -----
        with tab_mapas:
            modo = st.radio(
                "Modalidad",
                ["Cantidad de votos", "Porcentaje (partido / total)"],
                horizontal=True,
                key=f"modo_{ano}",
            )
            col_mapa, col_puesto = st.columns([3, 3])

            # --- Choropleth por localidad ---
            with col_mapa:
                st.subheader("Por localidad")
                loc = build_localidad_data(res_ano, lar_ano, partido_sel)
                if modo == "Cantidad de votos":
                    color_col, color_label = "votos_partido", "Votos"
                else:
                    color_col, color_label = "pct", "% votos"

                fig = px.choropleth_map(
                    loc.assign(Pct=format_pct(loc["pct"])),
                    geojson=geojson,
                    locations="codigo_localidad",
                    featureidkey="properties.codigo_localidad",
                    color=color_col,
                    hover_name="localidad",
                    hover_data={
                        "votos_partido": True,
                        "votos_totales": True,
                        "pct": False,
                        "Pct": True,
                        "codigo_localidad": False,
                    },
                    color_continuous_scale=COLOR_SCALE,
                    zoom=9.5,
                    center=BOGOTA_CENTER,
                    height=550,
                    opacity=0.8,
                    labels={color_col: color_label, "votos_partido": "Votos",
                            "votos_totales": "Total votos"},
                )
                fig.update_layout(margin=dict(l=0, r=0, t=0, b=0))
                st.plotly_chart(fig, use_container_width=True, key=f"mapa_loc_{ano}")

            # --- Scatter por puesto de votación ---
            with col_puesto:
                st.subheader("Por puesto de votación")
                pue = build_puesto_data(res_ano, lar_ano, partido_sel)
                pue_geo = pue.dropna(subset=["latitud", "longitud"])
                sin_geo = len(pue) - len(pue_geo)
                st.caption(
                    f"{len(pue_geo)} de {len(pue)} puestos con coordenada"
                    + (f" ({sin_geo} sin match de geometría)." if sin_geo else ".")
                )

                if modo == "Cantidad de votos":
                    color_col, color_label = "votos_partido", "Votos"
                else:
                    color_col, color_label = "pct", "% votos"

                fig = px.scatter_map(
                    pue_geo.assign(Pct=format_pct(pue_geo["pct"])),
                    lat="latitud",
                    lon="longitud",
                    size="votos_totales",
                    color=color_col,
                    hover_name="nombre_puesto",
                    hover_data={
                        "votos_partido": True,
                        "votos_totales": True,
                        "pct": False,
                        "Pct": True,
                        "localidad": True,
                        "latitud": False,
                        "longitud": False,
                    },
                    color_continuous_scale=COLOR_SCALE,
                    size_max=25,
                    zoom=10,
                    center=BOGOTA_CENTER,
                    height=550,
                    labels={color_col: color_label, "votos_partido": "Votos",
                            "votos_totales": "Total votos"},
                )
                fig.update_layout(margin=dict(l=0, r=0, t=0, b=0))
                st.plotly_chart(fig, use_container_width=True, key=f"mapa_puesto_{ano}")

        # ----- HISTOGRAMAS TOP 5 -----
        with tab_hist:
            top5_bogota = (
                lar_ano.groupby("partido")["votos"].sum().sort_values(ascending=False).head(5).index.tolist()
            )
            col_bog, col_loc = st.columns(2)

            with col_bog:
                st.subheader("Top 5 — Bogotá")
                df_top_bog = lar_ano[lar_ano["partido"].isin(top5_bogota)]
                agg_bog = df_top_bog.groupby("partido")["votos"].sum().sort_values(ascending=False)
                fig = px.bar(
                    agg_bog.reset_index(),
                    x="votos",
                    y="partido",
                    orientation="h",
                    title=f"Top 5 partidos — Bogotá {ano}",
                    color="votos",
                    color_continuous_scale=COLOR_SCALE,
                    height=400,
                )
                fig.update_layout(yaxis=dict(categoryorder="total ascending"))
                st.plotly_chart(fig, use_container_width=True, key=f"hist_bog_{ano}")

            with col_loc:
                st.subheader("Top 5 — Por localidad")
                loc_sel = st.selectbox(
                    "Localidad",
                    sorted(res_ano["localidad"].dropna().unique()),
                    key=f"loc_hist_{ano}",
                )
                df_top_loc = lar_ano[
                    (lar_ano["partido"].isin(top5_bogota))
                    & (lar_ano["localidad"] == loc_sel)
                ]
                agg_loc = (
                    df_top_loc.groupby("partido")["votos"].sum().sort_values(ascending=False)
                )
                fig = px.bar(
                    agg_loc.reset_index(),
                    x="votos",
                    y="partido",
                    orientation="h",
                    title=f"Top 5 — {loc_sel} {ano}",
                    color="votos",
                    color_continuous_scale=COLOR_SCALE,
                    height=400,
                )
                fig.update_layout(yaxis=dict(categoryorder="total ascending"))
                st.plotly_chart(fig, use_container_width=True, key=f"hist_loc_{ano}")

        # ----- DISTRIBUCIÓN TOP 5 -----
        with tab_dist:
            st.subheader(f"Distribución Top 5 partidos por puesto — {ano}")
            st.caption(
                "Votos de los 5 partidos más votados en cada puesto de votación. "
                "Los puntos están unidos por líneas para facilitar la comparación."
            )
            top5_dist = (
                lar_ano.groupby("partido")["votos"].sum().sort_values(ascending=False).head(5).index.tolist()
            )
            # Pivot: filas = puesto, columnas = partidos
            piv_dist = (
                lar_ano[lar_ano["partido"].isin(top5_dist)]
                .groupby(KEY + ["partido"])["votos"]
                .sum()
                .unstack(fill_value=0)
            )
            # Agregar nombre de puesto para el eje X
            piv_dist = piv_dist.reset_index()
            piv_dist["puesto_label"] = piv_dist["nombre_puesto"]
            # Ordenar por votos totales para mejor visualización
            piv_dist["total"] = piv_dist[top5_dist].sum(axis=1)
            piv_dist = piv_dist.sort_values("total", ascending=True)

            # Crear gráfico de líneas con puntos
            fig = px.line(
                piv_dist,
                x="puesto_label",
                y=top5_dist,
                markers=True,
                title=f"Distribución Top 5 por puesto — {ano}",
                labels={"value": "Votos", "variable": "Partido", "puesto_label": "Puesto de votación"},
                height=600,
            )
            # Nombres de puestos verticales
            fig.update_layout(
                xaxis_tickangle=-90,
                legend_title_text="Partido",
                margin=dict(l=0, r=0, t=40, b=200),
            )
            st.plotly_chart(fig, use_container_width=True, key=f"dist_top5_{ano}")

        # ----- CORRELACIÓN -----
        with tab_corr:
            st.subheader(f"Correlación entre Top 5 partidos — {ano}")
            st.caption(
                "Matriz de correlación de votos por puesto entre los 5 partidos más votados, "
                "y correlación con la cantidad total de votos por puesto."
            )
            top5 = (
                lar_ano.groupby("partido")["votos"].sum().sort_values(ascending=False).head(5).index.tolist()
            )
            # Pivot: filas = puesto (eleccion+codigo_localidad+nombre_puesto), columnas = partidos
            piv = (
                lar_ano[lar_ano["partido"].isin(top5)]
                .groupby(KEY + ["partido"])["votos"]
                .sum()
                .unstack(fill_value=0)
            )
            # Votos totales por puesto
            tot = res_ano.groupby(KEY)["votos_totales"].sum().rename("TOTAL_VOTOS")
            piv = piv.join(tot, how="inner")

            corr = piv.corr().round(2)

            col_heat, col_text = st.columns([2, 3])

            with col_heat:
                fig = px.imshow(
                    corr,
                    text_auto=True,
                    color_continuous_scale="RdBu_r",
                    zmin=-1,
                    zmax=1,
                    title="Matriz de correlación (votos por puesto)",
                    height=450,
                )
                fig.update_layout(margin=dict(l=0, r=0, t=40, b=0))
                st.plotly_chart(fig, use_container_width=True, key=f"corr_heat_{ano}")

            with col_text:
                st.markdown("**Interpretación**")
                # Correlación con total de votos
                corr_total = corr["TOTAL_VOTOS"].drop("TOTAL_VOTOS").sort_values(ascending=False)
                st.write("**Correlación con votos totales por puesto:**")
                st.dataframe(corr_total.to_frame("corr"), use_container_width=True)

                # Correlaciones entre partidos (pares)
                st.write("**Correlaciones entre partidos (pares):**")
                pares = []
                for i in range(len(top5)):
                    for j in range(i + 1, len(top5)):
                        r = corr.loc[top5[i], top5[j]]
                        pares.append((top5[i], top5[j], r))
                pares.sort(key=lambda x: abs(x[2]), reverse=True)
                for a, b, r in pares[:5]:
                    st.write(f"- **{a}** vs **{b}**: {r:.2f}")

                # Análisis breve
                st.markdown("---")
                st.markdown("**Análisis automático**")
                if len(corr_total) > 0:
                    max_corr = corr_total.abs().idxmax()
                    direction = "positiva" if corr_total[max_corr] > 0 else "negativa"
                    st.write(
                        f"- El partido con mayor correlación {direction} con el total de votos "
                        f"por puesto es **{max_corr}** (r = {corr_total[max_corr]:.2f})."
                    )
                if len(pares) > 0:
                    a, b, r = pares[0]
                    if r > 0.7:
                        st.write(
                            f"- **{a}** y **{b}** muestran una correlación fuerte (r = {r:.2f}), "
                            "lo que sugiere que sus votantes coinciden geográficamente."
                        )
                    elif r < -0.3:
                        st.write(
                            f"- **{a}** y **{b}** muestran correlación negativa (r = {r:.2f}), "
                            "indicando bases electorales territorialmente diferenciadas."
                        )
                    else:
                        st.write(
                            f"- No se observa correlación fuerte entre los partidos "
                            f"(máximo r = {r:.2f} entre **{a}** y **{b}**)."
                        )

with st.expander("Notas y limitaciones"):
    st.markdown("""
- **2019**: datos de la Alcaldía de Bogotá. No hay censo oficial de 2019, se usa proxy de 2022.
- **2026 (Presidencial/Cámara/Senado)**: datos de ESCRUTINIO oficial. El cruce de puesto/censo usa el código exacto de puesto (mismo DIVIPOL de cada elección), no el nombre.
- **Geometría**: se une por nombre de puesto normalizado (el número de puesto del gpkg de IDECA no coincide con el código de la Registraduría). ~10-15% de los puestos no tienen coordenada.
- **Colores**: rojo = mayor intensidad (más votos o mayor porcentaje), verde = menor intensidad.
- **Diámetro del círculo**: proporcional a la cantidad total de votos en ese puesto de votación.
- **Censo**: Presidencial 2022 y 2026 usan su propio censo real; Territoriales 2023 y 2019 usan censo proxy.
""")
