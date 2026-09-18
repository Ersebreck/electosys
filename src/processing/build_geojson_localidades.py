"""Convierte data/loca/Loca.shp (límites de localidades) a GeoJSON para el choropleth.
Ya está en grados (GCS_MAGNA ~ WGS84), no requiere reproyectar."""
import json

import shapefile
from shapely.geometry import shape, mapping

IN_PATH = "data/loca/Loca.shp"
OUT_PATH = "output/maps/localidades.geojson"


def main():
    sf = shapefile.Reader(IN_PATH)
    features = []
    for shp_rec, rec in zip(sf.shapes(), sf.records()):
        geom = shape(shp_rec.__geo_interface__)
        features.append({
            "type": "Feature",
            "properties": {
                "codigo_localidad": rec["LocCodigo"],
                "localidad": rec["LocNombre"],
            },
            "geometry": mapping(geom),
        })

    geojson = {"type": "FeatureCollection", "features": features}
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False)

    print(f"OK -> {OUT_PATH} ({len(features)} localidades)")


if __name__ == "__main__":
    main()
