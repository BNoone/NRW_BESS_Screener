# NRW_BESS_Screener

A screening pipeline for battery storage (BESS) and PV potential in Nordrhein-Westfalen (NRW), Germany.

## Status

Layer 1 + Layer 2 complete. Layer 3 (economics) and Layer 4 (simulation) in progress.

- **Layer 1 - Solar production modeling**: hourly/full-year PV output estimator (Open-Meteo ERA5 GTI), validated against 100 Duesseldorf rooftops from the Solarkataster NRW cadastre, plus theoretical-vs-actual PV potential for Duesseldorf.
- **Layer 2 - NRW BESS + PV inventory**: battery storage and PV unit inventory for NRW from the Marktstammdatenregister (MaStR), via `open-mastr`.
- **Layer 3 - Economics**: not started.
- **Layer 4 - Simulation**: not started.

## Sources & Licenses

- **Open-Meteo ERA5 historical archive** (Global Tilted Irradiance) - [CC BY 4.0](https://open-meteo.com/en/license)
- **Marktstammdatenregister (MaStR)** - German federal register of power-generation and storage units, bulk XML via [`open-mastr`](https://github.com/OpenEnergyPlatform/open-MaStR); public registry data, self-reported by plant operators
- **Solarkataster NRW** (Land.NRW / Geobasis NRW) - rooftop PV potential cadastre for Duesseldorf; [Datenlizenz Deutschland - Namensnennung - Version 2.0](https://www.govdata.de/dl-de/by-2-0)
- **[deutschlandGeoJSON](https://github.com/isellsoap/deutschlandGeoJSON)** (isellsoap) - German administrative boundaries (Kreis level), GADM/DIVA-GIS derived; project archived

## Limitations

- Solarkataster figures are **theoretical** rooftop potential (shading/geometry model only), not an economic or grid-connection feasibility assessment.
- MaStR is self-reported registry data with known gaps: e.g. usable storage capacity (kWh) is unpopulated at the unit level and had to be joined from a separate plant-level table; a small number of rows have inconsistent Bundesland/Landkreis values.
- ERA5-based yield estimates were validated against 100 Duesseldorf roofs: **+17.1% mean offset** vs. the Solarkataster's own cadastre figure, with a tight **0.28% std** across roofs. The offset is explained by 2025 being an anomalously sunny year in ERA5 versus the DWD climatological baseline the cadastre uses - not a formula error (the tight std confirms the pipeline is internally consistent).
- NRW Kreis boundaries come from a GADM-derived source with pre-2009 administrative boundaries (no native "Städteregion Aachen"); joined to MaStR data via a manual name-normalization mapping.
