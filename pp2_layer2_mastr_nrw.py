"""
PP2 Layer 2 - NRW BESS + PV inventory from Marktstammdatenregister (MaStR).

Phase 1 : Bulk-download solar + storage tables via open-mastr (national DB,
          written to ~/.open-MaStR/data/sqlite/  — NOT in this repo).
Phase 2 : Filter to NRW, save small parquet files (safe to commit).
Phase 3 : Print summary statistics.

Run once to download (~several GB, may take 15-30 min depending on connection).
Re-running skips the download if the DB already has data.

Outputs (committed):
  pp2_layer2_nrw_bess.parquet
  pp2_layer2_nrw_pv.parquet
"""

import sys
import os
import warnings
warnings.filterwarnings("ignore")

# open-mastr installs to user site-packages on this machine
sys.path.insert(0, "/Users/bogdankolchenko/Library/Python/3.9/lib/python/site-packages")

import pandas as pd
from pathlib import Path
from sqlalchemy import create_engine, inspect as sa_inspect

BASE = Path(__file__).parent

# ---------------------------------------------------------------------------
# 1. Download (solar + storage only)
# ---------------------------------------------------------------------------

print("=" * 60)
print("  PHASE 1 — MaStR bulk download (solar + storage)")
print("=" * 60)
print("Writing to ~/.open-MaStR/data/sqlite/ (not in repo).")
print("This may take 15-30 min on first run.\n")

from open_mastr import Mastr

db = Mastr(engine="sqlite")
db.download(method="bulk", data=["solar", "storage"], keep_old_downloads=True)
print("\nDownload complete.\n")

# ---------------------------------------------------------------------------
# 2. Connect directly to the SQLite file and read tables
# ---------------------------------------------------------------------------

print("=" * 60)
print("  PHASE 2 — Filter NRW storage + PV")
print("=" * 60)

sqlite_path = os.path.join(
    os.path.expanduser("~"), ".open-MaStR", "data", "sqlite", "open-mastr.db"
)
engine = create_engine(f"sqlite:///{sqlite_path}")

available_tables = sa_inspect(engine).get_table_names()
print(f"Tables in DB: {sorted(available_tables)}\n")

# NOTE: SQLite table names are snake_case (not CamelCase).
# NOTE: MaStR Batterietechnologie values differ from official spec labels:
#   Spec "Lithium-Ionen-Batterie"  → DB "Lithium-Batterie"
#   Spec "Blei-Saeure-Batterie"    → DB "Blei-Batterie"
#   Spec "Natrium-Ionen-Batterie"  → not present in current dump
#   Spec "Redox-Flow-Batterie"     → DB "Redox-Flow-Batterie" (exact match)
# NOTE: NutzbareSpeicherkapazitaet (kWh) is NULL for all units in the current
#   MaStR dump — a known data quality gap in the registry.
# NOTE: Loading full national tables into RAM is too slow (8M+ solar rows).
#   All NRW filtering is pushed into SQL WHERE clauses.

BATTERY_TECHS = ("Lithium-Batterie", "Redox-Flow-Batterie",
                 "Blei-Batterie", "Hochtemperaturbatterie")
BATT_IN = ", ".join(f"'{t}'" for t in BATTERY_TECHS)

# ── 2A. Storage units (SQL-filtered) ────────────────────────────────────

bess_sql = text(f"""
    SELECT EinheitMastrNummer, Bundesland, Landkreis, Gemeinde,
           Gemeindeschluessel, Postleitzahl, Laengengrad, Breitengrad,
           Inbetriebnahmedatum, Bruttoleistung, Nettonennleistung,
           NutzbareSpeicherkapazitaet, Batterietechnologie, Technologie,
           EinheitBetriebsstatus
    FROM storage_extended
    WHERE Bundesland = 'Nordrhein-Westfalen'
      AND Technologie = 'Batterie'
      AND Batterietechnologie IN ({BATT_IN})
""")
print("Querying storage_extended (NRW + battery filter in SQL) ...")
bess_out = pd.read_sql(bess_sql, engine)
print(f"  NRW battery storage rows : {len(bess_out):,}")

# ── 2B. PV units (SQL-filtered) ──────────────────────────────────────────

