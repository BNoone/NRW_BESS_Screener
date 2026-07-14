"""
PP2 Website - Build the three folium maps for the dashboard.

Reuses existing outputs only - no data is regenerated here:
  - pp2_layer1_top100_validation.csv        (Layer 1 top-100 ERA5 validation)
  - data/shp_duesseldorf/...shp             (Solarkataster - only the
    LANUK_ID/kw/monthly-median columns, for seasonal figures)
  - pp2_layer2_nrw_bess.parquet             (Layer 2 NRW battery storage)
  - pp2_layer2_nrw_pv.parquet               (Layer 2 NRW PV)
  - data/nrw_kreise_boundaries.geojson       (Kreis boundaries, see
    pp2_website_fetch_kreis_boundaries.py)

Outputs (repo root, embedded into index.html via <iframe>):
  - map_dus_top100.html
  - map_nrw_bess.html
  - map_nrw_pv.html
"""

from __future__ import annotations

import json
from pathlib import Path

import folium
import geopandas as gpd
import pandas as pd
import branca.colormap as cm

BASE = Path(__file__).parent
DUS_CENTER = (51.2277, 6.7735)
NRW_CENTER = (51.43, 7.55)

GEOJSON_PATH = BASE / "data" / "nrw_kreise_boundaries.geojson"
SHP_PATH = BASE / "data/shp_duesseldorf/Solarkataster-Potentiale-Photovoltaik_05111000_Duesseldorf.shp"

PR = 0.80  # same performance ratio used throughout Layer 1

SEASON_MONTHS = {
    "spring (Mar-May)": ["mrz_median", "apr_median", "mai_median"],
    "summer (Jun-Aug)": ["jun_median", "jul_median", "aug_median"],
    "autumn (Sep-Nov)": ["sep_median", "okt_median", "nov_median"],
    "winter (Dec-Feb)": ["dez_median", "jan_median", "feb_median"],
}

BATTERY_CHEMISTRIES = [
    "Lithium-Batterie",
    "Blei-Batterie",
    "Redox-Flow-Batterie",
    "Hochtemperaturbatterie",
]

PV_SIZE_BUCKETS = [
    ("Residential (<10 kWp)", 0, 10),
    ("Commercial (10-100 kWp)", 10, 100),
    ("Utility-scale (>100 kWp)", 100, float("inf")),
]


def section(title: str, width: int = 76):
    print()
    print("=" * width)
    print(f"  {title}")
    print("=" * width)


# ---------------------------------------------------------------------------
# Map A: Duesseldorf top-100 rooftop validation
# ---------------------------------------------------------------------------

def load_seasonal_data(facet_ids: set) -> pd.DataFrame:
    """Per-roof kw + seasonal average daily kWh, joined from the Solarkataster
    shapefile (LANUK_ID == facet_id) - not from a new download, same source
    already used for the top-100 curation."""
    month_cols = sorted({c for cols in SEASON_MONTHS.values() for c in cols})
    gdf = gpd.read_file(SHP_PATH, engine="pyogrio", columns=["LANUK_ID", "kw", *month_cols])
    gdf = gdf[gdf["LANUK_ID"].isin(facet_ids)].copy()

    for season, cols in SEASON_MONTHS.items():
        avg_irradiance_wh_m2_day = gdf[cols].mean(axis=1)
        gdf[season] = (avg_irradiance_wh_m2_day / 1000.0) * gdf["kw"] * PR

    return gdf.rename(columns={"LANUK_ID": "facet_id"})[["facet_id", *SEASON_MONTHS.keys()]]


def build_top100_map():
    section("MAP A: Duesseldorf top-100 rooftop validation")
    df = pd.read_csv(BASE / "pp2_layer1_top100_validation.csv")
    print(f"Loaded {len(df):,} roofs")

    seasonal = load_seasonal_data(set(df["facet_id"]))
    df = df.merge(seasonal, on="facet_id", how="left")
    print(f"Joined seasonal daily kWh for {seasonal['facet_id'].nunique()} roofs")

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
            f"Shading-adjusted irradiation received: {row['gradprz']}%<br>"
            f"<b>Approx. daily production by season:</b><br>"
            + "".join(
                f"&nbsp;&nbsp;{season}: {row[season]:.1f} kWh/day<br>"
                for season in SEASON_MONTHS
            )
        )
        folium.CircleMarker(
            location=(row["lat"], row["lon"]),
            radius=5,
            color=colormap(row["pct_diff"]),
            fill=True,
            fill_color=colormap(row["pct_diff"]),
            fill_opacity=0.85,
            weight=1,
            popup=folium.Popup(popup_html, max_width=280),
        ).add_to(m)

    colormap.add_to(m)
    out_path = BASE / "map_dus_top100.html"
    m.save(str(out_path))
    print(f"Saved: {out_path}")


