import uuid
from sqlalchemy import Column, String, Integer, Float, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.database import Base

class GeoFile(Base):
    __tablename__ = "geo_files"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String, nullable=False)
    status = Column(String, default="PENDING") 
    feature_count = Column(Integer, default=0)
    crs = Column(String, nullable=True)
    error_message = Column(String, nullable=True)
    
    measurements = relationship("FeatureMeasurement", back_populates="geo_file")

class FeatureMeasurement(Base):
    __tablename__ = "feature_measurements"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    geo_file_id = Column(String, ForeignKey("geo_files.id"))
    feature_index = Column(Integer, nullable=False)
    geometry_type = Column(String, nullable=False)
    properties = Column(JSON, nullable=True)
    area_sqm = Column(Float, nullable=True)
    length_m = Column(Float, nullable=True)
    
    geo_file = relationship("GeoFile", back_populates="measurements")