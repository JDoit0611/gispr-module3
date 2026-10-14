# [Python] Section 1 — Data setup: paths, course CRS, hosted layer URL
from pathlib import Path

DATA = Path(r"C:\Users\Jordan\Desktop\ArcGIS\510 Python & R\3\GISPR_Module3_Data\data")  # the unzipped GISPR_Module3_Data/data folder
OUT  = Path(r"C:\Users\Jordan\Desktop\ArcGIS\510 Python & R\3\Outputs"); OUT.mkdir(exist_ok=True) # or where you want outputs
COURSE_EPSG = 2926                        # NAD83(HARN) / Washington North (US survey feet)

# Paste the REST URL of the "GISPR Salmon Observations" hosted layer (posted on Canvas)
SALMON_OBS_URL = 'https://services2.arcgis.com/xv4COPn03HHYL16S/arcgis/rest/services/GISPR_Salmon_Observations/FeatureServer/0'

expected = ['salmon_watersheds.gdb', 'parcels.gdb', 'salmon_watersheds.gpkg',
            'salmon_obs_partner_agency.geojson', 'salmon_obs.csv', 'salmon_obs_agency2.csv',
            'monitoring_sites.csv', 'obs.csv', 'parcels.shp', 'no_crs.shp', 'in_4326.shp',
            'salmon_observations_hosted_backup.gpkg']
missing = [f for f in expected if not (DATA / f).exists()]
if missing:
    print(f"⚠️  Missing from {DATA.resolve()}: {missing}\n    Unzip GISPR_Module3_Data.zip next to this notebook.")
else:
    print(f"✅  All Module 3 data files found in {DATA.resolve()}")
if '<org>' in SALMON_OBS_URL:
    print("ℹ️  SALMON_OBS_URL not set yet — hosted-layer cells will use the offline backup.")

def sedf_to_gdf(sdf):
    """Spatially Enabled DataFrame -> GeoDataFrame. Works whether or not your arcgis
    version has sdf.spatial.to_geodataframe()."""
    import geopandas as gpd
    if hasattr(sdf.spatial, "to_geodataframe"):
        return fiona_safe(sdf.spatial.to_geodataframe())
    geom_col = getattr(sdf.spatial, "name", None) or "SHAPE"
    sr = sdf.spatial.sr
    epsg = sr.get("latestWkid") or sr.get("wkid")
    geoms = gpd.GeoSeries.from_wkt(sdf[geom_col].apply(lambda g: None if g is None else g.WKT), crs=epsg)
    return fiona_safe(gpd.GeoDataFrame(sdf.drop(columns=geom_col), geometry=geoms))

def list_layers(path):
    """Layer names in a GeoPackage/GDB — works with or without pyogrio installed."""
    import pandas as pd, geopandas as gpd
    try:
        return gpd.list_layers(path)            # needs pyogrio
    except ImportError:
        import fiona                            # ships with the ArcGIS Pro / older geopandas envs
        return pd.DataFrame({"name": fiona.listlayers(str(path))})

def fiona_safe(gdf):
    """Plain numpy dtypes for writing with the fiona engine (it can't handle pandas
    nullable dtypes like Float64/Int64/string, which ArcGIS SeDFs use). pyogrio doesn't need this."""
    import pandas as pd
    out = gdf.copy()
    geom = out.geometry.name
    for col in out.columns:
        dt = out[col].dtype
        if col == geom or not isinstance(dt, pd.api.extensions.ExtensionDtype) or isinstance(dt, pd.DatetimeTZDtype):
            continue
        if pd.api.types.is_float_dtype(dt) or (pd.api.types.is_integer_dtype(dt) and out[col].isna().any()):
            out[col] = out[col].astype("float64")
        elif pd.api.types.is_integer_dtype(dt):
            out[col] = out[col].astype("int64")
        else:                                   # string, boolean, categorical, ...
            out[col] = out[col].map(lambda v: None if pd.isna(v) else str(v)).astype(object)
    return out
    

# [Python / ArcPy] Reading vector data from a File Geodatabase
# Runs live in ArcGIS Pro's Notebook (or a cloned arcgispro-py3 env). Anywhere arcpy isn't installed,
# it falls back to GeoPandas — GDAL's OpenFileGDB driver reads .gdb feature classes with no license.
import os
import pandas as pd
import geopandas as gpd
from pathlib import Path