# ---------------------------------------------------------------------------
# Shared: Kreis boundaries + quantile-binned choropleth layers
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


def quantile_bins(values: pd.Series, n: int = 6) -> list:
    """Quantile-based bin edges (equal COUNT of Kreise per band, not equal
    value range) so one outlier Kreis doesn't flatten the whole color scale."""
    qs = [i / n for i in range(n + 1)]
    edges = sorted(set(round(float(e), 3) for e in values.quantile(qs).tolist()))
    if len(edges) < 3:
        # Degenerate distribution (too few distinct values) - fall back to min/max.
        edges = sorted({round(float(values.min()), 3), round(float(values.max()), 3)})
        if len(edges) < 2:
            edges = [edges[0], edges[0] + 1]
    return edges


def add_choropleth_layer(parent, matched: pd.DataFrame, geojson: dict, *,
                          legend_name: str, tooltip_energy_label: str | None,
                          has_energy: bool, bins: list, legend_map=None):
    """Adds a quantile-binned choropleth + tooltip to `parent` (a Map or a
    FeatureGroup, so multiple layers can be toggled via LayerControl).

    folium.Choropleth() only accepts a Map as parent (hard assertion), which
    breaks FeatureGroup-based layer toggling - so the choropleth is built
    manually here via GeoJson + a quantile StepColormap instead. If
    `legend_map` is given, the color-scale legend is added there (always a
    Map, so it stays visible regardless of which FeatureGroup is toggled).
    """
    value_by_kreis = matched.set_index("match_key")["power"].to_dict()
    units_by_kreis = matched.set_index("match_key")["units"].to_dict()
    energy_by_kreis = matched.set_index("match_key")["energy"].to_dict() if has_energy else {}

    # Work on a copy so different layers (e.g. per-chemistry) don't clobber
    # each other's power_value/units_value on the shared geojson features.
    geojson = json.loads(json.dumps(geojson))
    for feature in geojson["features"]:
        jn = feature["properties"]["kreis_join_name"]
        feature["properties"]["power_value"] = round(value_by_kreis.get(jn, 0), 1)
        feature["properties"]["units_value"] = int(units_by_kreis.get(jn, 0))
        if has_energy:
            feature["properties"]["energy_value"] = round(energy_by_kreis.get(jn, 0), 1)

    step_colormap = cm.StepColormap(
        colors=["#ffffb2", "#fed976", "#feb24c", "#fd8d3c", "#f03b20", "#bd0026"][: len(bins) - 1],
        index=bins,
        vmin=bins[0],
        vmax=bins[-1],
        caption=legend_name,
    )

    def style_function(feature):
        jn = feature["properties"]["kreis_join_name"]
        value = value_by_kreis.get(jn)
        return {
            "fillColor": step_colormap(value) if value is not None else "#dddddd",
            "color": "black",
            "weight": 0.5,
            "fillOpacity": 0.8,
        }

    tooltip_fields = ["kreis_join_name", "power_value", "units_value"]
    tooltip_aliases = ["Kreis:", legend_name + ":", "Units:"]
    if has_energy:
        tooltip_fields.append("energy_value")
        tooltip_aliases.append((tooltip_energy_label or "Energy") + ":")

    folium.GeoJson(
        geojson,
        style_function=style_function,
        tooltip=folium.GeoJsonTooltip(fields=tooltip_fields, aliases=tooltip_aliases),
    ).add_to(parent)

    if legend_map is not None:
        step_colormap.add_to(legend_map)


