def test_health_route_reports_application_status(test_client) -> None:
    response = test_client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ready_route_reports_loaded_processed_manifest(test_client) -> None:
    response = test_client.get("/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["dataset_version"] == "test-dataset-2026-04-02"
