# Wind visualization
"Real-time" (once per hour) wind visualization from forecast model Harmonie via the Danish Meterological Institute. 

Data is retrieved with the [DMI-Forecast-EDR-API](https://github.com/1oly/dmi-forecast-edr) that requires an API key.

Visualization is done via a combination of [leaflet-velocity](https://github.com/onaci/leaflet-velocity) and [windy](https://github.com/Wolfrax/windy). 

## Data sources
- Basemap is courtesy of: (https://www.openstreetmap.org/copyright)[OpenStreetMap contributors] and (https://carto.com/attributions)[CARTO].  
- Wind data is from Harmonie forecast model run by (https://www.dmi.dk)[DMI] via (https://confluence.govcloud.dk/display/FDAPI/Danish+Meteorological+Institute+-+Open+Data)[DMI Open Data]. Updated every hour using Github Actions running a python script (`script/forecastedr_script.py`).
- Wind turbine data is from (https://ens.dk/service/statistik-data-noegletal-og-kort/download-gis-filer)[Energistyrelsen] (the Danish Energy Agency). Updated once per year. Data conversion by `ogr2ogr`:
```
ogr2ogr -f GeoJSON -t_srs crs:84 wt.geojson stamdata_eksisterende_moeller_xxxx.shp
```