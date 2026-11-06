import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pipeline as pl  # noqa: E402

T0 = 1793551493  # 2026-11-01 13:44:53 -05:00


def raw(values, step=30, start=T0, skip=()):
    data, t = {}, start
    for i, v in enumerate(values):
        if i not in skip:
            data[str(t)] = {"epoch": t, "ts": "x", "distance_cm": v, "received_at": (t + 1.5) * 1000,
                            "device": "esp32-cam-01"}
        t += step
    return data


def run(values, **kw):
    pre = pl.preprocess(pl.to_frame(raw(values, **kw)))
    filt = pl.filter_data(pre)
    return pre, filt, pl.transform(filt)


def test_preprocess_sorts_deduplicates_and_flags_range():
    data = raw([214.0, 1.0, 500.0])
    data["dup"] = dict(data[str(T0)])
    pre = pl.preprocess(pl.to_frame(data))
    assert list(pre["epoch"]) == sorted(pre["epoch"])
    assert len(pre) == 3
    assert list(pre["in_range"]) == [True, False, False]
    assert pre["latency_s"].eq(1.5).all()


def test_gaps_and_sessions():
    pre = pl.preprocess(pl.to_frame(raw([214.0] * 6, skip=(2, 3))))
    assert pre["gap"].sum() == 1
    assert pre["missing_samples"].sum() == 2
    split = {**raw([214.0] * 3), **raw([214.0] * 3, start=T0 + 3600)}
    assert pl.preprocess(pl.to_frame(split))["session"].nunique() == 2


def test_hampel_removes_isolated_spike_but_not_noise_or_steps():
    noisy = [214.0, 214.3, 213.8, 214.1, 4.5, 214.2, 213.9, 214.0]
    _, filt, _ = run(noisy)
    assert filt["outlier"].sum() == 1
    assert filt.loc[filt["distance_cm"] == 4.5, "distance_filtered"].iloc[0] > 200

    step = [214.0] * 5 + [4.5] * 5
    _, filt, _ = run(step)
    assert not filt["outlier"].any()


def test_change_events_states_and_episodes():
    values = [214.0] * 4 + [4.5] * 4 + [214.2] * 4
    _, _, res = run(values)
    ev = res["events"]
    assert list(ev["type"]) == ["acercamiento", "alejamiento"]
    assert list(ev["delta_cm"]) == [-209.5, 209.7]
    assert list(res["episodes"]["state"]) == ["libre", "objeto cercano", "libre"]
    assert list(res["episodes"]["duration_min"]) == [2.0, 2.0, 2.0]


def test_small_variations_do_not_trigger_events():
    _, _, res = run([214.0, 214.5, 205.0, 213.9])
    assert res["events"].empty


def test_compare_alerts_matches_device_epochs():
    values = [214.0] * 3 + [4.5] * 3
    _, _, res = run(values)
    epoch = int(res["events"]["epoch"].iloc[0])
    device = pd.DataFrame([{"epoch": epoch}])
    cmp_ = pl.compare_alerts(res["events"], device)
    assert cmp_ == {"alertas_borde": 1, "coinciden": 1, "solo_borde": 0, "solo_pipeline": 0, "desde_epoch": epoch}


def test_run_exports_files(tmp_path):
    out = pl.run(raw([214.0] * 4 + [4.5] * 4), {}, tmp_path, figures=False)
    assert out["quality"]["completitud_pct"] == 100.0
    for name in ("lecturas_procesadas.csv", "datos_procesados.xlsx", "resumen.json"):
        assert (tmp_path / name).exists()
