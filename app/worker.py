import json
import math
import os
import tempfile
import zipfile

import geopandas as gpd
from shapely.geometry import mapping
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import FeatureMeasurement, GeoFile


def make_json_safe(value):
    if value is None:
        return None

    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return value

    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return str(value)


def safe_extract_zip(zip_path: str, extract_dir: str) -> str:
    with zipfile.ZipFile(zip_path, "r") as archive:
        members = archive.namelist()

        for member in members:
            target_path = os.path.abspath(
                os.path.join(extract_dir, member)
            )

            if not target_path.startswith(
                os.path.abspath(extract_dir) + os.sep
            ):
                raise ValueError(
                    "Unsafe ZIP file: path traversal detected."
                )

        archive.extractall(extract_dir)

    shapefiles = []

    for root, _, files in os.walk(extract_dir):
        for name in files:
            if name.lower().endswith(".shp"):
                shapefiles.append(os.path.join(root, name))

    if not shapefiles:
        raise ValueError(
            "ZIP file does not contain a Shapefile (.shp)."
        )

    if len(shapefiles) > 1:
        raise ValueError(
            "ZIP file contains multiple Shapefiles. "
            "Please upload one Shapefile per ZIP."
        )

    return shapefiles[0]


def read_geospatial_file(file_path: str) -> gpd.GeoDataFrame:
    extension = os.path.splitext(file_path)[1].lower()

    if extension == ".zip":
        with tempfile.TemporaryDirectory() as extract_dir:
            shapefile_path = safe_extract_zip(
                file_path,
                extract_dir,
            )
            return gpd.read_file(shapefile_path)

    if extension == ".kml":
        return gpd.read_file(
            file_path,
            driver="KML",
        )

    raise ValueError("Unsupported file format.")


def process_geospatial_file(file_id: str, file_path: str):
    db: Session = SessionLocal()

    try:
        geo_file = (
            db.query(GeoFile)
            .filter(GeoFile.id == file_id)
            .first()
        )

        if not geo_file:
            return

        geo_file.status = "PROCESSING"
        db.commit()

        gdf = read_geospatial_file(file_path)

        geo_file.feature_count = len(gdf)
        geo_file.crs = str(gdf.crs) if gdf.crs else None

        projected_gdf = gdf

        if gdf.crs and gdf.crs.is_geographic:
            projected_crs = gdf.estimate_utm_crs()

            if projected_crs is None:
                raise ValueError(
                    "Could not determine a suitable projected CRS."
                )

            projected_gdf = gdf.to_crs(projected_crs)

        measurements = []

        for feature_position, (_, row) in enumerate(
            gdf.iterrows()
        ):
            original_geometry = row.geometry

            projected_geometry = projected_gdf.iloc[
                feature_position
            ].geometry

            properties = {
                str(column): make_json_safe(value)
                for column, value in row.items()
                if column != "geometry"
            }

            geometry_type = (
                original_geometry.geom_type
                if original_geometry is not None
                else "Unknown"
            )

            geometry_json = None

            if original_geometry is not None:
                try:
                    geometry_json = mapping(original_geometry)
                except Exception:
                    geometry_json = None

            measurement_status = "NOT_SUPPORTED"
            error_message = None
            area_sqm = None
            length_m = None

            try:
                if (
                    original_geometry is None
                    or original_geometry.is_empty
                ):
                    measurement_status = "EMPTY_GEOMETRY"
                    error_message = "Geometry is empty."

                elif geometry_type in (
                    "Polygon",
                    "MultiPolygon",
                ):
                    if not gdf.crs:
                        measurement_status = "NO_CRS"
                        error_message = (
                            "CRS is missing; area cannot be "
                            "calculated reliably."
                        )
                    else:
                        area_sqm = float(
                            projected_geometry.area
                        )
                        measurement_status = "MEASURED"

                elif geometry_type in (
                    "LineString",
                    "MultiLineString",
                ):
                    if not gdf.crs:
                        measurement_status = "NO_CRS"
                        error_message = (
                            "CRS is missing; length cannot be "
                            "calculated reliably."
                        )
                    else:
                        length_m = float(
                            projected_geometry.length
                        )
                        measurement_status = "MEASURED"

                elif geometry_type == "Point":
                    measurement_status = "NOT_REQUIRED"

                else:
                    measurement_status = "NOT_SUPPORTED"
                    error_message = (
                        f"Measurement is not supported for "
                        f"{geometry_type}."
                    )

            except Exception as feature_error:
                measurement_status = "ERROR"
                error_message = str(feature_error)

            measurements.append(
                FeatureMeasurement(
                    geo_file_id=geo_file.id,
                    feature_index=feature_position,
                    geometry_type=geometry_type,
                    geometry=geometry_json,
                    properties=properties,
                    measurement_status=measurement_status,
                    error_message=error_message,
                    area_sqm=area_sqm,
                    length_m=length_m,
                )
            )

        db.add_all(measurements)

        geo_file.status = "COMPLETED"

        db.commit()

    except Exception as error:
        db.rollback()

        geo_file = (
            db.query(GeoFile)
            .filter(GeoFile.id == file_id)
            .first()
        )

        if geo_file:
            geo_file.status = "FAILED"
            geo_file.error_message = str(error)
            db.commit()

    finally:
        db.close()

        if os.path.exists(file_path):
            os.remove(file_path)