def point_marker_layer(name: str, points: pd.DataFrame, *, lat_col, lon_col,
                        value_col, value_label, unit: str, popup_extra_cols: dict,
                        show: bool = False) -> folium.FeatureGroup:
    """A toggleable FeatureGroup of individual site markers, sized/colored by
    `value_col` - same visual style as the top-100 solar map."""
    fg = folium.FeatureGroup(name=name, show=show)
    if len(points) == 0:
        return fg

    vmin, vmax = points[value_col].min(), points[value_col].max()
    colormap = cm.LinearColormap(
        colors=["#2b83ba", "#fdae61", "#d7191c"],
        vmin=vmin, vmax=(vmax if vmax > vmin else vmin + 1),
        caption=f"{value_label} ({unit})",
    )
    for _, row in points.iterrows():
        radius = 4 + 10 * ((row[value_col] - vmin) / (vmax - vmin) if vmax > vmin else 0.3)
        popup_lines = [f"<b>{value_label}:</b> {row[value_col]:.1f} {unit}"]
        for label, col in popup_extra_cols.items():
            popup_lines.append(f"{label}: {row[col]}")
        folium.CircleMarker(
            location=(row[lat_col], row[lon_col]),
            radius=radius,
            color=colormap(row[value_col]),
            fill=True,
            fill_color=colormap(row[value_col]),
            fill_opacity=0.85,
            weight=1,
            popup=folium.Popup("<br>".join(popup_lines), max_width=250),
        ).add_to(fg)
    colormap.add_to(fg)
    return fg


# ---------------------------------------------------------------------------
# Map B: NRW battery storage by Kreis (+ chemistry filters + Duesseldorf points)
# ---------------------------------------------------------------------------

def build_bess_map(geojson: dict, join_names: set):
    section("MAP B: NRW battery storage by Kreis")
    df = pd.read_parquet(BASE / "pp2_layer2_nrw_bess.parquet")

    m = folium.Map(location=NRW_CENTER, zoom_start=8, tiles="cartodbpositron")

    # --- Combined (all chemistries) - default visible layer ---
    matched, unmatched = aggregate_by_kreis(df, "Bruttoleistung", "NutzbareSpeicherkapazitaet", join_names)
    print(f"[Combined] Matched Kreise: {len(matched)}")
    if len(unmatched):
        print(f"[Combined] UNMATCHED Landkreis values ({len(unmatched)} rows, not shown on map):")
        print(unmatched[["Landkreis", "units", "power", "energy"]].to_string(index=False))

    combined_bins = quantile_bins(matched["power"])
    print(f"[Combined] Quantile bin edges (kW): {[round(b, 1) for b in combined_bins]}")
    dus_area = matched[matched["match_key"].isin(
        ["Düsseldorf", "Mettmann", "Rhein-Kreis Neuss", "Duisburg", "Krefeld"])]
    print(f"[Combined] Duesseldorf-area Kreise values (kW):\n{dus_area[['match_key', 'power']].to_string(index=False)}")

    fg_combined = folium.FeatureGroup(name="All chemistries (combined)", show=True)
    add_choropleth_layer(
        fg_combined, matched, geojson,
        legend_name="Total battery storage power (kW)",
        tooltip_energy_label="Total usable energy (kWh)",
        has_energy=True, bins=combined_bins, legend_map=m,
    )
    fg_combined.add_to(m)

    # --- Per-chemistry layers ---
    for chem in BATTERY_CHEMISTRIES:
        subset = df[df["Batterietechnologie"] == chem]
        matched_c, _ = aggregate_by_kreis(subset, "Bruttoleistung", "NutzbareSpeicherkapazitaet", join_names)
        print(f"[{chem}] {len(subset):,} units, {len(matched_c)} Kreise with data")
        if len(matched_c) == 0:
            continue
        bins_c = quantile_bins(matched_c["power"])
        fg = folium.FeatureGroup(name=chem, show=False)
        add_choropleth_layer(
            fg, matched_c, geojson,
            legend_name=f"{chem} power (kW)",
            tooltip_energy_label="Usable energy (kWh)",
            has_energy=True, bins=bins_c,
        )
        fg.add_to(m)

    # --- Duesseldorf point-level layer ---
    dus_points = df[
        (df["Landkreis"] == "Düsseldorf")
        & df["Laengengrad"].notna() & df["Breitengrad"].notna()
    ]
    print(f"[Duesseldorf points] {len(dus_points)} of {(df['Landkreis'] == 'Düsseldorf').sum()} "
          f"Duesseldorf BESS units have usable coordinates (MaStR coordinate reporting is sparse/self-reported)")
    fg_dus = point_marker_layer(
        "Duesseldorf sites (point-level)", dus_points,
        lat_col="Breitengrad", lon_col="Laengengrad",
        value_col="Bruttoleistung", value_label="Power", unit="kW",
        popup_extra_cols={"Chemistry": "Batterietechnologie", "PLZ": "Postleitzahl"},
    )
    fg_dus.add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)
    out_path = BASE / "map_nrw_bess.html"
    m.save(str(out_path))
    print(f"Saved: {out_path}")


