"""
PP2 Website - Step 2: Build the three folium maps for the dashboard.

Reuses existing outputs only - no data is regenerated here:
  - pp2_layer1_top100_validation.csv  (Layer 1 top-100 ERA5 validation)
  - pp2_layer2_nrw_bess.parquet       (Layer 2 NRW battery storage)
  - pp2_layer2_nrw_pv.parquet         (Layer 2 NRW PV)
  - data/nrw_kreise_boundaries.geojson (Kreis boundaries, see
    pp2_website_fetch_kreis_boundaries.py)

Outputs (repo root, embedded into index.html via <iframe>):
  - map_dus_top100.html
  - map_nrw_bess.html
  - map_nrw_pv.html
"""

from __future__ import annotations

import json
from pathlib import Path

import branca.colormap as cm
import folium
import pandas as pd

BASE = Path(__file__).parent
DUS_CENTER = (51.2277, 6.7735)
NRW_CENTER = (51.43, 7.55)

GEOJSON_PATH = BASE / "data" / "nrw_kreise_boundaries.geojson"


def section(title: str, width: int = 72):
    print()
    print("=" * width)
    print(f"  {title}")
    print("=" * width)


# ---------------------------------------------------------------------------
# Map A: Duesseldorf top-100 rooftop validation
# ---------------------------------------------------------------------------

def build_top100_map():
    section("MAP A: Duesseldorf top-100 rooftop validation")
    df = pd.read_csv(BASE / "pp2_layer1_top100_validation.csv")
    print(f"Loaded {len(df):,} roofs")

    colormap = cm.LinearColormap(
        colors=["#2b83ba", "#ffffbf", "#d7191c"],
        vmin=df["pct_diff"].min(),
        vmax=df["pct_diff"].max(),
        caption="ERA5 vs. Solarkataster cadastre yield offset (%)",
    )

    m = folium.Map(location=DUS_CENTER, zoom_start=11, tiles="cartodbpositron")

    for _, row in df.iterrows():
        popup_html = (
            f"<b>{row['facet_id']}</b><br>"
            f"Cadastre kwh/kWp: {row['kwh_kwp']:.1f}<br>"
            f"Our kwh/kWp: {row['our_kwh_per_kwp']:.1f}<br>"
            f"Offset: {row['pct_diff']:+.2f}%<br>"
            f"Roof tilt (gradprz): {row['gradprz']}"
        )
        folium.CircleMarker(
            location=(row["lat"], row["lon"]),
            radius=5,
            color=colormap(row["pct_diff"]),
            fill=True,
            fill_color=colormap(row["pct_diff"]),
            fill_opacity=0.85,
            weight=1,
            popup=folium.Popup(popup_html, max_width=250),
        ).add_to(m)

    colormap.add_to(m)
    out_path = BASE / "map_dus_top100.html"
    m.save(str(out_path))
    print(f"Saved: {out_path}")


# ---------------------------------------------------------------------------
# Shared: aggregate a parquet by Landkreis and join to Kreis boundaries
# ---------------------------------------------------------------------------

def load_kreis_geojson():
    with open(GEOJSON_PATH, encoding="utf-8") as f:
        return json.load(f)


