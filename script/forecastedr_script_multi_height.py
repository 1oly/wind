from datetime import datetime
import os
import numpy as np
from scipy.interpolate import griddata
import math
import json
import pytz
from dmi_forecast_edr import DMIForecastEDRClient, Collection

try:
    DMI_API_KEY = os.environ['DMI_API_KEY']
except KeyError:
    DMI_API_KEY = "Token not available!"

client = DMIForecastEDRClient(api_key=DMI_API_KEY)

dtnow = datetime.now(pytz.timezone('Europe/Copenhagen')).replace(tzinfo=None)

forecast = client.get_forecast(
    collection = Collection.HarmonieDiniSf,
    parameter = ['wind-speed-10m','wind-speed-50m','wind-speed-100m','wind-speed-150m','wind-speed-250m','wind-dir-10m','wind-dir-50m','wind-dir-100m','wind-dir-150m','wind-dir-250m'],
    crs = 'crs84',
    to_time = dtnow,
    f = 'GeoJSON',
    coords = [6.00,53.00,17.00,59.00]
)

geo = []
step = []
winddir10 = []
winddir50 = []
winddir100 = []
winddir150 = []
winddir250 = []
windspeed10 = []
windspeed50 = []
windspeed100 = []
windspeed150 = []
windspeed250 = []
for feature in forecast:
    geo.append(feature['geometry']['coordinates'])
    step.append(feature['properties']['step'])
    winddir10.append(feature['properties']['wind-dir-10m'])
    winddir50.append(feature['properties']['wind-dir-50m'])
    winddir100.append(feature['properties']['wind-dir-100m'])
    winddir150.append(feature['properties']['wind-dir-150m'])
    winddir250.append(feature['properties']['wind-dir-250m'])
    windspeed10.append(feature['properties']['wind-speed-10m'])
    windspeed50.append(feature['properties']['wind-speed-50m'])
    windspeed100.append(feature['properties']['wind-speed-100m'])
    windspeed150.append(feature['properties']['wind-speed-150m'])
    windspeed250.append(feature['properties']['wind-speed-250m'])

geo = np.asarray(geo)
step = np.asarray(step)
winddir10 = np.asarray(winddir10)
winddir50 = np.asarray(winddir50)
winddir100 = np.asarray(winddir100)
winddir150 = np.asarray(winddir150)
winddir250 = np.asarray(winddir250)
windspeed10 = np.asarray(windspeed10)
windspeed50 = np.asarray(windspeed50)
windspeed100 = np.asarray(windspeed100)
windspeed150 = np.asarray(windspeed150)
windspeed250 = np.asarray(windspeed250)

ind = np.lexsort((geo[:, 1], geo[:, 0]))

for name,winddir,windspeed in zip(['10m','50m','100m','150m','250m'],[winddir10,winddir50,winddir100,winddir150,winddir250],[windspeed10,windspeed50,windspeed100,windspeed150,windspeed250]):
    geo = geo[ind]
    winddir = winddir[ind]
    windspeed = windspeed[ind]
    u_vector = []
    v_vector = []
    for i in range(geo.shape[0]):
        theta = 270 - winddir[i]
        if theta < 0:
          theta += 360
        theta = math.radians(theta)
        u = windspeed[i] * math.cos(theta)
        v = windspeed[i] * math.sin(theta)
        u_vector.append(u)
        v_vector.append(v)

    # grid interpolation on u and v vectors and option for down-sampling
    loni = np.arange(np.amin(geo[:,0]),np.amax(geo[:,0]),0.5)
    lati = np.arange(np.amax(geo[:,1]),np.amin(geo[:,1]),-0.25)
    loni,lati = np.meshgrid(loni,lati)
    ui = griddata((geo[:,0],geo[:,1]),u_vector,(loni,lati),method='nearest')
    vi = griddata((geo[:,0],geo[:,1]),v_vector,(loni,lati),method='nearest')

    bounds = {'Min lon': np.amin(loni), 'Max lon': np.amax(loni),'Min lat': np.amin(lati), 'Max lat': np.amax(lati)}

    lat_ny,lon_nx = loni.shape

    head_u = {'parameterCategory': 2,
              'parameterNumber': 2,
              'lo1': bounds['Min lon'],
              'la1': bounds['Max lat'],
              'dx': abs((bounds['Min lon'] - bounds['Max lon']) / (lon_nx - 1)),
              'dy': abs((bounds['Min lat'] - bounds['Max lat']) / (lat_ny - 1)),
              'nx': lon_nx,  # lon W-E
              'ny': lat_ny,  # lat S-N
              'refTime': step[0]}
    head_v = head_u.copy()
    head_v['parameterNumber'] = 3
    out_data = [{'header': head_u,
                      'data': list(ui.flatten())},
                     {'header': head_v,
                      'data': list(vi.flatten())}]

    with open("wind{}.json".format(name), 'w') as f:
        json.dump(out_data, f)
