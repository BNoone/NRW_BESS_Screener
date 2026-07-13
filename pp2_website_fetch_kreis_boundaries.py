"""
PP2 Website - Step 1: Fetch NRW Kreis-level boundaries.

Downloads the mid-simplification Kreis-level GeoJSON from deutschlandGeoJSON
(https://github.com/isellsoap/deutschlandGeoJSON), filters to Nordrhein-
Westfalen (via the Bundesland/NAME_1 property), and adds a normalized
`kreis_join_name` property so map scripts can join against MaStR's
`Landkreis` column.

The source is GADM/DIVA-GIS derived: it uses English city names for some
kreisfreie Staedte (e.g. "Cologne", "Cleves") and pre-2009 administrative
boundaries (separate "Aachen" / "Aachen Staedte" instead of the merged
"Staedteregion Aachen" that has existed since 2009). Both quirks are
corrected only in the added `kreis_join_name` field - the original
properties are left untouched.
"""

import json
import urllib.request
from pathlib import Path

BASE = Path(__file__).parent
OUT_PATH = BASE / "data" / "nrw_kreise_boundaries.geojson"

SOURCE_URL = (
    "https://raw.githubusercontent.com/isellsoap/deutschlandGeoJSON/main/"
    "4_kreise/3_mittel.geo.json"  # mid-simplification: reasonable file size
)

BUNDESLAND = "Nordrhein-Westfalen"

# Raw NAME_3 (from the source) -> normalized name matching MaStR's Landkreis
# convention. Built by inspecting both datasets directly; see module docstring.
NAME_MAP = {
    "Aachen": "Städteregion Aachen",
    "Aachen Städte": "Städteregion Aachen",
    "Bielefeld Städte": "Bielefeld",
    "Bochum Städte": "Bochum",
    "Bonn Städte": "Bonn",
    "Borken": "Borken",
    "Bottrop Städte": "Bottrop",
    "Cleves": "Kleve",
    "Coesfeld": "Coesfeld",
    "Cologne Städte": "Köln",
    "Dortmund Städte": "Dortmund",
    "Duisburg Städte": "Duisburg",
    "Düren": "Düren",
    "Düsseldorf Städte": "Düsseldorf",
    "Ennepe-Ruhr": "Ennepe-Ruhr-Kreis",
    "Essen Städte": "Essen",
    "Euskirchen": "Euskirchen",
    "Gelsenkirchen Städte": "Gelsenkirchen",
    "Gütersloh": "Gütersloh",
    "Hagen Städte": "Hagen",
    "Hamm Städte": "Hamm",
    "Heinsberg": "Heinsberg",
    "Herford": "Herford",
    "Herne Städte": "Herne",
    "Hochsauerlandkreis": "Hochsauerlandkreis",
    "Höxter": "Höxter",
    "Krefeld Städte": "Krefeld",
    "Leverkusen Städte": "Leverkusen",
    "Lippe": "Lippe",
    "Märkischer Kreis": "Märkischer Kreis",
    "Mettmann": "Mettmann",
    "Minden-Lübbecke": "Minden-Lübbecke",
    "Mönchengladbach Städte": "Mönchengladbach",
    "Mülheim Städte": "Mülheim an der Ruhr",
    "Münster Städte": "Münster",
    "Oberbergischer Kreis": "Oberbergischer Kreis",
    "Oberhausen Städte": "Oberhausen",
    "Olpe": "Olpe",
    "Paderborn": "Paderborn",
    "Recklinghausen": "Recklinghausen",
    "Remscheid Städte": "Remscheid",
    "Rhein-Erft-Kreis": "Rhein-Erft-Kreis",
    "Rhein-Kreis Neuss": "Rhein-Kreis Neuss",
    "Rhein-Sieg": "Rhein-Sieg-Kreis",
    "Rheinisch-Bergischer Kreis": "Rheinisch-Bergischer Kreis",
    "Siegen-Wittgenstein": "Siegen-Wittgenstein",
    "Soest": "Soest",
    "Solingen Städte": "Solingen",
    "Steinfurt": "Steinfurt",
    "Unna": "Unna",
    "Viersen": "Viersen",
    "Warendorf": "Warendorf",
    "Wesel": "Wesel",
    "Wuppertal Städte": "Wuppertal",
}


def main():
    print(f"Fetching: {SOURCE_URL}")
    with urllib.request.urlopen(SOURCE_URL) as response:
        data = json.load(response)
    print(f"Total features (all of Germany): {len(data['features']):,}")

    nrw_features = [
        f for f in data["features"] if f["properties"].get("NAME_1") == BUNDESLAND
    ]
    print(f"Filtered to {BUNDESLAND}: {len(nrw_features):,} features")

    unmapped = set()
    for f in nrw_features:
        raw_name = f["properties"]["NAME_3"]
        join_name = NAME_MAP.get(raw_name)
        if join_name is None:
            unmapped.add(raw_name)
        f["properties"]["kreis_join_name"] = join_name

    if unmapped:
        print(f"WARNING: {len(unmapped)} NAME_3 values have no join mapping:")
        for n in sorted(unmapped):
            print(f"  - {n}")

    unique_join_names = sorted({f["properties"]["kreis_join_name"] for f in nrw_features})
    print(f"Unique kreis_join_name values: {len(unique_join_names)}")

    out_geojson = {"type": "FeatureCollection", "features": nrw_features}
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out_geojson), encoding="utf-8")
    print(f"Saved: {OUT_PATH} ({OUT_PATH.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
