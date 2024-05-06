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
    parameter = ['wind-speed','wind-dir'],
    crs = 'crs84',
    to_time = dtnow,
    f = 'GeoJSON',
    coords = [6.00,53.00,17.00,59.00]
)

geo = []
step = []
winddir = []
windspeed = []
for feature in forecast:
    geo.append(feature['geometry']['coordinates'])
    step.append(feature['properties']['step'])
    winddir.append(feature['properties']['wind-dir'])
    windspeed.append(feature['properties']['wind-speed'])

geo = np.asarray(geo)
step = np.asarray(step)
winddir = np.asarray(winddir)
windspeed = np.asarray(windspeed)

ind = np.lexsort((geo[:, 1], geo[:, 0]))

for name,winddir,windspeed in zip(['10m'],[winddir],[windspeed]):
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
