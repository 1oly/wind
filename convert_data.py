import re

import geopandas
import pandas as pd


META_COLUMNS = [
    'id',
    'date_connect',
    'date_decom',
    'capacity_kW',
    'rotor_diam_m',
    'hub_height_m',
    'manufacturer',
    'type',
    'auth',
    'location',
    'district',
    'district_no',
    'X_UTM_32_ETRS89',
    'Y_UTM_32_ETRS89',
    'coord_origin',
]


def _extract_year(value) -> str | None:
    match = re.match(r'^(\d{4})', str(value))
    return match.group(1) if match else None


def _collapse_to_years(frame: pd.DataFrame) -> pd.DataFrame:
    numeric_cols = [col for col in frame.columns if _extract_year(col)]
    if not numeric_cols:
        return frame
    numeric_df = frame[numeric_cols].copy()
    numeric_df.columns = [_extract_year(col) for col in numeric_df.columns]
    numeric_df = numeric_df.groupby(by=numeric_df.columns, axis=1).sum(numeric_only=True, min_count=1)
    return pd.concat([frame.drop(columns=numeric_cols), numeric_df], axis=1)


df = pd.read_excel('data_2025-01.xlsx', skiprows=10, header=0, usecols='A:CR')
rename_limit = min(len(META_COLUMNS), len(df.columns))
column_map = {df.columns[i]: META_COLUMNS[i] for i in range(rename_limit)}
df = df.rename(columns=column_map)
df = _collapse_to_years(df)

points = geopandas.points_from_xy(
    x=df.X_UTM_32_ETRS89,
    y=df.Y_UTM_32_ETRS89,
    crs="EPSG:25832",
)
gdf = geopandas.GeoDataFrame(df, geometry=points).to_crs("EPSG:4326")
gdf.to_file('wt_2025jan.json', driver='GeoJSON')
