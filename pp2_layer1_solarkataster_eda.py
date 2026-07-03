"""
PP2 Layer 1 - Solarkataster NRW schema/EDA pass (Duesseldorf rooftop dataset).

Schema-only: no PV computation. Goal is to understand available fields
(orientation, tilt, usable area, official yield figure) before filtering.

Outputs:
  solarkataster_dus_schema_summary.txt  - full printed summary
"""

import io
import sys
import textwrap
from pathlib import Path

import geopandas as gpd
import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BASE = Path(__file__).parent
SHP = BASE / "data/shp_duesseldorf/Solarkataster-Potentiale-Photovoltaik_05111000_Duesseldorf.shp"
META_XLSX = BASE / "data/meta/Metadaten_PV_Dach_2024_09_opendata.xlsx"
OUT_TXT = BASE / "solarkataster_dus_schema_summary.txt"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class Tee:
    """Write to both stdout and a string buffer simultaneously."""
    def __init__(self):
        self.buf = io.StringIO()
        self._stdout = sys.stdout

    def write(self, text):
        self._stdout.write(text)
        self.buf.write(text)

    def flush(self):
        self._stdout.flush()

    def getvalue(self):
        return self.buf.getvalue()


def section(title: str, width: int = 72):
    print()
    print("=" * width)
    print(f"  {title}")
    print("=" * width)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    tee = Tee()
    sys.stdout = tee

    # -----------------------------------------------------------------------
    # 1. Load shapefile
    # -----------------------------------------------------------------------
    section("1. LOADING SHAPEFILE")
    print(f"Path : {SHP}")
    gdf = gpd.read_file(SHP, engine="pyogrio")
    print(f"Done : {len(gdf):,} rows loaded")

    # -----------------------------------------------------------------------
    # 2. Basic counts & CRS
    # -----------------------------------------------------------------------
    section("2. OVERVIEW")
    print(f"Total roof facets (rows) : {len(gdf):,}")
    print(f"Total columns            : {len(gdf.columns)}")
    print(f"CRS                      : {gdf.crs}")
    print(f"EPSG                     : {gdf.crs.to_epsg() if gdf.crs else 'unknown'}")
    print(f"Geometry type(s)         : {gdf.geometry.geom_type.unique().tolist()}")

    bbox = gdf.total_bounds  # [minx, miny, maxx, maxy]
    print(f"Bounding box (m)         : minX={bbox[0]:.0f}  minY={bbox[1]:.0f}  "
          f"maxX={bbox[2]:.0f}  maxY={bbox[3]:.0f}")

    # -----------------------------------------------------------------------
    # 3. Column names and dtypes
    # -----------------------------------------------------------------------
    section("3. COLUMN NAMES AND DATA TYPES")
    col_df = pd.DataFrame({
        "column": gdf.columns,
        "dtype": [str(gdf[c].dtype) for c in gdf.columns],
    })
    print(col_df.to_string(index=False))

    # -----------------------------------------------------------------------
    # 4. First 5 rows
    # -----------------------------------------------------------------------
    section("4. FIRST 5 ROWS (all columns)")
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 200)
    pd.set_option("display.max_colwidth", 40)
    print(gdf.head().drop(columns="geometry").to_string(index=True))

    # -----------------------------------------------------------------------
    # 5. Numeric column statistics
    # -----------------------------------------------------------------------
    section("5. NUMERIC COLUMN STATISTICS (min / max / mean / median)")
    num_cols = gdf.select_dtypes(include="number").columns.tolist()
    if num_cols:
        stats = gdf[num_cols].agg(["min", "max", "mean", "median"]).T
        stats.columns = ["min", "max", "mean", "median"]
        print(stats.to_string(float_format=lambda x: f"{x:,.3f}"))
    else:
        print("No numeric columns found.")

    # -----------------------------------------------------------------------
    # 6. Non-numeric (categorical / string) columns: unique value counts
    # -----------------------------------------------------------------------
    section("6. CATEGORICAL / STRING COLUMN SUMMARIES")
    cat_cols = gdf.select_dtypes(exclude="number").columns.tolist()
    cat_cols = [c for c in cat_cols if c != "geometry"]
    for col in cat_cols:
        vc = gdf[col].value_counts(dropna=False)
        top = vc.head(10)
        print(f"\n  {col}  (unique: {gdf[col].nunique()}, nulls: {gdf[col].isna().sum()})")
        for val, cnt in top.items():
            print(f"    {str(val):<40}  {cnt:>8,}")

    # -----------------------------------------------------------------------
    # 7. Null / missing value overview
    # -----------------------------------------------------------------------
    section("7. NULL / MISSING VALUE COUNTS")
    null_counts = gdf.isnull().sum()
    null_pct = (null_counts / len(gdf) * 100).round(2)
    null_df = pd.DataFrame({"null_count": null_counts, "null_pct": null_pct})
    null_df = null_df[null_df["null_count"] > 0].sort_values("null_count", ascending=False)
    if null_df.empty:
        print("No null values found in any column.")
    else:
        print(null_df.to_string())

    # -----------------------------------------------------------------------
    # 8. Metadata (Excel) — column abbreviation dictionary
    # -----------------------------------------------------------------------
    section("8. METADATA — FIELD ABBREVIATION DICTIONARY")
    if META_XLSX.exists():
        print(f"Metadata file: {META_XLSX.name}")
        xl = pd.ExcelFile(META_XLSX)
        print(f"Sheets        : {xl.sheet_names}\n")

        for sheet in xl.sheet_names:
            df_meta = xl.parse(sheet, header=None)
            print(f"\n--- Sheet: '{sheet}' ---")
            # Print raw content (first 120 rows max) so nothing is lost
            pd.set_option("display.max_rows", 120)
            pd.set_option("display.max_colwidth", 80)
            print(df_meta.to_string(index=False, header=False))
    else:
        print("Metadata Excel file not found — skipped.")

    # -----------------------------------------------------------------------
    # 9. Write summary file
    # -----------------------------------------------------------------------
    sys.stdout = tee._stdout  # restore
    summary_text = tee.getvalue()
    OUT_TXT.write_text(summary_text, encoding="utf-8")
    print(f"\nSummary saved to: {OUT_TXT}")


if __name__ == "__main__":
    main()
