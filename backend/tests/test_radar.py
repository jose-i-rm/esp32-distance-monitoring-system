import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.integrations.radar import RadarWatcher, nearest_preset, parse_preset_angles
from app.integrations.tuya.camera import PtzRateLimited, SnapshotUnavailable
from app.models import RadarCapture

ADMIN = {"X-API-Key": "admin-test-key"}


class FakeCamera:
    def __init__(self, frame: bytes | None = b"\xff\xd8jpeg", rate_limited_once: bool = False) -> None:
        self.presets: list[int] = []
        self.frame = frame
        self.rate_limited_once = rate_limited_once

    def ptz(self, *, preset=None, **_):
        if self.rate_limited_once:
            self.rate_limited_once = False
            raise PtzRateLimited(0.5)
        self.presets.append(preset)
        return {"action": "preset", "preset": preset}

    def live_frame(self) -> bytes:
        if self.frame is None:
            raise SnapshotUnavailable("live_stream: ffmpeg no está instalado")
        return self.frame


class FakeFirebase:
    def __init__(self) -> None:
        self.alert = None

    def __call__(self, request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/stats/last_alert.json"
        return httpx.Response(200, json=self.alert)


def _alert(epoch, angle=60, kind="acercamiento", distance=80.0):
    return {"epoch": epoch, "angle_deg": angle, "type": kind, "distance_cm": distance, "previous_cm": 300.0}


@pytest.fixture()
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture()
def firebase():
    return FakeFirebase()


def _watcher(camera, firebase, presets="1:0,2:90,3:180", **kwargs):
    clock = kwargs.pop("clock", lambda: 1000.0)
    sleeps: list[float] = []
    watcher = RadarWatcher(
        camera,
        "https://db.example.com/",
        parse_preset_angles(presets),
        http=httpx.Client(transport=httpx.MockTransport(firebase)),
        sleep=sleeps.append,
        clock=clock,
        **kwargs,
    )
    return watcher, sleeps


def test_parse_and_nearest_preset():
    presets = parse_preset_angles("1:0, 2:90 ,3:180, x:1, 9:45, 4:200")
    assert presets == {1: 0, 2: 90, 3: 180}
    assert nearest_preset(30, presets) == 1
    assert nearest_preset(120, presets) == 2
    assert nearest_preset(45, presets) == 1  # empate: el preset de menor número
    assert nearest_preset(90, {}) is None


def test_existing_alert_on_startup_is_ignored_then_new_approach_moves_and_captures(db, firebase):
    camera = FakeCamera()
    watcher, sleeps = _watcher(camera, firebase, settle_seconds=4)
    firebase.alert = _alert(1794878000, angle=150)
    assert watcher.check_once(db) is None
    assert camera.presets == []

    firebase.alert = _alert(1794878100, angle=150)
    capture = watcher.check_once(db)
    assert camera.presets == [3]
    assert sleeps == [4]
    assert capture.status == "ok" and capture.image == b"\xff\xd8jpeg" and capture.preset == 3
    assert watcher.check_once(db) is None  # misma alerta: no se repite


def test_ignores_departures_and_alerts_without_angle(db, firebase):
    camera = FakeCamera()
    watcher, _ = _watcher(camera, firebase)
    firebase.alert = _alert(1)
    watcher.check_once(db)
    firebase.alert = _alert(2, kind="alejamiento")
    assert watcher.check_once(db) is None
    firebase.alert = {**_alert(3), "angle_deg": None}
    assert watcher.check_once(db) is None
    assert camera.presets == []


def test_cooldown_between_captures(db, firebase):
    now = [1000.0]
    camera = FakeCamera()
    watcher, _ = _watcher(camera, firebase, cooldown_seconds=30, clock=lambda: now[0])
    firebase.alert = _alert(1)
    watcher.check_once(db)
    firebase.alert = _alert(2)
    assert watcher.check_once(db) is not None
    now[0] += 10
    firebase.alert = _alert(3)
    assert watcher.check_once(db) is None
    now[0] += 30
    firebase.alert = _alert(4)
    assert watcher.check_once(db) is not None
    assert len(camera.presets) == 2


def test_rate_limited_ptz_is_retried_and_photo_errors_are_recorded(db, firebase):
    camera = FakeCamera(frame=None, rate_limited_once=True)
    watcher, sleeps = _watcher(camera, firebase, settle_seconds=2)
    firebase.alert = _alert(1)
    watcher.check_once(db)
    firebase.alert = _alert(2, angle=10)
    capture = watcher.check_once(db)
    assert camera.presets == [1]
    assert sleeps == [0.5, 2]
    assert capture.status == "error" and capture.image is None
    assert "ffmpeg" in capture.detail


def test_without_presets_takes_photo_in_place(db, firebase):
    camera = FakeCamera()
    watcher, _ = _watcher(camera, firebase, presets="")
    firebase.alert = _alert(1)
    watcher.check_once(db)
    firebase.alert = _alert(2)
    capture = watcher.check_once(db)
    assert camera.presets == [] and capture.preset is None
    assert capture.status == "ok" and "sin presets" in capture.detail


def test_old_captures_are_pruned(db, firebase):
    now = [0.0]
    watcher, _ = _watcher(FakeCamera(), firebase, cooldown_seconds=0, max_captures=2, clock=lambda: now[0])
    firebase.alert = _alert(1)
    watcher.check_once(db)
    for epoch in (2, 3, 4):
        firebase.alert = _alert(epoch)
        watcher.check_once(db)
    assert sorted(db.scalars(select(RadarCapture.alert_epoch)).all()) == [3, 4]


def test_capture_endpoints_require_key_and_serve_images(client):
    from app.database import get_db
    from app.main import app

    session = next(app.dependency_overrides[get_db]())
    session.add(RadarCapture(alert_epoch=10, angle_deg=45, distance_cm=80, status="ok", image=b"\xff\xd8img"))
    session.add(RadarCapture(alert_epoch=11, angle_deg=90, distance_cm=60, status="error", detail="foto: x"))
    session.commit()

    assert client.get("/api/camera/captures").status_code == 401
    items = client.get("/api/camera/captures", headers=ADMIN).json()["items"]
    assert [(i["alert_epoch"], i["has_image"]) for i in items] == [(11, False), (10, True)]
    image = client.get(f"/api/camera/captures/{items[1]['id']}/image", headers=ADMIN)
    assert image.status_code == 200 and image.content == b"\xff\xd8img"
    assert client.get(f"/api/camera/captures/{items[0]['id']}/image", headers=ADMIN).status_code == 404
