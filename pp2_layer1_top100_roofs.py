"""
PP2 Layer 1 - Curate top-100 most promising rooftops (Duesseldorf).

Filters the Solarkataster NRW shapefile to pitched roofs with >= 10 kWp
installable capacity, ranks by specific yield (kwh_kwp), takes the top 100,
reprojects centroids to WGS84, and saves a CSV ready for Open-Meteo queries.

No PV yield computation in this step.

Output:
  pp2_layer1_top100_roofs.csv  - 100 rows with lat/lon and key roof params
"""

from pathlib import Path

import geopandas as gpd
import pandas as pd
from pyproj import Transformer

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BASE = Path(__file__).parent
SHP = (
    BASE
    / "data/shp_duesseldorf"
    / "Solarkataster-Potentiale-Photovoltaik_05111000_Duesseldorf.shp"
)
OUT_CSV = BASE / "pp2_layer1_top100_roofs.csv"

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

MIN_KW = 10.0
TOP_N = 100

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    # 1. Load
    print(f"Loading shapefile ...")
    gdf = gpd.read_file(SHP, engine="pyogrio")
    print(f"  Total facets loaded : {len(gdf):,}")

    # 2. Filter
    gdf_f = gdf[(gdf["dachtyp"] == "geneigt") & (gdf["kw"] >= MIN_KW)].copy()
    print(f"  After filter (geneigt, kw >= {MIN_KW}) : {len(gdf_f):,}")

    # 3. Sort + top 100
    gdf_top = gdf_f.sort_values("kwh_kwp", ascending=False).head(TOP_N).copy()

    # 4. Centroids → reproject to EPSG:4326
    transformer = Transformer.from_crs("EPSG:25832", "EPSG:4326", always_xy=True)
    centroids = gdf_top.geometry.centroid
    lons, lats = transformer.transform(centroids.x.values, centroids.y.values)

    # 5. Build output DataFrame
    out = pd.DataFrame({
        "facet_id":       gdf_top["LANUK_ID"].values,
        "lat":            lats.round(6),
        "lon":            lons.round(6),
        "richtung_deg":   gdf_top["richtung"].values,
        "neigung_deg":    gdf_top["neigung"].values,
        "kw":             gdf_top["kw"].values,
        "kwh_kwp":        gdf_top["kwh_kwp"].values,
        "gradprz":        gdf_top["gradprz"].values,
        "modarea":        gdf_top["modarea"].values,
        "str":            gdf_top["str"].values,
    })

    # 6. Derived: Open-Meteo azimuth convention (0 = south, ±180 = north)
    # Solarkataster: 180° = south, 270° = west
    # Open-Meteo:      0° = south,  90° = west
    out["openmeteo_azimuth"] = out["richtung_deg"] - 180

    # 7. Save
    out.to_csv(OUT_CSV, index=False)
    print(f"\nSaved : {OUT_CSV}  ({len(out)} rows)")

    # 8. Sanity summary
    print("\n--- Sanity Summary ---")
    print(f"Row count            : {len(out)}")
    print(f"kwh_kwp range        : {out['kwh_kwp'].min():.1f} – {out['kwh_kwp'].max():.1f} kWh/kWp")
    print(f"Average gradprz      : {out['gradprz'].mean():.1f} %")
    print(f"Total capacity       : {out['kw'].sum():.1f} kWp")
    print(f"openmeteo_azimuth    : {out['openmeteo_azimuth'].min()}° to {out['openmeteo_azimuth'].max()}°")
    print(f"\nTop 5 rows:")
    print(out.head().to_string(index=False))


if __name__ == "__main__":
    main()
