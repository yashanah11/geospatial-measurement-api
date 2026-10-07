import os
import shutil
from fastapi import FastAPI, BackgroundTasks, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import engine, Base, get_db
from app.models import GeoFile, FeatureMeasurement
from app.worker import process_geospatial_file
from pydantic import BaseModel

Base.metadata.create_all(bind=engine)
os.makedirs("uploads", exist_ok=True)

app = FastAPI(title="Geospatial File Measurement API")

class FileInfoResponse(BaseModel):
    id: str
    filename: str
    feature_count: int
    crs: str | None
    status: str
    
    class Config:
        from_attributes = True

@app.post("/api/files/", response_model=FileInfoResponse, status_code=202)
def upload_file(
    background_tasks: BackgroundTasks, 
    file: UploadFile = File(...), 
    db: Session = Depends(get_db)
):
    if not file.filename.endswith(('.zip', '.kml')):
        raise HTTPException(status_code=400, detail="Only .zip (Shapefile) or .kml allowed.")

    geo_file = GeoFile(filename=file.filename)
    db.add(geo_file)
    db.commit()
    db.refresh(geo_file)

    file_path = os.path.join("uploads", f"{geo_file.id}_{file.filename}")
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    background_tasks.add_task(process_geospatial_file, geo_file.id, file_path, db)

    return geo_file

@app.get("/api/files/{file_id}/", response_model=FileInfoResponse)
def get_file_info(file_id: str, db: Session = Depends(get_db)):
    geo_file = db.query(GeoFile).filter(GeoFile.id == file_id).first()
    if not geo_file:
        raise HTTPException(status_code=404, detail="File not found")
    return geo_file

@app.get("/api/files/{file_id}/measurements/")
def get_measurements(file_id: str, db: Session = Depends(get_db)):
    geo_file = db.query(GeoFile).filter(GeoFile.id == file_id).first()
    if not geo_file:
        raise HTTPException(status_code=404, detail="File not found")
    
    if geo_file.status != "COMPLETED":
        return {"status": geo_file.status, "message": "Processing not complete"}

    measurements = db.query(FeatureMeasurement).filter(FeatureMeasurement.geo_file_id == file_id).all()
    
    return {
        "file_id": file_id,
        "crs": geo_file.crs,
        "features": [
            {
                "feature_index": m.feature_index,
                "geometry_type": m.geometry_type,
                "properties": m.properties,
                "measurements": {
                    "area_sqm": m.area_sqm,
                    "length_m": m.length_m
                }
            } for m in measurements
        ]
    }