def aggregate_by_kreis(df: pd.DataFrame, power_col: str, energy_col: str | None,
                        join_names: set) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Aggregate df by Landkreis and split into matched / unmatched vs. join_names
    (case-insensitive match against the geojson's kreis_join_name values)."""
    agg = {"units": ("EinheitMastrNummer", "count"), "power": (power_col, "sum")}
    if energy_col:
        agg["energy"] = (energy_col, "sum")

    by_lk = df.groupby("Landkreis", dropna=False).agg(**agg).reset_index()

    join_names_lower = {n.lower(): n for n in join_names}
    by_lk["match_key"] = by_lk["Landkreis"].str.strip().str.lower().map(join_names_lower)

    unmatched = by_lk[by_lk["match_key"].isna()].copy()

    # Multiple raw Landkreis spellings can collapse onto the same match_key
    # (e.g. "Unna" and "unna") - re-aggregate so none of them get silently
    # dropped/overwritten downstream.
    value_cols = ["units", "power"] + (["energy"] if energy_col else [])
    matched = (
        by_lk[by_lk["match_key"].notna()]
        .groupby("match_key")[value_cols]
        .sum()
        .reset_index()
    )
    return matched, unmatched


def build_choropleth_map(matched: pd.DataFrame, geojson: dict, *,
                          legend_name: str, tooltip_energy_label: str | None,
                          out_filename: str, has_energy: bool):
    m = folium.Map(location=NRW_CENTER, zoom_start=8, tiles="cartodbpositron")

    value_by_kreis = matched.set_index("match_key")["power"].to_dict()
    units_by_kreis = matched.set_index("match_key")["units"].to_dict()
    energy_by_kreis = matched.set_index("match_key")["energy"].to_dict() if has_energy else {}

    for feature in geojson["features"]:
        jn = feature["properties"]["kreis_join_name"]
        feature["properties"]["power_value"] = round(value_by_kreis.get(jn, 0), 1)
        feature["properties"]["units_value"] = int(units_by_kreis.get(jn, 0))
        if has_energy:
            feature["properties"]["energy_value"] = round(energy_by_kreis.get(jn, 0), 1)

    folium.Choropleth(
        geo_data=geojson,
        data=matched,
        columns=["match_key", "power"],
        key_on="feature.properties.kreis_join_name",
        fill_color="YlOrRd",
        fill_opacity=0.8,
        line_opacity=0.4,
        legend_name=legend_name,
        nan_fill_color="#dddddd",
    ).add_to(m)

    tooltip_fields = ["kreis_join_name", "power_value", "units_value"]
    tooltip_aliases = ["Kreis:", legend_name + ":", "Units:"]
    if has_energy:
        tooltip_fields.append("energy_value")
        tooltip_aliases.append((tooltip_energy_label or "Energy") + ":")

    folium.GeoJson(
        geojson,
        style_function=lambda x: {"fillOpacity": 0, "weight": 0},
        tooltip=folium.GeoJsonTooltip(fields=tooltip_fields, aliases=tooltip_aliases),
    ).add_to(m)

    out_path = BASE / out_filename
    m.save(str(out_path))
    print(f"Saved: {out_path}")


# ---------------------------------------------------------------------------
# Map B: NRW battery storage by Kreis
# ---------------------------------------------------------------------------

def build_bess_map(geojson: dict, join_names: set):
    section("MAP B: NRW battery storage by Kreis")
    df = pd.read_parquet(BASE / "pp2_layer2_nrw_bess.parquet")
    matched, unmatched = aggregate_by_kreis(df, "Bruttoleistung", "NutzbareSpeicherkapazitaet", join_names)

    print(f"Matched Kreise: {len(matched)}")
    if len(unmatched):
        print(f"UNMATCHED Landkreis values ({len(unmatched)} rows, not shown on map):")
        print(unmatched[["Landkreis", "units", "power", "energy"]].to_string(index=False))

    build_choropleth_map(
        matched, geojson,
        legend_name="Total battery storage power (kW)",
        tooltip_energy_label="Total usable energy (kWh)",
        out_filename="map_nrw_bess.html",
        has_energy=True,
    )


# ---------------------------------------------------------------------------
# Map C: NRW PV by Kreis
# ---------------------------------------------------------------------------

def build_pv_map(geojson: dict, join_names: set):
    section("MAP C: NRW PV by Kreis")
    df = pd.read_parquet(BASE / "pp2_layer2_nrw_pv.parquet")
    matched, unmatched = aggregate_by_kreis(df, "Bruttoleistung", None, join_names)

    print(f"Matched Kreise: {len(matched)}")
    if len(unmatched):
        print(f"UNMATCHED Landkreis values ({len(unmatched)} rows, not shown on map):")
        print(unmatched[["Landkreis", "units", "power"]].to_string(index=False))

    build_choropleth_map(
        matched, geojson,
        legend_name="Total installed PV capacity (kWp)",
        tooltip_energy_label=None,
        out_filename="map_nrw_pv.html",
        has_energy=False,
    )


def main():
    build_top100_map()

    geojson = load_kreis_geojson()
    join_names = {f["properties"]["kreis_join_name"] for f in geojson["features"]}

    build_bess_map(geojson, join_names)
    build_pv_map(geojson, join_names)


if __name__ == "__main__":
    main()