DATA = Path(r"C:\Users\Jordan\Desktop\ArcGIS\510 Python & R\3\GISPR_Module3_Data\data") # put the path to the data file on your machine just like we did above

gdb = str((DATA / 'salmon_watersheds.gdb').resolve())

try:
    import arcpy
    arcpy.env.workspace = gdb

    # ── List all feature classes in the GDB ──────────────────────────────────
    print("Feature classes:", arcpy.ListFeatureClasses())

    # ── Describe a feature class — geometry type, CRS ────────────────────────
    desc = arcpy.Describe('watersheds')
    print("Geometry type:", desc.shapeType)
    print("Spatial reference:", desc.spatialReference.name, "| WKID:", desc.spatialReference.factoryCode)

    # ── Option 1: row-by-row read with SearchCursor ──────────────────────────
    with arcpy.da.SearchCursor('watersheds', ["WATERSHED_ID", "WATERSHED_NAME"]) as cur:
        rows = [row for row in cur]
    print(f"Read {len(rows)} rows via SearchCursor:", rows[:2])

    # ── Option 2: read directly into a Spatially Enabled DataFrame ───────────
    from arcgis.features import GeoAccessor
    watersheds_sdf = pd.DataFrame.spatial.from_featureclass(os.path.join(gdb, 'watersheds'))
    print("SeDF CRS:", watersheds_sdf.spatial.sr, "| shape:", watersheds_sdf.shape)   # wkid 2926

except ImportError:
    print("arcpy not available here — reading the same GDB with GeoPandas instead\n")
    print("Feature classes:", list(list_layers(gdb)['name']))
    watersheds_gdb = gpd.read_file(gdb, layer='watersheds')
    print("Geometry type:", watersheds_gdb.geom_type.unique())
    print("CRS:", watersheds_gdb.crs.name, "| EPSG:", watersheds_gdb.crs.to_epsg())
    print(watersheds_gdb[['WATERSHED_ID', 'WATERSHED_NAME']].head(3))

# [Python] CRS inspection, assignment, and reprojection
import geopandas as gpd
import pandas as pd

# Build a salmon observations GeoDataFrame (synthetic data — no file download needed)
obs_df = pd.DataFrame({
    'obs_id':   ['OBS001', 'OBS002', 'OBS003', 'OBS004', 'OBS005'],
    'species':  ['Chinook', 'Coho', 'Chinook', 'Sockeye', 'Coho'],
    'lon':      [-122.3088, -122.4500, -122.5403, -122.6200, -122.3700],
    'lat':      [  47.6062,   47.5800,   47.6500,   47.7100,   47.5500],
    'count':    [12, 5, 8, 21, 3]
})
obs_4326 = gpd.GeoDataFrame(
    obs_df,
    geometry=gpd.points_from_xy(obs_df['lon'], obs_df['lat']),
    crs='EPSG:4326'
)

# ── Inspect CRS ───────────────────────────────────────────────────────────────
print("CRS:",            obs_4326.crs)
print("EPSG code:",      obs_4326.crs.to_epsg())
print("Is geographic?:", obs_4326.crs.is_geographic)
print("Is projected?:",  obs_4326.crs.is_projected)

# ── set_crs() — assigns a label only, does NOT move coordinates ──────────────
obs_no_crs = obs_4326.copy()
obs_no_crs.crs = None                         # strip CRS for demo
obs_reassigned = obs_no_crs.set_crs('EPSG:4326')   # assign — coordinates unchanged
print("\nAfter set_crs — same coordinates, label restored:", obs_reassigned.crs)

# ── to_crs() — actually transforms coordinates to the course standard ────────
obs_2926 = obs_4326.to_crs('EPSG:2926')
print("\nAfter to_crs(2926) — coordinates transformed:")
print(obs_2926.geometry.head(2))
print("New CRS:", obs_2926.crs)

# [Python] Attribute table cleaning — same logic as ArcGIS Pro's "Calculate Field" and "Select by Attribute",
# but reproducible, batch-able, and auditable.
import pandas as pd
import geopandas as gpd

# Simulate a messy watershed table — inconsistent casing, stray whitespace, mixed types, some nulls
messy = pd.DataFrame({
    ' Watershed ID ':   ['WS-01', 'WS-02', 'WS-03', None, 'WS-05'],
    'Watershed Name':   ['Cedar River', 'Issaquah Creek', 'Bear Creek', 'Unnamed', 'Soos Creek'],
    'Area_SqFt':        ['4521000', '2110500', 'bad_value', '8870000', '3340000'],
    'Survey Date':      ['2023-04-01', '2023-04-15', '2023/05/02', None, '2023-05-20'],
})

