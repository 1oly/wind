import pandas as pd 
import geopandas
years = [f'Y{x}' for x in range(1977,2024)]
df = pd.read_excel('anlaeg.xlsx',skiprows=13,header=0,usecols='A:BI,BU',
    names = ['id', 'date_connect','date_decom', 'capacity_kW', 'rotor_diam_m',
       'hub_height_m', 'manufacturer', 'type', 'auth',
       'location', 'district', 'district_no',
       'X_UTM_32_ETRS89',
       'Y_UTM_32_ETRS89','coord_origin']+years)

points = geopandas.points_from_xy(x=df.X_UTM_32_ETRS89, y=df.Y_UTM_32_ETRS89,crs="EPSG:25832")
gdf = geopandas.GeoDataFrame(df, geometry=points).to_crs("EPSG:4326")
gdf.to_file('wt_2023.json', driver='GeoJSON')