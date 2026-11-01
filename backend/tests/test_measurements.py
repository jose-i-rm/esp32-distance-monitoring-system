def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"


def test_create_measurement_requires_api_key(client):
    response = client.post("/api/v1/measurements", json={"timestamp": "2026-11-01T16:08:55Z", "distance_cm": 214.05})
    assert response.status_code == 401


def test_create_measurement_rejects_wrong_api_key(client):
    response = client.post(
        "/api/v1/measurements",
        json={"timestamp": "2026-11-01T16:08:55Z", "distance_cm": 214.05},
        headers={"X-API-Key": "wrong"},
    )
    assert response.status_code == 401


def test_create_and_read_measurements(client, auth_headers):
    first = client.post(
        "/api/v1/measurements",
        json={"timestamp": "2026-11-01T16:08:55Z", "distance_cm": 214.05},
        headers=auth_headers,
    )
    assert first.status_code == 201
    assert first.json()["distance_cm"] == 214.05
    assert first.json()["id"] > 0

    second = client.post(
        "/api/v1/measurements",
        json={"timestamp": "2026-11-01T11:09:25-05:00", "distance_cm": 4.92},
        headers=auth_headers,
    )
    assert second.status_code == 201

    listing = client.get("/api/v1/measurements").json()
    assert listing["total"] == 2
    assert [item["distance_cm"] for item in listing["items"]] == [4.92, 214.05]

    latest = client.get("/api/v1/measurements/latest")
    assert latest.status_code == 200
    assert latest.json()["distance_cm"] == 4.92
    assert latest.json()["timestamp"] == "2026-11-01T16:09:25Z"


def test_latest_returns_404_when_empty(client):
    assert client.get("/api/v1/measurements/latest").status_code == 404


def test_validation_rejects_negative_distance(client, auth_headers):
    response = client.post(
        "/api/v1/measurements",
        json={"timestamp": "2026-11-01T16:08:55Z", "distance_cm": -1},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_pagination_and_date_filter(client, auth_headers):
    for minute in range(5):
        client.post(
            "/api/v1/measurements",
            json={"timestamp": f"2026-11-01T16:0{minute}:00Z", "distance_cm": 10 + minute},
            headers=auth_headers,
        )

    page = client.get("/api/v1/measurements", params={"limit": 2, "offset": 1}).json()
    assert page["total"] == 5
    assert [item["distance_cm"] for item in page["items"]] == [13, 12]

    filtered = client.get(
        "/api/v1/measurements",
        params={"start": "2026-11-01T16:03:00Z"},
    ).json()
    assert filtered["total"] == 2
