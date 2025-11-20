from datetime import datetime
import os
import numpy as np
from scipy.interpolate import griddata
import math
import json
import pytz
from dmi_forecast_edr import DMIForecastEDRClient, Collection

HEIGHTS = ['10m', '50m', '100m', '150m', '250m', '350m', '450m']

try:
    DMI_API_KEY = os.environ['DMI_API_KEY']
except KeyError:
    DMI_API_KEY = "Token not available!"

client = DMIForecastEDRClient(api_key=DMI_API_KEY)

dtnow = datetime.now(pytz.timezone('Europe/Copenhagen')).replace(tzinfo=None)

forecast = client.get_forecast(
    collection=Collection.HarmonieDiniSf,
    parameter=[f'wind-speed-{h}' for h in HEIGHTS] + [f'wind-dir-{h}' for h in HEIGHTS],
    crs='crs84',
    to_time=dtnow,
    f='GeoJSON',
    coords=[3.00, 52.00, 20.00, 65.00]
)

geo = []
step = []
winddir_data = {height: [] for height in HEIGHTS}
windspeed_data = {height: [] for height in HEIGHTS}
for feature in forecast:
    geo.append(feature['geometry']['coordinates'])
    step.append(feature['properties']['step'])
    props = feature['properties']
    for height in HEIGHTS:
        winddir_data[height].append(props[f'wind-dir-{height}'])
        windspeed_data[height].append(props[f'wind-speed-{height}'])

geo = np.asarray(geo)
step = np.asarray(step)
winddir_data = {height: np.asarray(values) for height, values in winddir_data.items()}
windspeed_data = {height: np.asarray(values) for height, values in windspeed_data.items()}

ind = np.lexsort((geo[:, 1], geo[:, 0]))
geo_sorted = geo[ind]
step_sorted = step[ind]
ref_time = step_sorted[0] if step_sorted.size else None

for height in HEIGHTS:
    winddir = winddir_data[height][ind]
    windspeed = windspeed_data[height][ind]
    u_vector = []
    v_vector = []
    for i in range(geo_sorted.shape[0]):
        theta = 270 - winddir[i]
        if theta < 0:
          theta += 360
        theta = math.radians(theta)
        u = windspeed[i] * math.cos(theta)
        v = windspeed[i] * math.sin(theta)
        u_vector.append(u)
        v_vector.append(v)

    # grid interpolation on u and v vectors and option for down-sampling
    loni = np.arange(np.amin(geo_sorted[:, 0]), np.amax(geo_sorted[:, 0]), 0.5)
    lati = np.arange(np.amax(geo_sorted[:, 1]), np.amin(geo_sorted[:, 1]), -0.25)
    loni, lati = np.meshgrid(loni, lati)
    ui = griddata((geo_sorted[:, 0], geo_sorted[:, 1]), u_vector, (loni, lati), method='nearest')
    vi = griddata((geo_sorted[:, 0], geo_sorted[:, 1]), v_vector, (loni, lati), method='nearest')

    bounds = {'Min lon': np.amin(loni), 'Max lon': np.amax(loni), 'Min lat': np.amin(lati), 'Max lat': np.amax(lati)}

    lat_ny, lon_nx = loni.shape

    head_u = {'parameterCategory': 2,
              'parameterNumber': 2,
              'lo1': bounds['Min lon'],
              'la1': bounds['Max lat'],
              'dx': abs((bounds['Min lon'] - bounds['Max lon']) / (lon_nx - 1)),
              'dy': abs((bounds['Min lat'] - bounds['Max lat']) / (lat_ny - 1)),
              'nx': lon_nx,  # lon W-E
              'ny': lat_ny,  # lat S-N
              'refTime': ref_time}
    head_v = head_u.copy()
    head_v['parameterNumber'] = 3
    out_data = [{'header': head_u,
                      'data': list(ui.flatten())},
                     {'header': head_v,
                      'data': list(vi.flatten())}]

    with open("wind{}.json".format(height), 'w') as f:
        json.dump(out_data, f)
