"""
PP2 Layer 1 - Solar production estimator (full-year pass).

Full calendar year 2025, same site and system as the validated MVP:
- Duesseldorf (lat=51.23, lon=6.77)
- System: 10 kWp, PR=0.80, tilt=35 deg south (azimuth=0), model=era5

Formula: kWh = (GTI_Wh_per_m2 / 1000) * kWp * PR, applied per hour.

Outputs:
  pp2_layer1_2025_hourly.csv          - 8760 rows: date, hour, gti_wh_m2, kwh
  pp2_layer1_2025_monthly_totals.png  - bar chart of kWh per month
"""

import csv
import json
import urllib.parse
import urllib.request
from collections import defaultdict

import matplotlib.pyplot as plt

# --- Config ------------------------------------------------------------------

LATITUDE = 51.23
LONGITUDE = 6.77
START_DATE = "2025-01-01"
END_DATE = "2025-12-31"
TIMEZONE = "Europe/Berlin"

TILT_DEG = 35
AZIMUTH_DEG = 0  # Open-Meteo convention: 0 = south

KWP = 10.0
PR = 0.80

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

MONTH_LABELS = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]


def fetch_gti():
    params = {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "start_date": START_DATE,
        "end_date": END_DATE,
        "hourly": "global_tilted_irradiance",
        "tilt": TILT_DEG,
        "azimuth": AZIMUTH_DEG,
        "timezone": TIMEZONE,
        "models": "era5",
    }
    url = f"{ARCHIVE_URL}?{urllib.parse.urlencode(params)}"
    print(f"Fetching GTI for {START_DATE} to {END_DATE} ...")
    print(f"Request URL: {url}\n")

    with urllib.request.urlopen(url) as response:
        data = json.load(response)

    timestamps = data["hourly"]["time"]   # "2025-01-01T00:00"
    gti_values = data["hourly"]["global_tilted_irradiance"]
    return timestamps, gti_values


def gti_to_kwh(gti_wh_m2):
    return (gti_wh_m2 / 1000.0) * KWP * PR


def main():
    timestamps, gti_values = fetch_gti()

    rows = []
    monthly_kwh = defaultdict(float)

    for ts, gti in zip(timestamps, gti_values):
        date_str, time_str = ts.split("T")
        hour_str = time_str[:5]
        month = int(date_str[5:7])
        kwh = gti_to_kwh(gti if gti is not None else 0.0)
        rows.append((date_str, hour_str, gti if gti is not None else 0.0, kwh))
        monthly_kwh[month] += kwh

    # --- CSV -----------------------------------------------------------------
    csv_path = "pp2_layer1_2025_hourly.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "hour", "gti_wh_m2", "kwh"])
        for date_str, hour_str, gti, kwh in rows:
            writer.writerow([date_str, hour_str, f"{gti:.1f}", f"{kwh:.4f}"])
    print(f"Hourly data saved to: {csv_path}  ({len(rows)} rows)")

    # --- Monthly bar chart ---------------------------------------------------
    months = list(range(1, 13))
    monthly_totals = [monthly_kwh[m] for m in months]

    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.bar(MONTH_LABELS, monthly_totals, color="#f4a300", edgecolor="white")
    for bar, val in zip(bars, monthly_totals):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 5,
            f"{val:.0f}",
            ha="center", va="bottom", fontsize=8,
        )
    ax.set_xlabel("Month")
    ax.set_ylabel("Output (kWh)")
    ax.set_title(
        f"PP2 Layer 1 - Monthly Solar Production (2025)\n"
        f"Duesseldorf, {KWP} kWp, PR={PR}, tilt={TILT_DEG} deg south"
    )
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    fig.tight_layout()

    chart_path = "pp2_layer1_2025_monthly_totals.png"
    fig.savefig(chart_path, dpi=150)
    print(f"Monthly chart saved to: {chart_path}")

    # --- Console summary -----------------------------------------------------
    annual_kwh = sum(monthly_totals)
    specific_yield = annual_kwh / KWP  # kWh/kWp

    print(f"\n--- Annual Summary ---")
    print(f"Annual total production : {annual_kwh:,.0f} kWh")
    print(f"Specific yield          : {specific_yield:.0f} kWh/kWp")

    if 800 <= specific_yield <= 1000:
        verdict = f"PASS — within typical German benchmark (800-1000 kWh/kWp)"
    elif specific_yield < 800:
        verdict = f"LOW  — below typical German benchmark (800-1000 kWh/kWp)"
    else:
        verdict = f"HIGH — above typical German benchmark (800-1000 kWh/kWp)"
    print(f"Sanity check            : {verdict}")


if __name__ == "__main__":
    main()
