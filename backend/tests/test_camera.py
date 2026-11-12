import base64
import json
import time

import httpx
import pytest

from app.integrations.tuya.camera import CameraService, decrypt_alarm_image, parse_log_entry
from app.integrations.tuya.client import (
    TuyaClient,
    TuyaError,
    TuyaPermissionError,
    build_string_to_sign,
    sign_request,
)
from app.routers.camera import camera_service
from app.main import app

DEVICE = "dev123"
ADMIN = {"X-API-Key": "admin-test-key"}


def _alarm(cmd: str, ts: int) -> str:
    payload = {
        "v": "5.0",
        "cmd": cmd,
        "type": "image",
        "with": "resources",
        "files": [["bucket-pic", f"/abc/detect/{ts}.jpeg", "0123456789abcdef", str(ts + 3600)]],
    }
    return base64.b64encode(json.dumps(payload).encode()).decode()


NOW_MS = int(time.time() * 1000)
LOGS = [
    {"code": "alarm_message", "event_id": 7, "event_time": NOW_MS - 1000, "event_from": "1",
     "value": _alarm("ipc_human", NOW_MS // 1000)},
    {"code": "alarm_message", "event_id": 7, "event_time": NOW_MS - 5000, "event_from": "1",
     "value": _alarm("ipc_bang", NOW_MS // 1000)},
    {"event_id": 1, "event_time": NOW_MS - 60000, "event_from": "1", "status": "1"},
    {"code": "motion_switch", "event_id": 7, "event_time": NOW_MS - 70000, "event_from": "1", "value": "true"},
]


class FakeTuya:
    """Servidor Tuya simulado que valida las cabeceras de firma."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.commands: list[dict] = []
        self.token_requests = 0
        self.expire_next = False

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        self.calls.append((request.method, path))
        for header in ("client_id", "sign", "t", "nonce", "sign_method"):
            assert header in request.headers
        if path == "/v1.0/token":
            self.token_requests += 1
            return self._ok({"access_token": f"tok{self.token_requests}", "refresh_token": "ref",
                             "expire_time": 7200, "uid": "uid1"})
        assert request.headers.get("access_token")
        if self.expire_next:
            self.expire_next = False
            return httpx.Response(200, json={"success": False, "code": 1010, "msg": "token invalid"})
        if path == f"/v1.0/devices/{DEVICE}":
            return self._ok({"name": "Security Camera", "category": "sp", "online": True,
                             "product_name": "Security Camera", "time_zone": "-05:00", "update_time": 1794420000})
        if path == f"/v1.0/devices/{DEVICE}/status":
            return self._ok([{"code": "motion_switch", "value": True}, {"code": "alarm_message", "value": "secret"}])
        if path == f"/v1.0/devices/{DEVICE}/logs":
            return self._ok({"logs": LOGS, "has_next": False, "device_id": DEVICE})
        if path == f"/v1.0/devices/{DEVICE}/commands":
            self.commands.append(json.loads(request.content))
            return self._ok(True)
        if path.endswith("/stream/actions/allocate") or path.endswith("/movement-configs"):
            return httpx.Response(200, json={"success": False, "code": 28841105,
                                             "msg": "No permissions. This project is not authorized to call this API."})
        return httpx.Response(200, json={"success": False, "code": 1108, "msg": "uri path invalid"})

    @staticmethod
    def _ok(result):
        return httpx.Response(200, json={"success": True, "result": result, "t": NOW_MS})


@pytest.fixture()
def fake_tuya():
    return FakeTuya()


@pytest.fixture()
def tuya_client(fake_tuya):
    client = TuyaClient("id", "secret", "https://openapi.example.com", transport=httpx.MockTransport(fake_tuya))
    yield client
    client.close()


@pytest.fixture()
def service(tuya_client, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: None)  # sin ffmpeg en las pruebas
    svc = CameraService(tuya_client, DEVICE, ptz_min_interval_seconds=0.0)
    app.dependency_overrides[camera_service] = lambda: svc
    yield svc
    app.dependency_overrides.pop(camera_service, None)


# ------------------------------------------------------------------ cliente
def test_string_to_sign_sorts_query_and_hashes_empty_body():
    sts = build_string_to_sign("get", "/v1.0/token", {"grant_type": 1, "a": "x", "skip": None}, b"")
    assert sts == (
        "GET\ne3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855\n\n/v1.0/token?a=x&grant_type=1"
    )


def test_sign_is_uppercase_hmac_and_includes_token():
    a = sign_request(access_id="id", access_secret="s", timestamp_ms="1", nonce="n", string_to_sign="x")
    b = sign_request(access_id="id", access_secret="s", timestamp_ms="1", nonce="n", string_to_sign="x", access_token="t")
    assert a.isupper() and len(a) == 64 and a != b


def test_client_rejects_insecure_endpoint_and_hides_secret():
    with pytest.raises(ValueError):
        TuyaClient("id", "secret", "http://openapi.tuyaus.com")
    client = TuyaClient("abcdef", "supersecret", "https://x")
    assert "supersecret" not in repr(client)
    client.close()


def test_token_is_cached_and_renewed_on_expiry(tuya_client, fake_tuya):
    tuya_client.get_device(DEVICE)
    tuya_client.get_device_status(DEVICE)
    assert fake_tuya.token_requests == 1
    fake_tuya.expire_next = True
    tuya_client.get_device(DEVICE)
    assert fake_tuya.token_requests == 2


def test_permission_error_is_typed(tuya_client):
    with pytest.raises(TuyaPermissionError) as exc:
        tuya_client.allocate_stream(DEVICE, "hls")
    assert exc.value.code == 28841105
    with pytest.raises(TuyaError):
        tuya_client.request("GET", "/v1.0/nope")


# -------------------------------------------------------------- normalización
def test_parse_alarm_logs():
    human = parse_log_entry(DEVICE, LOGS[0])
    assert human["event_type"] == "humanoid_detection"
    assert human["tuya_cmd"] == "ipc_human"
    assert human["image_bucket"] == "bucket-pic" and human["image_key"] == "0123456789abcdef"
    assert "files" not in human["raw"]["payload"]
    assert parse_log_entry(DEVICE, LOGS[1])["event_type"] == "abnormal_sound"
    assert parse_log_entry(DEVICE, LOGS[2])["event_type"] == "online"
    assert parse_log_entry(DEVICE, LOGS[3])["event_type"] == "dp_report"
    plain = parse_log_entry(DEVICE, {"code": "alarm_message", "event_id": 7, "event_time": NOW_MS, "value": "disalarm"})
    assert plain["event_type"] == "disalarm"


def test_decrypt_alarm_image_roundtrip():
    from cryptography.hazmat.primitives import padding
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    key, iv, jpeg = "0123456789abcdef", bytes(range(16)), b"\xff\xd8\xff\xe0fake-jpeg"
    padder = padding.PKCS7(128).padder()
    encryptor = Cipher(algorithms.AES(key.encode()), modes.CBC(iv)).encryptor()
    ciphertext = encryptor.update(padder.update(jpeg) + padder.finalize()) + encryptor.finalize()
    blob = b"\x00\x00\x00\x01" + iv + b"\x00" * 44 + ciphertext
    assert decrypt_alarm_image(blob, key) == jpeg
    assert decrypt_alarm_image(jpeg, key) == jpeg


# ------------------------------------------------------------------ endpoints
def test_camera_endpoints_require_admin_key(client, service):
    assert client.get("/api/camera/events").status_code == 401
    assert client.get("/api/camera/events", headers={"X-API-Key": "test-key"}).status_code == 401


def test_camera_endpoints_fail_closed_without_admin_key(client, service, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "admin_api_key", "")
    assert client.get("/api/camera/events", headers=ADMIN).status_code == 503


def test_camera_not_configured_returns_503(client):
    response = client.get("/api/camera/status", headers=ADMIN)
    assert response.status_code == 503
    assert "TUYA" in response.json()["detail"]


def test_status_hides_alarm_payload(client, service):
    body = client.get("/api/camera/status", headers=ADMIN).json()
    assert body["online"] is True
    assert body["status"]["alarm_message"] == "<omitido>"
    assert body["status"]["motion_switch"] is True


def test_sync_events_is_idempotent_and_listing(client, service):
    first = client.post("/api/camera/events/sync", headers=ADMIN).json()
    assert first == {"fetched": 4, "inserted": 4}
    second = client.post("/api/camera/events/sync", headers=ADMIN).json()
    assert second["inserted"] == 0

    listing = client.get("/api/camera/events", headers=ADMIN).json()
    assert listing["total"] == 4
    assert listing["items"][0]["event_type"] == "humanoid_detection"
    assert listing["items"][0]["has_image"] is True
    assert "image_key" not in listing["items"][0]
    assert "0123456789abcdef" not in json.dumps(listing)

    filtered = client.get("/api/camera/events", params={"event_type": "abnormal_sound"}, headers=ADMIN).json()
    assert filtered["total"] == 1

    latest = client.get("/api/camera/latest", headers=ADMIN).json()
    assert latest["event_type"] == "humanoid_detection"
    assert client.get("/api/camera/latest", params={"event_type": "online"}, headers=ADMIN).json()["code"] == "online"


def test_latest_404_when_empty(client, service):
    assert client.get("/api/camera/latest", headers=ADMIN).status_code == 404


def test_ptz_move_sends_control_then_stop(client, service, fake_tuya):
    response = client.post("/api/camera/ptz", json={"direction": "right", "duration_ms": 10}, headers=ADMIN)
    assert response.status_code == 200
    assert fake_tuya.commands == [
        {"commands": [{"code": "ptz_control", "value": "2"}]},
        {"commands": [{"code": "ptz_stop", "value": True}]},
    ]
    preset = client.post("/api/camera/ptz", json={"preset": 2}, headers=ADMIN)
    assert preset.json() == {"action": "preset", "preset": 2, "direction": None, "duration_ms": None}


def test_ptz_validation_and_rate_limit(client, service):
    assert client.post("/api/camera/ptz", json={"direction": "sideways"}, headers=ADMIN).status_code == 422
    assert client.post("/api/camera/ptz", json={}, headers=ADMIN).status_code == 422
    assert client.post("/api/camera/ptz", json={"direction": "up", "duration_ms": 9999}, headers=ADMIN).status_code == 422
    service.ptz_min_interval_seconds = 60
    assert client.post("/api/camera/ptz", json={"direction": "stop"}, headers=ADMIN).status_code == 200
    limited = client.post("/api/camera/ptz", json={"direction": "stop"}, headers=ADMIN)
    assert limited.status_code == 429
    assert "Retry-After" in limited.headers


def test_ptz_first_command_not_limited_right_after_boot(client, service, monkeypatch):
    # Reproduce un servidor recién arrancado: monotonic() menor que el intervalo mínimo.
    monkeypatch.setattr("app.integrations.tuya.camera.time.monotonic", lambda: 5.0)
    service.ptz_min_interval_seconds = 60
    assert client.post("/api/camera/ptz", json={"direction": "stop"}, headers=ADMIN).status_code == 200
    assert client.post("/api/camera/ptz", json={"direction": "stop"}, headers=ADMIN).status_code == 429


def test_stream_and_snapshot_report_missing_permissions(client, service):
    stream = client.get("/api/camera/stream", params={"type": "hls"}, headers=ADMIN)
    assert stream.status_code == 503
    assert "28841105" in stream.json()["detail"]
    assert client.get("/api/camera/stream", params={"type": "x"}, headers=ADMIN).status_code == 422

    client.post("/api/camera/events/sync", headers=ADMIN)
    snapshot = client.get("/api/camera/snapshot", headers=ADMIN)
    assert snapshot.status_code == 503
    assert "alarm_image" in snapshot.json()["detail"]


def test_security_headers(client):
    response = client.get("/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