# 1. Column name standardization
messy.columns = (
    messy.columns.str.lower()
    .str.strip()
    .str.replace(" ", "_", regex=False)
    .str.replace(r"[^a-z0-9_]", "", regex=True)
)
print("Standardized columns:", list(messy.columns))

# 2. Data type fixes — unparseable values become NaN, not a crash
messy["area_sqft"]   = pd.to_numeric(messy["area_sqft"], errors="coerce")
messy["survey_date"] = pd.to_datetime(messy["survey_date"], errors="coerce")
print("\nAfter type coercion:")
print(messy[["area_sqft", "survey_date"]])

# 3. Drop rows missing the key join field
clean = messy.dropna(subset=["watershed_id", "area_sqft"])
print(f"\n{len(clean)}/{len(messy)} rows kept after dropping nulls in key fields")
print(clean)

# [Python] Tabular → Spatial — promote a salmon observation CSV to a GeoDataFrame
import pandas as pd
import geopandas as gpd

# Simulate the salmon observation CSV (in production: pd.read_csv('data/salmon_obs.csv'))
obs_csv = pd.DataFrame({
    'obs_id':  ['OBS101', 'OBS102', 'OBS103', 'OBS104'],
    'species': ['Chinook', 'Coho', 'Sockeye', 'Chinook'],
    'lon':     [-122.3088, -122.4500, -122.5403, -122.2900],
    'lat':     [  47.6062,   47.5800,   47.6500,   47.5200],
    'count':   [14, 6, 22, 9]
})

# CRITICAL: points_from_xy(x=LON, y=LAT) — longitude first, latitude second
obs_gdf = gpd.GeoDataFrame(
    obs_csv,
    geometry=gpd.points_from_xy(
        obs_csv["lon"],   # x = longitude
        obs_csv["lat"]),  # y = latitude
    crs="EPSG:4326"
)

# ── Mandatory sanity checks ───────────────────────────────────────────────────
print("Is valid:",        obs_gdf.geometry.is_valid.all())   # True
print("Row count match:", len(obs_gdf) == len(obs_csv))      # True
print("Geometry type:",   obs_gdf.geom_type.unique())

# ── Mandatory plot check — catches a swapped lon/lat instantly ───────────────
obs_gdf.plot()  # Should show points clustered around Western Washington, not the ocean

# [Python] Export a clean, multi-layer GeoPackage — the preferred delivery format
import geopandas as gpd
import pandas as pd
from shapely.geometry import box
import os

os.makedirs(OUT, exist_ok=True)               # OUT is set in the setup cell

# ── Layer 1: salmon observations (built in Section 4, reprojected to course standard) ──
obs_csv = pd.DataFrame({
    'obs_id':  ['OBS101', 'OBS102', 'OBS103', 'OBS104'],
    'species': ['Chinook', 'Coho', 'Sockeye', 'Chinook'],
    'lon':     [-122.3088, -122.4500, -122.5403, -122.2900],
    'lat':     [  47.6062,   47.5800,   47.6500,   47.5200],
    'count':   [14, 6, 22, 9]
})
obs_gdf = gpd.GeoDataFrame(
    obs_csv,
    geometry=gpd.points_from_xy(obs_csv["lon"], obs_csv["lat"]),
    crs="EPSG:4326"
).to_crs(epsg=2926)

# ── Layer 2: watershed polygons (synthetic stand-in for a GDB/GeoPackage layer) ──
watersheds = gpd.GeoDataFrame({
    'watershed_id':   ['WS-01', 'WS-02', 'WS-03'],
    'watershed_name': ['Cedar River', 'Issaquah Creek', 'Bear Creek'],
    'geometry': [
        box(-122.35, 47.58, -122.28, 47.64),
        box(-122.48, 47.55, -122.40, 47.61),
        box(-122.58, 47.62, -122.50, 47.68),
    ]
}, crs='EPSG:4326').to_crs(epsg=2926)

# ── Confirm both layers share a CRS before writing ────────────────────────────
assert obs_gdf.crs.to_epsg() == watersheds.crs.to_epsg() == 2926
print("✅  Both layers confirmed in EPSG:2926")

