"""
PP2 Layer 1 - Solar production estimator (formula validation pass).

Single summer day, single site, single system config:
- Date: 2023-06-21, Duesseldorf (lat=51.23, lon=6.77)
- System: 10 kWp, PR = 0.80
- Roof: south-facing, tilt = 35 deg (Open-Meteo azimuth=0 == south)

Pulls Global Tilted Irradiance (GTI) from Open-Meteo's ERA5 historical
archive and applies: kWh = (GTI_Wh_per_m2 / 1000) * kWp * PR
"""

import json
import urllib.parse
import urllib.request

import matplotlib.pyplot as plt

# --- Config ---------------------------------------------------------------

LATITUDE = 51.23
LONGITUDE = 6.77
DATE = "2023-06-21"
TIMEZONE = "Europe/Berlin"

TILT_DEG = 35
AZIMUTH_DEG = 0  # Open-Meteo convention: 0 = south

KWP = 10.0
PR = 0.80

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"


def fetch_gti():
    params = {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "start_date": DATE,
        "end_date": DATE,
        "hourly": "global_tilted_irradiance",
        "tilt": TILT_DEG,
        "azimuth": AZIMUTH_DEG,
        "timezone": TIMEZONE,
        "models": "era5",  # required: default model omits GTI for archive queries
    }
    url = f"{ARCHIVE_URL}?{urllib.parse.urlencode(params)}"
    print(f"Request URL: {url}\n")

    with urllib.request.urlopen(url) as response:
        data = json.load(response)

    print("Raw hourly GTI response (global_tilted_irradiance):")
    print(json.dumps(data["hourly"]["global_tilted_irradiance"], indent=2))
    print()

    hours = [t.split("T")[1] for t in data["hourly"]["time"]]
    gti_wh_m2 = data["hourly"]["global_tilted_irradiance"]
    return hours, gti_wh_m2


def gti_to_kwh(gti_wh_m2):
    """kWh = (GTI / 1000) * kWp * PR, per hour."""
    return (gti_wh_m2 / 1000.0) * KWP * PR


def main():
    hours, gti_wh_m2 = fetch_gti()
    kwh_per_hour = [gti_to_kwh(g) for g in gti_wh_m2]
    daily_total = sum(kwh_per_hour)

    # --- Table ---
    print(f"PP2 Layer 1 - Solar Production Estimate")
    print(f"Site: Duesseldorf (lat={LATITUDE}, lon={LONGITUDE})  Date: {DATE}")
    print(f"System: {KWP} kWp, PR={PR}, tilt={TILT_DEG} deg, azimuth={AZIMUTH_DEG} deg (south)\n")
    print(f"{'Hour':>6} | {'GTI (Wh/m2)':>12} | {'Output (kWh)':>13}")
    print("-" * 37)
    for hour, gti, kwh in zip(hours, gti_wh_m2, kwh_per_hour):
        print(f"{hour:>6} | {gti:>12.1f} | {kwh:>13.3f}")
    print("-" * 37)
    print(f"{'Total':>6} | {sum(gti_wh_m2):>12.1f} | {daily_total:>13.3f}")

    print(f"\nDaily total production: {daily_total:.2f} kWh")

    # --- Chart ---
    hour_labels = [h[:2] for h in hours]
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(hour_labels, kwh_per_hour, color="#f4a300")
    ax.set_xlabel("Hour of day")
    ax.set_ylabel("Output (kWh)")
    ax.set_title(
        f"PP2 Layer 1 - Hourly Solar Production\n"
        f"{DATE}, Duesseldorf, {KWP} kWp, PR={PR}, tilt={TILT_DEG} deg south "
        f"(Daily total: {daily_total:.2f} kWh)"
    )
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    fig.tight_layout()

    out_path = "pp2_layer1_hourly_output.png"
    fig.savefig(out_path, dpi=150)
    print(f"Chart saved to: {out_path}")


if __name__ == "__main__":
    main()
