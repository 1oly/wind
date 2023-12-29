from datetime import datetime
import os
import numpy as np
from scipy.interpolate import griddata
import math
import json

from dmi_forecast_edr import DMIForecastEDRClient, Collection

try:
    DMI_API_KEY = os.environ['DMI_API_KEY']
except KeyError:
    DMI_API_KEY = "Token not available!"

client = DMIForecastEDRClient(api_key=DMI_API_KEY)

dtnow = datetime.now()

forecast = client.get_forecast(
    collection = Collection.HarmonieNeaSf,
    parameter = ['wind-speed','wind-dir'],
    crs = 'crs84',
    to_time = dtnow,
    f = 'GeoJSON',
    coords = [7.00,54.00,16.00,58.00]
)

# Returns non-gridded data that does not fit into wind.js grid.
# maybe project geojson 'crs84' into web mercator?

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

wind = np.column_stack((geo,winddir,windspeed))

points_per_step = int(len(forecast)/len(np.unique(step)))
wind = wind[0:points_per_step]

ind = np.lexsort((wind[:, 1], wind[:, 0]))
wind = wind[ind]

u_vector = []
v_vector = []
for i in range(wind.shape[0]):
    theta = 270 - wind[i][2]
    if theta < 0:
      theta += 360
    theta = math.radians(theta)
    u = wind[i][3] * math.cos(theta)
    v = wind[i][3] * math.sin(theta)
    u_vector.append(u)
    v_vector.append(v)

wind = np.column_stack((wind, u_vector, v_vector))

# grid interpolation on u and v vectors and option for down-sampling
loni = np.arange(np.amin(wind[:,0]),np.amax(wind[:,0]),0.5)
lati = np.arange(np.amax(wind[:,1]),np.amin(wind[:,1]),-0.25)
loni,lati = np.meshgrid(loni,lati)
ui = griddata((wind[:,0],wind[:,1]),wind[:,4],(loni,lati),method='nearest')
vi = griddata((wind[:,0],wind[:,1]),wind[:,5],(loni,lati),method='nearest')

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

with open("wind.json", 'w') as f:
   json.dump(out_data, f)
