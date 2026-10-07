from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)

TEST_KML = Path(__file__).resolve().parents[1] / "test.kml"


def test_health():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_invalid_file_type():
    response = client.post(
        "/api/files/",
        files={
            "file": (
                "invalid.txt",
                b"not a geospatial file",
                "text/plain",
            )
        },
    )

    assert response.status_code == 400
    assert "Only .zip" in response.json()["detail"]


def test_file_not_found():
    response = client.get(
        "/api/files/00000000-0000-0000-0000-000000000000/"
    )

    assert response.status_code == 404


def test_kml_upload_and_processing():
    with TEST_KML.open("rb") as file:
        response = client.post(
            "/api/files/",
            files={
                "file": (
                    "test.kml",
                    file,
                    "application/vnd.google-earth.kml+xml",
                )
            },
        )

    assert response.status_code == 202

    data = response.json()

    assert data["filename"] == "test.kml"
    assert data["id"]

    file_id = data["id"]

    status_response = client.get(
        f"/api/files/{file_id}/"
    )

    assert status_response.status_code == 200

    status_data = status_response.json()

    assert status_data["status"] == "COMPLETED"
    assert status_data["feature_count"] == 1
    assert status_data["crs"] == "EPSG:4326"


def test_measurements_response():
    with TEST_KML.open("rb") as file:
        upload_response = client.post(
            "/api/files/",
            files={
                "file": (
                    "test.kml",
                    file,
                    "application/vnd.google-earth.kml+xml",
                )
            },
        )

    assert upload_response.status_code == 202

    file_id = upload_response.json()["id"]

    response = client.get(
        f"/api/files/{file_id}/measurements/"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "COMPLETED"
    assert data["feature_count"] == 1
    assert len(data["features"]) == 1

    feature = data["features"][0]

    assert feature["feature_index"] == 0
    assert feature["geometry_type"] == "Polygon"
    assert feature["geometry"]["type"] == "Polygon"
    assert feature["measurement_status"] == "MEASURED"

    area = feature["measurements"]["area_sqm"]

    assert area is not None
    assert area > 0