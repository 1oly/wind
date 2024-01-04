# Wind visualization
"Real-time" (once per hour) wind visualization from forecast model Harmonie via the Danish Meterological Institute. 

Data is retrieved with the [DMI-Forecast-EDR-API](https://github.com/1oly/dmi-forecast-edr) that requires an API key.

Visualization is done via a combination of [leaflet-velocity](https://github.com/onaci/leaflet-velocity) and [windy](https://github.com/Wolfrax/windy). 

## Data sources
- Basemap is courtesy of: [OpenStreetMap contributors](https://www.openstreetmap.org/copyright) and [CARTO](https://carto.com/attributions).  
- Wind data is from Harmonie forecast model run by [DMI](https://www.dmi.dk) via [DMI Open Data](https://confluence.govcloud.dk/display/FDAPI/Danish+Meteorological+Institute+-+Open+Data). Updated every hour using Github Actions running a python script (`script/forecastedr_script.py`).
- Wind turbine data is from [Energistyrelsen](https://ens.dk/service/statistik-data-noegletal-og-kort/download-gis-filer) (the Danish Energy Agency). Updated once per year. Data conversion by `ogr2ogr`:
```
ogr2ogr -f GeoJSON -t_srs crs:84 wt.geojson stamdata_eksisterende_moeller_xxxx.shp
```