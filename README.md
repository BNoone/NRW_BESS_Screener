# NRW_BESS_Screener

A screening pipeline focused on PV potential in Duesseldorf, extending into a look at battery storage (BESS) already in place in Duesseldorf and the surrounding area. Wider NRW-wide data is included for context.

## Status

Layer 1 + Layer 2 complete. Layer 3 (economics) and Layer 4 (simulation) in progress.

- **Layer 1 - Solar production modeling**: hourly/full-year PV output estimator (Open-Meteo ERA5 GTI), validated against 100 Duesseldorf rooftops from the Solarkataster NRW cadastre, plus theoretical-vs-actual PV potential for Duesseldorf (pitched + flat roofs, see below).
- **Layer 2 - NRW BESS + PV inventory**: battery storage and PV unit inventory for NRW from the Marktstammdatenregister (MaStR), via `open-mastr`. Framing only so far for whether local BESS capacity could absorb local solar output - no absorption calculation yet (Phase B). Both NRW maps (`map_nrw_bess.html`, `map_nrw_pv.html`) use a **quantile-based color scale** (equal counts of Kreise per color band, not equal value ranges), fixing a linear-scale bug where one outlier Kreis (Hamm, 737,274 kW) flattened the rest of the map into one pale color. Each map has toggleable layers: a combined view, one layer per BESS chemistry (Lithium-/Blei-/Redox-Flow-/Hochtemperaturbatterie) or PV size bucket (residential &lt;10 kWp / commercial 10-100 kWp / utility-scale &ge;100 kWp), and an individual-site point-level layer for Duesseldorf specifically.
- **Layer 3 - Economics**: not started.
- **Layer 4 - Simulation**: not started.

## Duesseldorf: Potential vs. Actual

| | kWp |
|---|---|
| Pitched-roof potential (dachtyp='geneigt', kw&ge;10) | 716,356.3 |
| Flat-roof potential (dachtyp='flach', kw&ge;10) | 439,727.8 |
| **Combined total potential** | **1,156,084.1** |
| Actual registered (MaStR) | 161,365 |
| **Realized** | **14.0%** |

An earlier pass (`pp2_layer1_potential_vs_actual.txt`) covered pitched roofs only, understating total potential by excluding flat roofs entirely. The updated combined figure (`pp2_layer1_potential_vs_actual_v2.txt`) adds flat roofs after confirming the cadastre's own `kw`/`kwh_kwp`/`str` columns are fully populated and valid for them (zero nulls across 67,515 flat-roof rows), using the same south-facing-mounting methodology and 21.7% module efficiency the cadastre documents for pitched roofs - not a fallback assumption. The original pitched-only file is kept for comparison.

## Sources & Licenses

- **Open-Meteo ERA5 historical archive** (Global Tilted Irradiance) - [CC BY 4.0](https://open-meteo.com/en/license)
- **Marktstammdatenregister (MaStR)** - German federal register of power-generation and storage units, bulk XML via [`open-mastr`](https://github.com/OpenEnergyPlatform/open-MaStR); public registry data, self-reported by plant operators
- **Solarkataster NRW** (Land.NRW / Geobasis NRW) - rooftop PV potential cadastre for Duesseldorf; [Datenlizenz Deutschland - Namensnennung - Version 2.0](https://www.govdata.de/dl-de/by-2-0)
- **[deutschlandGeoJSON](https://github.com/isellsoap/deutschlandGeoJSON)** (isellsoap) - German administrative boundaries (Kreis level), GADM/DIVA-GIS derived; project archived

## Limitations

- Solarkataster figures are **theoretical** rooftop potential (shading/geometry model only), not an economic or grid-connection feasibility assessment. Flat-roof potential assumes south-facing mounting (the cadastre's `modarea` default); an east/west alternative (`modarea_ow`) exists in the source data but isn't used here. Even the combined pitched+flat figure excludes roofs below the 10 kW size threshold.
- MaStR is self-reported registry data with known gaps: e.g. usable storage capacity (kWh) is unpopulated at the unit level and had to be joined from a separate plant-level table; a small number of rows have inconsistent Bundesland/Landkreis values. Exact coordinates are also sparse and self-reported: only 29 of 6,672 Duesseldorf BESS units and 368 of 11,820 Duesseldorf PV units have usable lat/lon, which is why the Duesseldorf point-level map layers show a small sample of sites, not the full registered inventory.
- ERA5-based yield estimates were validated against 100 Duesseldorf roofs: **+17.1% mean offset** vs. the Solarkataster's own cadastre figure, with a tight **0.28% std** across roofs. The offset is explained by 2025 being an anomalously sunny year in ERA5 versus the DWD climatological baseline the cadastre uses - not a formula error (the tight std confirms the pipeline is internally consistent).
- NRW Kreis boundaries come from a GADM-derived source with pre-2009 administrative boundaries (no native "Städteregion Aachen"); joined to MaStR data via a manual name-normalization mapping.