# ---------------------------------------------------------------------------
# Map C: NRW PV by Kreis (+ size-bucket filters + Duesseldorf points)
# ---------------------------------------------------------------------------

def build_pv_map(geojson: dict, join_names: set):
    section("MAP C: NRW PV by Kreis")
    df = pd.read_parquet(BASE / "pp2_layer2_nrw_pv.parquet")

    m = folium.Map(location=NRW_CENTER, zoom_start=8, tiles="cartodbpositron")

    # --- Combined (all sizes) - default visible layer ---
    matched, unmatched = aggregate_by_kreis(df, "Bruttoleistung", None, join_names)
    print(f"[Combined] Matched Kreise: {len(matched)}")
    if len(unmatched):
        print(f"[Combined] UNMATCHED Landkreis values ({len(unmatched)} rows, not shown on map):")
        print(unmatched[["Landkreis", "units", "power"]].to_string(index=False))

    combined_bins = quantile_bins(matched["power"])
    print(f"[Combined] Quantile bin edges (kWp): {[round(b, 1) for b in combined_bins]}")
    dus_area = matched[matched["match_key"].isin(
        ["Düsseldorf", "Mettmann", "Rhein-Kreis Neuss", "Duisburg", "Krefeld"])]
    print(f"[Combined] Duesseldorf-area Kreise values (kWp):\n{dus_area[['match_key', 'power']].to_string(index=False)}")

    fg_combined = folium.FeatureGroup(name="All sizes (combined)", show=True)
    add_choropleth_layer(
        fg_combined, matched, geojson,
        legend_name="Total installed PV capacity (kWp)",
        tooltip_energy_label=None,
        has_energy=False, bins=combined_bins, legend_map=m,
    )
    fg_combined.add_to(m)

    # --- Per-size-bucket layers ---
    for label, lo, hi in PV_SIZE_BUCKETS:
        subset = df[(df["Bruttoleistung"] >= lo) & (df["Bruttoleistung"] < hi)] if hi != float("inf") \
            else df[df["Bruttoleistung"] >= lo]
        matched_b, _ = aggregate_by_kreis(subset, "Bruttoleistung", None, join_names)
        print(f"[{label}] {len(subset):,} units, {len(matched_b)} Kreise with data")
        if len(matched_b) == 0:
            continue
        bins_b = quantile_bins(matched_b["power"])
        fg = folium.FeatureGroup(name=label, show=False)
        add_choropleth_layer(
            fg, matched_b, geojson,
            legend_name=f"{label} capacity (kWp)",
            tooltip_energy_label=None,
            has_energy=False, bins=bins_b,
        )
        fg.add_to(m)

    # --- Duesseldorf point-level layer ---
    dus_points = df[
        (df["Landkreis"] == "Düsseldorf")
        & df["Laengengrad"].notna() & df["Breitengrad"].notna()
    ]
    print(f"[Duesseldorf points] {len(dus_points)} of {(df['Landkreis'] == 'Düsseldorf').sum()} "
          f"Duesseldorf PV units have usable coordinates (MaStR coordinate reporting is sparse/self-reported)")
    fg_dus = point_marker_layer(
        "Duesseldorf sites (point-level)", dus_points,
        lat_col="Breitengrad", lon_col="Laengengrad",
        value_col="Bruttoleistung", value_label="Capacity", unit="kWp",
        popup_extra_cols={"PLZ": "Postleitzahl"},
    )
    fg_dus.add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)
    out_path = BASE / "map_nrw_pv.html"
    m.save(str(out_path))
    print(f"Saved: {out_path}")


def main():
    build_top100_map()

    geojson = load_kreis_geojson()
    join_names = {f["properties"]["kreis_join_name"] for f in geojson["features"]}

    build_bess_map(geojson, join_names)
    build_pv_map(geojson, join_names)


if __name__ == "__main__":
    main()
