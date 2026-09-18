"""Merge turbine master data and production into one GeoJSON.

Sources:
  data_2025-01.xlsx   every turbine ever connected, monthly production 1977-2024
  Vinddata.xlsx       active turbines, monthly production 2023 onward (Danish decimal commas)
  Parkproduktion.xlsx monthly production per wind park; turbines in a park report no production of their own
'Historiske vinddata.xlsx' is not needed: its turbines and values are already in the old file.
"""
import re

import geopandas
import pandas as pd

META_COLUMNS = [
    'id', 'date_connect', 'date_decom', 'capacity_kW', 'rotor_diam_m', 'hub_height_m',
    'manufacturer', 'type', 'auth', 'location', 'district', 'district_no',
    'X_UTM_32_ETRS89', 'Y_UTM_32_ETRS89', 'coord_origin',
]


def _year(col) -> str | None:
    m = re.match(r'^(\d{4})', str(col))
    return m.group(1) if m else None


def _danish_number(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.astype(str).str.replace(',', '.', regex=False), errors='coerce')


def _tidy(df: pd.DataFrame) -> pd.DataFrame:
    """Rename the leading meta columns, parse numbers and dates, collapse months to years."""
    df = df.rename(columns=dict(zip(df.columns[:len(META_COLUMNS)], META_COLUMNS)))
    df['id'] = df['id'].astype(str)
    df = df.drop_duplicates('id').set_index('id')
    year_cols = [c for c in df.columns if _year(c)]
    numeric = df[year_cols].apply(_danish_number)
    numeric.columns = [_year(c) for c in year_cols]
    numeric = numeric.T.groupby(level=0).sum(min_count=1).T
    for c in ('capacity_kW', 'rotor_diam_m', 'hub_height_m', 'X_UTM_32_ETRS89', 'Y_UTM_32_ETRS89'):
        df[c] = _danish_number(df[c])
    df['date_connect'] = pd.to_datetime(df['date_connect'].astype(str), errors='coerce').dt.strftime('%Y-%m-%d')
    df['date_decom'] = pd.to_datetime(df['date_decom'].astype(str), errors='coerce').dt.strftime('%Y-%m-%d')
    return pd.concat([df[META_COLUMNS[1:]], numeric], axis=1)


old = _tidy(pd.read_excel('data_2025-01.xlsx', skiprows=10, header=0, usecols='A:CR'))

raw = pd.read_excel('Vinddata.xlsx', header=2)
park_of = raw.set_index(raw.iloc[:, 0].astype(str))['Parknummer (relation)'].dropna()
park_of = park_of[~park_of.index.duplicated()]
raw = raw.drop(columns=['Parknummer (relation)'])
# the sheet's 'Kommune' and 'Type af placering' headers are swapped relative to the data
cols = list(raw.columns)
i, j = cols.index('Kommune'), cols.index('Type af placering')
cols[i], cols[j] = cols[j], cols[i]
new = _tidy(raw[cols])

# park production, shared out to member turbines by capacity
# ponytail: pro-rata by capacity ignores a turbine decommissioned mid-year; refine if a park's members change often
park = pd.read_excel('Parkproduktion.xlsx', header=1).drop_duplicates('Parknummer (relation)').set_index('Parknummer (relation)')
park = park.apply(_danish_number)
park.columns = [_year(c) for c in park.columns]
park = park.T.groupby(level=0).sum(min_count=1).T
park_of = park_of[park_of.index.isin(new.index)]
members = new.loc[park_of.index]
share = members['capacity_kW'] / members.groupby(park_of)['capacity_kW'].transform('sum')
allocated = park.reindex(park_of.values).set_index(park_of.index).mul(share, axis=0)
new = new.combine_first(allocated)

# new file wins for master data and recent years; old file wins for the years it covers,
# since it has measured per-turbine values where the new file only has a park estimate
old_years = [c for c in old.columns if _year(c)]
df = new.combine_first(old)
df[old_years] = old[old_years].combine_first(df[old_years])
year_cols = sorted(c for c in df.columns if _year(c))
df = df[META_COLUMNS[1:] + year_cols].rename_axis('id').reset_index()

points = geopandas.points_from_xy(x=df.X_UTM_32_ETRS89, y=df.Y_UTM_32_ETRS89, crs="EPSG:25832")
gdf = geopandas.GeoDataFrame(df, geometry=points).to_crs("EPSG:4326")
gdf.to_file('wt_2025jan.json', driver='GeoJSON')

# self-check: nothing lost, and the overlap year agrees between sources
assert len(df) == len(set(old.index) | set(new.index)), 'turbines lost in merge'
assert df.X_UTM_32_ETRS89.notna().sum() >= old.X_UTM_32_ETRS89.notna().sum(), 'coordinates lost in merge'
shared = old.index.intersection(new.index)
both = new.loc[shared, '2024'].dropna()
assert abs(both.sum() / old.loc[both.index, '2024'].sum() - 1) < 0.01, '2024 totals disagree between files'
print(f"{len(df)} turbines, years {year_cols[0]}-{year_cols[-1]}, "
      f"{df[year_cols[-1]].notna().sum()} with {year_cols[-1]} production")
