import os
import shutil

from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.database import Base, engine, get_db
from app.models import FeatureMeasurement, GeoFile
from app.worker import process_geospatial_file


Base.metadata.create_all(bind=engine)
os.makedirs("uploads", exist_ok=True)

app = FastAPI(
    title="Geospatial File Measurement API",
    version="1.0.0",
    description=(
        "Upload KML or zipped Shapefiles and calculate "
        "geospatial measurements with CRS-aware processing."
    ),
)

MAX_UPLOAD_SIZE = 50 * 1024 * 1024
ALLOWED_EXTENSIONS = {".zip", ".kml"}


class FileInfoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str
    feature_count: int
    crs: str | None
    status: str
    error_message: str | None = None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post(
    "/api/files/",
    response_model=FileInfoResponse,
    status_code=202,
)
def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    filename = os.path.basename(file.filename or "")
    extension = os.path.splitext(filename)[1].lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Only .zip (Shapefile) or .kml files are allowed.",
        )

    geo_file = GeoFile(filename=filename)
    db.add(geo_file)
    db.commit()
    db.refresh(geo_file)

    file_path = os.path.join(
        "uploads",
        f"{geo_file.id}_{filename}",
    )

    total_size = 0

    try:
        with open(file_path, "wb") as buffer:
            while True:
                chunk = file.file.read(1024 * 1024)

                if not chunk:
                    break

                total_size += len(chunk)

                if total_size > MAX_UPLOAD_SIZE:
                    raise HTTPException(
                        status_code=413,
                        detail="File exceeds the 50 MB upload limit.",
                    )

                buffer.write(chunk)

    except Exception:
        if os.path.exists(file_path):
            os.remove(file_path)

        db.delete(geo_file)
        db.commit()
        raise

    finally:
        file.file.close()

    background_tasks.add_task(
        process_geospatial_file,
        geo_file.id,
        file_path,
    )

    return geo_file


@app.get(
    "/api/files/{file_id}/",
    response_model=FileInfoResponse,
)
def get_file_info(
    file_id: str,
    db: Session = Depends(get_db),
):
    geo_file = (
        db.query(GeoFile)
        .filter(GeoFile.id == file_id)
        .first()
    )

    if not geo_file:
        raise HTTPException(
            status_code=404,
            detail="File not found.",
        )

    return geo_file


@app.get("/api/files/{file_id}/measurements/")
def get_measurements(
    file_id: str,
    db: Session = Depends(get_db),
):
    geo_file = (
        db.query(GeoFile)
        .filter(GeoFile.id == file_id)
        .first()
    )

    if not geo_file:
        raise HTTPException(
            status_code=404,
            detail="File not found.",
        )

    measurements = (
        db.query(FeatureMeasurement)
        .filter(FeatureMeasurement.geo_file_id == file_id)
        .order_by(FeatureMeasurement.feature_index)
        .all()
    )

    return {
        "file_id": file_id,
        "filename": geo_file.filename,
        "status": geo_file.status,
        "crs": geo_file.crs,
        "feature_count": geo_file.feature_count,
        "error_message": geo_file.error_message,
        "features": [
            {
                "feature_index": measurement.feature_index,
                "geometry_type": measurement.geometry_type,
                "geometry": measurement.geometry,
                "properties": measurement.properties,
                "measurement_status": measurement.measurement_status,
                "error_message": measurement.error_message,
                "measurements": {
                    "area_sqm": measurement.area_sqm,
                    "length_m": measurement.length_m,
                },
            }
            for measurement in measurements
        ],
    }
