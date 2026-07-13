"""
PP2 Layer 1 - Total theoretical PV potential vs. actual registered capacity,
Duesseldorf.

Loads the Solarkataster shapefile (already present locally, not
re-downloaded), filters to pitched roofs (dachtyp == "geneigt") with
meaningful installable capacity (kw >= 10), sums theoretical capacity (kw)
and theoretical annual yield (str), and compares against the actual
registered PV capacity from MaStR (PP2 Layer 2).
"""

from pathlib import Path

import geopandas as gpd

BASE = Path(__file__).parent
SHP = BASE / "data/shp_duesseldorf/Solarkataster-Potentiale-Photovoltaik_05111000_Duesseldorf.shp"
OUT_TXT = BASE / "pp2_layer1_potential_vs_actual.txt"

MIN_KW = 10
DACHTYP = "geneigt"

# Actual registered Duesseldorf PV capacity from MaStR (PP2 Layer 2,
# pp2_layer2_nrw_inventory.py output).
ACTUAL_REGISTERED_KWP = 161_365


def main():
    gdf = gpd.read_file(SHP, engine="pyogrio", columns=["dachtyp", "kw", "str"])

    filtered = gdf[(gdf["dachtyp"] == DACHTYP) & (gdf["kw"] >= MIN_KW)]

    total_roofs = len(filtered)
    theoretical_kwp = filtered["kw"].sum()
    theoretical_kwh_yr = filtered["str"].sum()
    realized_pct = ACTUAL_REGISTERED_KWP / theoretical_kwp * 100

    lines = [
        "PP2 Layer 1 - Duesseldorf: Theoretical PV Potential vs. Actual Registered",
        "=" * 76,
        f"Filter                       : dachtyp == '{DACHTYP}' AND kw >= {MIN_KW}",
        f"Total qualifying roofs        : {total_roofs:,}",
        f"Total theoretical potential   : {theoretical_kwp:,.1f} kWp",
        f"Total theoretical annual yield: {theoretical_kwh_yr:,.1f} kWh/year",
        f"Actual registered (MaStR)     : {ACTUAL_REGISTERED_KWP:,} kWp",
        f"Realized                      : {realized_pct:.1f}% of pitched-roof potential (kw>={MIN_KW}) already installed",
        "Note: flat roofs (dachtyp == 'flach') are excluded, so this is a floor",
        "estimate of total potential, not the full physical ceiling.",
    ]
    summary = "\n".join(lines)

    print(summary)
    OUT_TXT.write_text(summary + "\n", encoding="utf-8")
    print(f"\nSummary saved to: {OUT_TXT}")


if __name__ == "__main__":
    main()
