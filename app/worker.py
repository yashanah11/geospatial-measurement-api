import os
import geopandas as gpd
import fiona
from sqlalchemy.orm import Session
from app.models import GeoFile, FeatureMeasurement

# Enable KML driver in Fiona
fiona.drvsupport.supported_drivers['KML'] = 'rw'
fiona.drvsupport.supported_drivers['LIBKML'] = 'rw'

def process_geospatial_file(file_id: str, file_path: str, db: Session):
    geo_file = db.query(GeoFile).filter(GeoFile.id == file_id).first()
    if not geo_file:
        return

    geo_file.status = "PROCESSING"
    db.commit()

    try:
        gdf = gpd.read_file(file_path)
        
        geo_file.crs = str(gdf.crs) if gdf.crs else "UNKNOWN"
        geo_file.feature_count = len(gdf)
        
        if gdf.crs and gdf.crs.is_geographic:
            projected_crs = gdf.estimate_utm_crs()
            gdf_projected = gdf.to_crs(projected_crs)
        else:
            gdf_projected = gdf

        measurements = []
        
        for index, row in gdf_projected.iterrows():
            geom = row.geometry
            if not geom or geom.is_empty:
                continue
                
            geom_type = geom.geom_type
            area, length = None, None
            
            if geom_type in ['Polygon', 'MultiPolygon']:
                area = geom.area
            elif geom_type in ['LineString', 'MultiLineString']:
                length = geom.length
                
            props = {col: str(val) for col, val in row.items() if col != 'geometry'}
            
            measurements.append(
                FeatureMeasurement(
                    geo_file_id=geo_file.id,
                    feature_index=index,
                    geometry_type=geom_type,
                    properties=props,
                    area_sqm=area,
                    length_m=length
                )
            )
            
        db.add_all(measurements)
        geo_file.status = "COMPLETED"
        
    except Exception as e:
        geo_file.status = "FAILED"
        geo_file.error_message = str(e)
    finally:
        db.commit()
        if os.path.exists(file_path):
            os.remove(file_path)