# ── Write the harmonized GeoPackage — one file, two layers ────────────────────
output_path = str(OUT / 'salmon_watersheds_harmonized.gpkg')   # str() keeps older fiona happy
obs_gdf.to_file(output_path, driver='GPKG', layer='salmon_observations')
watersheds.to_file(output_path, driver='GPKG', layer='watersheds')

import fiona
print(f"\n✅  Wrote {output_path}")
print("Layers:", fiona.listlayers(output_path))

# [Python] Lab Step 1 — Load & Inspect
import pandas as pd
import geopandas as gpd

def describe(name, gdf):
    epsg = gdf.crs.to_epsg() if gdf.crs else None
    print(f"{name:<20} {', '.join(gdf.geom_type.unique()):<14} n={len(gdf):<4} EPSG:{epsg}")

# 1. File Geodatabase feature class (agency-maintained). In ArcGIS Pro you could use
#    pd.DataFrame.spatial.from_featureclass() — see Section 1a. GeoPandas reads it anywhere.
watersheds_raw = gpd.read_file(DATA / 'salmon_watersheds.gdb', layer='watersheds')

# 2. Hosted feature layer — ArcGIS API for Python, with an offline fallback
try:
    from arcgis.gis import GIS
    from arcgis.features import FeatureLayer
    if '<org>' in SALMON_OBS_URL:
        raise ValueError("SALMON_OBS_URL not set in Section 1")
    gis = GIS('home')                                   # sign-in required (group-shared layer)
    obs_hosted_raw = sedf_to_gdf(FeatureLayer(SALMON_OBS_URL, gis=gis).query().sdf)
except Exception as e:
    print(f"(hosted layer unavailable: {type(e).__name__}: {e} — using offline backup)\n")
    obs_hosted_raw = gpd.read_file(DATA / 'salmon_observations_hosted_backup.gpkg')

# 3. Partner agency GeoJSON
obs_partner_raw = gpd.read_file(DATA / 'salmon_obs_partner_agency.geojson')

# 4. Field-crew CSV — tabular, no geometry yet
obs_raw = pd.read_csv(DATA / 'salmon_obs.csv')

describe('watersheds (GDB)', watersheds_raw)
describe('obs (hosted)', obs_hosted_raw)
describe('obs (partner)', obs_partner_raw)

print("\nField CSV shape:", obs_raw.shape)
print("\nDtypes:\n", obs_raw.dtypes)
print("\nNull counts:\n", obs_raw.isna().sum())

# [Python] Lab Step 2 — CRS Check & Reproject
layers = {'watersheds': watersheds_raw,
          'salmon_obs_hosted': obs_hosted_raw,
          'salmon_obs_partner': obs_partner_raw}

print("CRS before:", {name: g.crs.to_epsg() for name, g in layers.items()})   # three different CRSs!

aligned = {name: g.to_crs(epsg=COURSE_EPSG) for name, g in layers.items()}   # or ensure_same_crs() from 2c

for name, g in aligned.items():
    assert g.crs.to_epsg() == COURSE_EPSG, f"{name}: reprojection failed — check the CRS"
print("CRS after: ", {name: g.crs.to_epsg() for name, g in aligned.items()})
print(f"✅  All spatial layers confirmed in EPSG:{COURSE_EPSG}")

watersheds_2926  = aligned['watersheds']
obs_hosted_2926  = aligned['salmon_obs_hosted']
obs_partner_2926 = aligned['salmon_obs_partner']

# [Python] Lab Step 3 — Clean Attributes
import re

def clean_columns(df):
    """lowercase, strip, spaces→underscores, drop punctuation — leaves the geometry column alone"""
    geom = df.geometry.name if isinstance(df, gpd.GeoDataFrame) else None
    std = lambda c: re.sub(r"[^a-z0-9_]", "", c.lower().strip().replace(" ", "_"))
    return df.rename(columns={c: std(c) for c in df.columns if c != geom})

obs = clean_columns(obs_raw)
print("Standardized columns:", list(obs.columns))

# Fix data types — unparseable values become NaN/NaT, not a crash
obs["count"] = pd.to_numeric(obs["count"], errors="coerce")
obs["survey_date"] = pd.to_datetime(obs["survey_date"], format="mixed", errors="coerce")
obs["species"] = obs["species"].str.strip().str.title()          # ' coho ' → 'Coho'
print("Species values:", sorted(obs["species"].unique()))
print("Unparseable counts →", obs["count"].isna().sum(), "NaN (kept, but flagged)")

