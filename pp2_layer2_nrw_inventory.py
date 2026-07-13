"""
PP2 Layer 2 - Step 2 & 3: Query, filter, and summarize NRW BESS + PV inventory
from the local MaStR SQLite database (built by pp2_layer2_download_mastr.py).

Reads directly from data/open-mastr/data/sqlite/open-mastr.db (gitignored,
national scope) and writes two small NRW-filtered parquet files that are
safe to commit:
  - pp2_layer2_nrw_bess.parquet   (battery storage units)
  - pp2_layer2_nrw_pv.parquet     (PV units)
"""

import sqlite3
from pathlib import Path

import pandas as pd

BASE = Path(__file__).parent
DB_PATH = BASE / "data" / "open-mastr" / "data" / "sqlite" / "open-mastr.db"

OUT_BESS = BASE / "pp2_layer2_nrw_bess.parquet"
OUT_PV = BASE / "pp2_layer2_nrw_pv.parquet"

BUNDESLAND = "Nordrhein-Westfalen"

# MaStR's public field label "Stromspeichertechnologie" maps to the
# `Batterietechnologie` column in open-mastr's storage_extended table.
# Pumped-hydro storage uses a separate `Pumpspeichertechnologie` column and
# is excluded simply by filtering Batterietechnologie to true battery types.
#
# The actual enum values in the bulk dump differ from the originally
# requested labels - mapped to the closest real category (confirmed):
#   Lithium-Ionen-Batterie  -> "Lithium-Batterie"
#   Blei-Saeure-Batterie    -> "Blei-Batterie"
#   Redox-Flow-Batterie     -> "Redox-Flow-Batterie"  (exact match)
#   Natrium-Ionen-Batterie  -> "Hochtemperaturbatterie" (closest proxy;
#                              covers sodium-based chemistries e.g. NaS/NaNiCl2)
BATTERY_TECHNOLOGIES = [
    "Lithium-Batterie",
    "Blei-Batterie",
    "Redox-Flow-Batterie",
    "Hochtemperaturbatterie",
]

STORAGE_COLUMNS = [
    "se.EinheitMastrNummer",
    "se.Batterietechnologie",
    "se.Bruttoleistung",
    "se.Nettonennleistung",
    "su.NutzbareSpeicherkapazitaet",
    "se.Landkreis",
    "se.Gemeindeschluessel",
    "se.Postleitzahl",
    "se.Laengengrad",
    "se.Breitengrad",
    "se.Inbetriebnahmedatum",
]

PV_COLUMNS = [
    "EinheitMastrNummer",
    "Energietraeger",
    "Bruttoleistung",
    "Landkreis",
    "Gemeindeschluessel",
    "Postleitzahl",
    "Laengengrad",
    "Breitengrad",
    "Inbetriebnahmedatum",
]


def section(title: str, width: int = 72):
    print()
    print("=" * width)
    print(f"  {title}")
    print("=" * width)


def load_nrw_storage(conn: sqlite3.Connection) -> pd.DataFrame:
    # storage_extended (unit-level, "se") carries power (kW) but its own
    # NutzbareSpeicherkapazitaet is unpopulated nationwide. The energy
    # capacity (kWh) actually lives on the linked Anlage/plant-level record
    # in storage_units ("su"), joined via VerknuepfteEinheit.
    placeholders = ", ".join("?" for _ in BATTERY_TECHNOLOGIES)
    cols = ", ".join(STORAGE_COLUMNS)
    query = f"""
        SELECT {cols}
        FROM storage_extended se
        LEFT JOIN storage_units su ON su.VerknuepfteEinheit = se.EinheitMastrNummer
        WHERE se.Bundesland = ?
          AND se.Batterietechnologie IN ({placeholders})
    """
    return pd.read_sql_query(query, conn, params=[BUNDESLAND, *BATTERY_TECHNOLOGIES])


def load_nrw_pv(conn: sqlite3.Connection) -> pd.DataFrame:
    cols = ", ".join(PV_COLUMNS)
    query = f"""
        SELECT {cols}
        FROM solar_extended
        WHERE Bundesland = ?
          AND Energietraeger = 'Solare Strahlungsenergie'
    """
    return pd.read_sql_query(query, conn, params=[BUNDESLAND])


def print_storage_summary(df: pd.DataFrame):
    section("NRW BATTERY STORAGE - SUMMARY")
    total_kw = df["Bruttoleistung"].sum()
    total_kwh = df["NutzbareSpeicherkapazitaet"].sum()
    print(f"Total units          : {len(df):,}")
    print(f"Total power capacity : {total_kw:,.1f} kW")
    print(f"Total usable energy  : {total_kwh:,.1f} kWh "
          f"(non-null: {df['NutzbareSpeicherkapazitaet'].notna().sum():,}/{len(df):,})")

    section("Top 10 Landkreise by installed power (kW)")
    by_lk = (
        df.groupby("Landkreis", dropna=False)
        .agg(units=("EinheitMastrNummer", "count"),
             kw=("Bruttoleistung", "sum"),
             kwh=("NutzbareSpeicherkapazitaet", "sum"))
        .sort_values("kw", ascending=False)
        .head(10)
    )
    print(by_lk.to_string(float_format=lambda x: f"{x:,.1f}"))

    section("Breakdown by Stromspeichertechnologie")
    by_tech = (
        df.groupby("Batterietechnologie", dropna=False)
        .agg(units=("EinheitMastrNummer", "count"),
             kw=("Bruttoleistung", "sum"),
             kwh=("NutzbareSpeicherkapazitaet", "sum"))
        .sort_values("kw", ascending=False)
    )
    print(by_tech.to_string(float_format=lambda x: f"{x:,.1f}"))


def print_pv_summary(df: pd.DataFrame):
    section("NRW PV - SUMMARY")
    total_kwp = df["Bruttoleistung"].sum()
    print(f"Total units             : {len(df):,}")
    print(f"Total installed capacity: {total_kwp:,.1f} kWp")

    section("Top 10 Landkreise by installed capacity (kWp)")
    by_lk = (
        df.groupby("Landkreis", dropna=False)
        .agg(units=("EinheitMastrNummer", "count"),
             kwp=("Bruttoleistung", "sum"))
        .sort_values("kwp", ascending=False)
        .head(10)
    )
    print(by_lk.to_string(float_format=lambda x: f"{x:,.1f}"))

    section("Duesseldorf - registered PV capacity")
    dus = df[df["Landkreis"].str.contains("sseldorf", case=False, na=False)]
    print(f"Units          : {len(dus):,}")
    print(f"Total capacity : {dus['Bruttoleistung'].sum():,.1f} kWp")
    print("(For comparison against Solarkataster's theoretical rooftop potential.)")


def main():
    if not DB_PATH.exists():
        raise SystemExit(
            f"MaStR database not found at {DB_PATH}. "
            "Run pp2_layer2_download_mastr.py first."
        )

    conn = sqlite3.connect(DB_PATH)
    try:
        bess = load_nrw_storage(conn)
        pv = load_nrw_pv(conn)
    finally:
        conn.close()

    bess.to_parquet(OUT_BESS, index=False)
    pv.to_parquet(OUT_PV, index=False)
    print(f"Saved: {OUT_BESS} ({len(bess):,} rows)")
    print(f"Saved: {OUT_PV} ({len(pv):,} rows)")

    print_storage_summary(bess)
    print_pv_summary(pv)


if __name__ == "__main__":
    main()
