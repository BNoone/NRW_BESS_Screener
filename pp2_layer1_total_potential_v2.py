"""
PP2 Layer 1 - Total theoretical PV potential vs. actual registered capacity,
Duesseldorf - v2: pitched + flat roofs combined.

v1 (pp2_layer1_total_potential.py) only covered pitched roofs (dachtyp ==
"geneigt"), which understated total potential. This version adds flat roofs
(dachtyp == "flach") after first checking whether the cadastre's own kw/
kwh_kwp/str figures are valid for them.

Investigation findings (see script output below the "INVESTIGATION" header):
- kw, kwh_kwp, str are fully populated for all 67,515 flat-roof rows (zero
  nulls), with kwh_kwp in the same range as pitched roofs.
- The cadastre metadata (data/meta/Metadaten_PV_Dach_2024_09_opendata.xlsx)
  documents `modarea` for flat roofs as assuming south-facing mounting
  ("bei Flachdaechern bei einer Aufstaenderung nach Sueden"), with a
  separate `modarea_ow` column for the east/west alternative - `kw`/`str`
  are derived from the south-facing `modarea`, not `modarea_ow`.
- `neigung` (tilt) == 0 for all flat rows: that's the raw roof-surface tilt
  from the LiDAR scan, not an assumed racking angle - the cadastre's own
  21.7%-efficiency methodology already accounts for the installed panel
  geometry internally.
Conclusion: the cadastre's flat-roof figures are valid, cadastre-sourced
values using the same methodology as pitched roofs - no fallback assumption
needed. Direct method used: filter kw >= 10, sum kw and str, same as v1.

Output: pp2_layer1_potential_vs_actual_v2.txt (v1's output file is left
untouched for comparison).
"""

from pathlib import Path

import geopandas as gpd

BASE = Path(__file__).parent
SHP = BASE / "data/shp_duesseldorf/Solarkataster-Potentiale-Photovoltaik_05111000_Duesseldorf.shp"
OUT_TXT = BASE / "pp2_layer1_potential_vs_actual_v2.txt"

MIN_KW = 10

# Actual registered Duesseldorf PV capacity from MaStR (PP2 Layer 2,
# pp2_layer2_nrw_inventory.py output).
ACTUAL_REGISTERED_KWP = 161_365


def investigate_flat_roofs(gdf: "gpd.GeoDataFrame"):
    print("=" * 76)
    print("  INVESTIGATION: flat-roof (dachtyp == 'flach') data quality")
    print("=" * 76)
    flach = gdf[gdf["dachtyp"] == "flach"]
    cols = ["kw", "kwh_kwp", "str", "modarea", "modarea_ow", "neigung"]
    print(f"Flat-roof rows: {len(flach):,}")
    print(f"Null counts:\n{flach[cols].isna().sum().to_string()}")
    print(f"\nSummary stats:\n{flach[cols].describe().to_string()}")
    print(
        "\nMetadata (data/meta/Metadaten_PV_Dach_2024_09_opendata.xlsx) confirms "
        "modarea assumes south-facing mounting for flat roofs; kw/kwh_kwp/str "
        "use the same 21.7%-efficiency methodology as pitched roofs.\n"
        "-> Using the direct method (no fallback assumption needed).\n"
    )


def compute_potential(gdf: "gpd.GeoDataFrame", dachtyp: str):
    filtered = gdf[(gdf["dachtyp"] == dachtyp) & (gdf["kw"] >= MIN_KW)]
    return {
        "roofs": len(filtered),
        "kwp": filtered["kw"].sum(),
        "kwh_yr": filtered["str"].sum(),
    }


def main():
    gdf = gpd.read_file(
        SHP, engine="pyogrio",
        columns=["dachtyp", "kw", "str", "kwh_kwp", "modarea", "modarea_ow", "neigung"],
    )

    investigate_flat_roofs(gdf)

    pitched = compute_potential(gdf, "geneigt")
    flat = compute_potential(gdf, "flach")
    combined_kwp = pitched["kwp"] + flat["kwp"]
    combined_kwh = pitched["kwh_yr"] + flat["kwh_yr"]
    realized_pct = ACTUAL_REGISTERED_KWP / combined_kwp * 100

    lines = [
        "PP2 Layer 1 v2 - Duesseldorf: Theoretical PV Potential vs. Actual Registered",
        "(pitched + flat roofs combined)",
        "=" * 78,
        f"Filter (both roof types)         : kw >= {MIN_KW}",
        "",
        f"Pitched roofs (dachtyp='geneigt') : {pitched['roofs']:,} roofs, {pitched['kwp']:,.1f} kWp, {pitched['kwh_yr']:,.1f} kWh/year",
        f"Flat roofs (dachtyp='flach')      : {flat['roofs']:,} roofs, {flat['kwp']:,.1f} kWp, {flat['kwh_yr']:,.1f} kWh/year",
        "  (flat-roof figures are cadastre-sourced, south-facing mounting",
        "   assumption per the cadastre's own methodology - not a fallback",
        "   estimate; see investigation output above.)",
        "",
        f"Combined total potential          : {combined_kwp:,.1f} kWp",
        f"Combined total annual yield        : {combined_kwh:,.1f} kWh/year",
        f"Actual registered (MaStR)          : {ACTUAL_REGISTERED_KWP:,} kWp",
        f"Realized                           : {realized_pct:.1f}% of combined pitched+flat potential (kw>={MIN_KW}) already installed",
        "",
        "Note: v1 (pp2_layer1_potential_vs_actual.txt) covered pitched roofs only",
        "and understated total potential by excluding flat roofs entirely. This",
        "combined figure is a better floor estimate, though still not the full",
        "physical ceiling (e.g. roofs below the 10 kW size threshold, and",
        "shading/structural/economic constraints not modeled by the cadastre,",
        "are still excluded).",
    ]
    summary = "\n".join(lines)

    print(summary)
    OUT_TXT.write_text(summary + "\n", encoding="utf-8")
    print(f"\nSummary saved to: {OUT_TXT}")


if __name__ == "__main__":
    main()