# Drop rows missing the key field (obs_id)
obs_clean = obs.dropna(subset=["obs_id"]).copy()
print(f"\n{len(obs_clean)}/{len(obs)} rows kept after dropping nulls in obs_id")

# Same column standardization on the spatial layers
watersheds_2926  = clean_columns(watersheds_2926)
obs_hosted_2926  = clean_columns(obs_hosted_2926)
obs_partner_2926 = clean_columns(obs_partner_2926)
print("\nwatersheds:", list(watersheds_2926.columns))
print("partner:   ", list(obs_partner_2926.columns))

# [Python] Lab Step 4 — Tabular → Spatial
# CRITICAL: points_from_xy(x=LON, y=LAT) — longitude first, latitude second
obs_field_2926 = gpd.GeoDataFrame(
    obs_clean,
    geometry=gpd.points_from_xy(obs_clean["longitude"], obs_clean["latitude"]),
    crs="EPSG:4326"
).to_crs(epsg=COURSE_EPSG)

print("Row count match:", len(obs_field_2926) == len(obs_clean))   # True
print("Geometry type:  ", obs_field_2926.geom_type.unique())
print("CRS:            ", obs_field_2926.crs.to_epsg())

# Mandatory plot check — points should sit on the streams inside the watersheds, not in Puget Sound
ax = watersheds_2926.plot(color="#eeeeee", edgecolor="grey", figsize=(7, 8))
obs_hosted_2926.plot(ax=ax, color="tab:blue", markersize=10, label="hosted")
obs_partner_2926.plot(ax=ax, color="tab:green", marker="s", markersize=12, label="partner")
obs_field_2926.plot(ax=ax, color="tab:orange", marker="^", markersize=16, label="field CSV")
ax.legend(); ax.set_title("Module 3 intake — all layers in EPSG:2926")

# [Python] Lab Step 5 — Export Harmonized Output
output_gpkg = OUT / 'module3_lab_output.gpkg'
if output_gpkg.exists():
    output_gpkg.unlink()                         # start clean on re-runs

out_layers = {'watersheds': watersheds_2926,
              'salmon_obs_hosted': obs_hosted_2926,
              'salmon_obs_partner': obs_partner_2926,
              'salmon_obs_field': obs_field_2926}

for name, g in out_layers.items():
    assert g.crs.to_epsg() == COURSE_EPSG, f"{name} is not in EPSG:{COURSE_EPSG}"
    fiona_safe(g).to_file(str(output_gpkg), layer=name, driver='GPKG')   # fiona_safe: see setup cell

print(f"✅  Wrote {output_gpkg}")
print(list_layers(str(output_gpkg)))
print("\nNext step (Module 4): a spatial join will populate watershed_name on each observation —")
print("that's the first spatial operation you'll run on this exact GeoPackage next week.")

# [Python] Option A — Spatial Join Warm-Up
# This previews Module 4. You are not expected to master predicates tonight —
# just see how directly tonight's GeoPackage feeds next week's first operation.
# R equivalent:  st_join(obs_field, aligned$watersheds["watershed_name"], join = st_within)

joined = gpd.sjoin(obs_field_2926, watersheds_2926[['watershed_id', 'watershed_name', 'geometry']],
                   how='left', predicate='within')
print(joined[['obs_id', 'species', 'count', 'watershed_name']].head(10))
print("\nObservations per watershed:\n", joined['watershed_name'].value_counts(dropna=False))

# Try the partner layer too — two partner points fall outside every watershed. Why might that be?

print("OBS207" in obs_field_2926["obs_id"].values)


# Check for which points are outside the watershed
joined_p = gpd.sjoin(obs_partner_2926,
                     watersheds_2926[['watershed_id', 'watershed_name', 'geometry']],
                     how='left', predicate='within')

outside = joined_p[joined_p['watershed_name'].isna()]
print(f"Partner points outside every watershed: {len(outside)}")
print(outside.drop(columns='geometry'))

# How far outside are they? Distance to the nearest watershed
near = gpd.sjoin_nearest(outside.drop(columns=['index_right', 'watershed_id', 'watershed_name']),
                         watersheds_2926[['watershed_name', 'geometry']],
                         distance_col='dist_ft')
print(near[['watershed_name', 'dist_ft']])

# 2. Check precision of partner coordinates
print(outside.to_crs(4326).geometry.apply(lambda p: (round(p.x, 6), round(p.y, 6))))


