\# Geospatial File Measurement API



A FastAPI-based backend that accepts KML files and ZIP archives containing Shapefiles, processes their geospatial features, and calculates CRS-aware measurements.



\## Features



\- Upload `.kml` files

\- Upload `.zip` archives containing a Shapefile

\- Background geospatial processing

\- Feature count and processing status

\- Geometry type and GeoJSON geometry

\- Feature properties/attributes

\- CRS detection

\- Polygon and MultiPolygon area calculation

\- LineString and MultiLineString length calculation

\- Point feature handling

\- Geographic CRS transformation before measurement

\- Safe ZIP extraction

\- File-size validation

\- Feature-level measurement status and errors

\- SQLite persistence through SQLAlchemy

\- Interactive Swagger API documentation



\## Tech Stack



\- Python

\- FastAPI

\- Uvicorn

\- GeoPandas

\- Shapely

\- PyProj

\- Fiona

\- SQLAlchemy

\- SQLite

\- Pytest



\## Project Structure



```text

geospatial-measurement-api/

├── app/

│   ├── \_\_init\_\_.py

│   ├── database.py

│   ├── main.py

│   ├── models.py

│   └── worker.py

├── tests/

│   └── test\_api.py

├── .gitignore

├── requirements.txt

├── test.kml

└── README.md

```



\## Setup



\### 1. Clone the repository



```bash

git clone https://github.com/yashanah11/geospatial-measurement-api.git

cd geospatial-measurement-api

```



\### 2. Create a virtual environment



Windows:



```powershell

python -m venv .venv

.venv\\Scripts\\Activate.ps1

```



Linux/macOS:



```bash

python -m venv .venv

source .venv/bin/activate

```



\### 3. Install dependencies



```bash

pip install -r requirements.txt

```



\### 4. Start the API



```bash

uvicorn app.main:app --reload

```



The API will be available at:



```text

http://127.0.0.1:8000

```



Interactive Swagger documentation:



```text

http://127.0.0.1:8000/docs

```



\## API Endpoints



\### Health Check



```http

GET /health

```



Example response:



```json

{

&#x20; "status": "ok"

}

```



\### Upload File



```http

POST /api/files/

```



Multipart form field:



```text

file

```



Supported formats:



\- `.kml`

\- `.zip` containing one Shapefile



Example:



```bash

curl -X POST http://127.0.0.1:8000/api/files/ \\

&#x20; -F "file=@test.kml"

```



The API returns HTTP `202 Accepted` and a file ID.



Example:



```json

{

&#x20; "id": "uuid",

&#x20; "filename": "test.kml",

&#x20; "feature\_count": 0,

&#x20; "crs": null,

&#x20; "status": "PENDING",

&#x20; "error\_message": null

}

```



Processing happens in the background.



\### Get File Status



```http

GET /api/files/{id}/

```



Example:



```json

{

&#x20; "id": "uuid",

&#x20; "filename": "test.kml",

&#x20; "feature\_count": 1,

&#x20; "crs": "EPSG:4326",

&#x20; "status": "COMPLETED",

&#x20; "error\_message": null

}

```



\### Get Measurements



```http

GET /api/files/{id}/measurements/

```



Example:



```json

{

&#x20; "file\_id": "uuid",

&#x20; "filename": "test.kml",

&#x20; "status": "COMPLETED",

&#x20; "crs": "EPSG:4326",

&#x20; "feature\_count": 1,

&#x20; "features": \[

&#x20;   {

&#x20;     "feature\_index": 0,

&#x20;     "geometry\_type": "Polygon",

&#x20;     "geometry": {

&#x20;       "type": "Polygon",

&#x20;       "coordinates": \[]

&#x20;     },

&#x20;     "properties": {},

&#x20;     "measurement\_status": "MEASURED",

&#x20;     "error\_message": null,

&#x20;     "measurements": {

&#x20;       "area\_sqm": 1086029.5,

&#x20;       "length\_m": null

&#x20;     }

&#x20;   }

&#x20; ]

}

```



\## Architecture



```text

Client

&#x20; |

&#x20; | POST /api/files/

&#x20; v

FastAPI

&#x20; |

&#x20; +--> Validate extension and file size

&#x20; |

&#x20; +--> Store upload temporarily

&#x20; |

&#x20; +--> Create database record

&#x20; |

&#x20; +--> Schedule background processing

&#x20;             |

&#x20;             v

&#x20;      Geospatial Worker

&#x20;             |

&#x20;             +--> Read KML / ZIP Shapefile

&#x20;             |

&#x20;             +--> Detect CRS

&#x20;             |

&#x20;             +--> Transform geographic CRS

&#x20;             |

&#x20;             +--> Calculate measurements

&#x20;             |

&#x20;             +--> Store geometry/properties/results

&#x20;             |

&#x20;             v

&#x20;          SQLite

&#x20;             |

&#x20;             v

GET /measurements/

```



\## File Processing Flow



\### KML



1\. Validate the `.kml` extension.

2\. Store the uploaded file temporarily.

3\. Read the KML using GeoPandas.

4\.