pv_sql = text("""
    SELECT EinheitMastrNummer, Bundesland, Landkreis, Gemeinde,
           Gemeindeschluessel, Postleitzahl, Laengengrad, Breitengrad,
           Inbetriebnahmedatum, Bruttoleistung, Nettonennleistung,
           Energietraeger, EinheitBetriebsstatus
    FROM solar_extended
    WHERE Bundesland = 'Nordrhein-Westfalen'
""")
print("Querying solar_extended (NRW in SQL) ...")
pv_out = pd.read_sql(pv_sql, engine)
print(f"  NRW solar rows           : {len(pv_out):,}")

# ---------------------------------------------------------------------------
# 3. Save parquet (small NRW slices only)
# ---------------------------------------------------------------------------

bess_path = BASE / "pp2_layer2_nrw_bess.parquet"
pv_path   = BASE / "pp2_layer2_nrw_pv.parquet"

bess_out.to_parquet(bess_path, index=False)
pv_out.to_parquet(pv_path, index=False)
print(f"\nSaved: {bess_path}  ({len(bess_out):,} rows)")
print(f"Saved: {pv_path}  ({len(pv_out):,} rows)")

# ---------------------------------------------------------------------------
# 4. Summary statistics
# ---------------------------------------------------------------------------

def section(title):
    print(f"\n{'='*60}\n  {title}\n{'='*60}")

# ── BESS summary ─────────────────────────────────────────────────────────

section("BESS SUMMARY — NRW Battery Storage")

total_kw = bess_out["Bruttoleistung"].sum()
print(f"  Total units (NRW, battery types)  : {len(bess_out):,}")
print(f"  Total power   (Bruttoleistung kW) : {total_kw:,.0f} kW  ({total_kw/1000:,.1f} MW)")
print(f"  Total energy  (NutzbareSpeicher.) : N/A — field is NULL for all units in")
print(f"                                      current MaStR dump (known data gap)")

print(f"\n  By Batterietechnologie:")
print(
    bess_out.groupby("Batterietechnologie")
    .agg(units=("EinheitMastrNummer", "count"),
         total_kw=("Bruttoleistung", "sum"))
    .sort_values("total_kw", ascending=False)
    .to_string()
)

print(f"\n  Top 10 Landkreise by total kW:")
print(
    bess_out.groupby("Landkreis")
    .agg(units=("EinheitMastrNummer", "count"),
         total_kw=("Bruttoleistung", "sum"))
    .sort_values("total_kw", ascending=False)
    .head(10)
    .to_string()
)

# ── PV summary ───────────────────────────────────────────────────────────

section("PV SUMMARY — NRW Solar")

total_pv_kwp = pv_out["Bruttoleistung"].sum()
print(f"  Total units (NRW)                 : {len(pv_out):,}")
print(f"  Total capacity (Bruttoleistung)   : {total_pv_kwp:,.0f} kWp  ({total_pv_kwp/1e6:,.2f} GWp)")

print(f"\n  Top 10 Landkreise by total kWp:")
print(
    pv_out.groupby("Landkreis")
    .agg(units=("EinheitMastrNummer", "count"),
         total_kwp=("Bruttoleistung", "sum"))
    .sort_values("total_kwp", ascending=False)
    .head(10)
    .to_string()
)

# ── Düsseldorf spotlight ──────────────────────────────────────────────────

section("DUSSELDORF SPOTLIGHT")

dus_pv   = pv_out[pv_out["Landkreis"].str.contains("sseldorf", na=False)]
dus_bess = bess_out[bess_out["Landkreis"].str.contains("sseldorf", na=False)]

print(f"  PV units              : {len(dus_pv):,}")
print(f"  PV total kWp          : {dus_pv['Bruttoleistung'].sum():,.0f} kWp"
      f"  ({dus_pv['Bruttoleistung'].sum()/1000:,.1f} MWp)")
print(f"  (Compare to Solarkataster theoretical rooftop potential in later layers.)")
print(f"\n  BESS units            : {len(dus_bess):,}")
print(f"  BESS power            : {dus_bess['Bruttoleistung'].sum():,.0f} kW"
      f"  ({dus_bess['Bruttoleistung'].sum()/1000:,.1f} MW)")
print(f"  BESS energy (kWh)     : N/A — MaStR field unpopulated")

print("\nDone.")
