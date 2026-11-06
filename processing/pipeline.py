"""Pipeline de procesamiento de datos IoT del ESP32 Distance Monitoring System.

Etapas (ETL):
  1. Extracción: descarga /measurements y /alerts de Firebase Realtime Database (REST).
  2. Preprocesamiento: tipos, zona horaria, orden, duplicados, rango válido, huecos, sesiones y latencia.
  3. Filtrado: descarte de lecturas fuera de rango y filtro de Hampel + mediana móvil para picos aislados.
  4. Transformación: variación entre lecturas, detección de cambios (alertas), estado del objeto,
     episodios de presencia, normalización y agregación temporal.
  5. Carga: Excel multihoja, CSV, figuras PNG y resumen JSON.

Uso:
    python processing/pipeline.py                      # descarga de Firebase y procesa
    python processing/pipeline.py --input datos.json   # procesa un respaldo local
"""
from __future__ import annotations

import argparse
import json
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

DB_URL = "https://esp32-distance-jirm-450f1-default-rtdb.firebaseio.com"
TZ = "America/Bogota"


@dataclass(frozen=True)
class Config:
    interval_s: int = 30                # periodo de muestreo del firmware
    min_cm: float = 2.0                 # rango útil del HC-SR04 según su hoja de datos
    max_cm: float = 400.0
    change_threshold_cm: float = 10.0   # mismo umbral que UMBRAL_CAMBIO_CM del firmware
    near_threshold_cm: float = 100.0    # separa los dos modos de la distribución (objeto cercano / libre)
    hampel_window: int = 5              # ventana centrada (lecturas) del filtro de Hampel
    hampel_k: float = 3.0               # múltiplo de la MAD escalada para marcar un pico
    hampel_min_mad_cm: float = 1.0      # piso de la MAD: evita marcar el ruido de ±0,5 cm como pico
    gap_factor: float = 1.5             # hueco si Δt > 1,5 × intervalo
    session_gap_s: int = 600            # una pausa > 10 min inicia una nueva sesión
    resample: str = "5min"


# ----------------------------------------------------------------------------- 1. Extracción
def fetch(path: str, db_url: str = DB_URL) -> dict:
    with urllib.request.urlopen(f"{db_url}/{path}.json", timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8")) or {}


def to_frame(raw: dict) -> pd.DataFrame:
    if not raw:
        return pd.DataFrame(columns=["epoch", "ts", "distance_cm", "received_at", "device"])
    df = pd.DataFrame.from_dict(raw, orient="index")
    df.index.name = "key"
    return df.reset_index()


# ----------------------------------------------------------------------------- 2. Preprocesamiento
def preprocess(df: pd.DataFrame, cfg: Config = Config()) -> pd.DataFrame:
    out = df.copy()
    out["epoch"] = pd.to_numeric(out["epoch"], errors="coerce")
    out["distance_cm"] = pd.to_numeric(out["distance_cm"], errors="coerce")
    out = out.dropna(subset=["epoch", "distance_cm"])
    out["epoch"] = out["epoch"].astype("int64")

    out = out.sort_values("epoch").drop_duplicates(subset="epoch", keep="first").reset_index(drop=True)

    out["time"] = pd.to_datetime(out["epoch"], unit="s", utc=True).dt.tz_convert(TZ)
    if "received_at" in out:
        received = pd.to_numeric(out["received_at"], errors="coerce")
        out["received"] = pd.to_datetime(received, unit="ms", utc=True).dt.tz_convert(TZ)
        out["latency_s"] = (received / 1000 - out["epoch"]).round(3)

    out["in_range"] = out["distance_cm"].between(cfg.min_cm, cfg.max_cm)

    dt = out["epoch"].diff()
    out["dt_s"] = dt
    out["gap"] = (dt > cfg.interval_s * cfg.gap_factor) & (dt <= cfg.session_gap_s)
    out["missing_samples"] = np.where(out["gap"], (dt / cfg.interval_s).round() - 1, 0).astype(int)
    out["session"] = (dt.fillna(0) > cfg.session_gap_s).cumsum() + 1
    return out


# ----------------------------------------------------------------------------- 3. Filtrado
def hampel(series: pd.Series, window: int, k: float, min_mad: float) -> pd.Series:
    """True donde la lectura se aleja más de k·MAD de la mediana de su vecindad (pico aislado)."""
    med = series.rolling(window, center=True, min_periods=1).median()
    mad = (series - med).abs().rolling(window, center=True, min_periods=1).median() * 1.4826
    return (series - med).abs() > k * np.maximum(mad, min_mad)


def filter_data(df: pd.DataFrame, cfg: Config = Config()) -> pd.DataFrame:
    out = df[df["in_range"]].copy()
    out["outlier"] = False
    out["distance_filtered"] = out["distance_cm"]
    for _, idx in out.groupby("session").groups.items():
        s = out.loc[idx, "distance_cm"]
        flags = hampel(s, cfg.hampel_window, cfg.hampel_k, cfg.hampel_min_mad_cm)
        med = s.rolling(cfg.hampel_window, center=True, min_periods=1).median()
        out.loc[idx, "outlier"] = flags
        out.loc[idx, "distance_filtered"] = np.where(flags, med, s)
    out["outlier"] = out["outlier"].astype(bool)
    out["distance_filtered"] = out["distance_filtered"].astype(float).round(2)
    return out


# ----------------------------------------------------------------------------- 4. Transformación
def transform(df: pd.DataFrame, cfg: Config = Config()) -> dict[str, pd.DataFrame]:
    out = df.copy()
    out["delta_cm"] = out.groupby("session")["distance_cm"].diff().round(2)
    out["change_event"] = out["delta_cm"].abs() >= cfg.change_threshold_cm
    out["state"] = np.where(out["distance_filtered"] < cfg.near_threshold_cm, "objeto cercano", "libre")
    out["distance_norm"] = ((out["distance_filtered"] - cfg.min_cm) / (cfg.max_cm - cfg.min_cm)).clip(0, 1).round(4)

    events = out[out["change_event"]].copy()
    events["previous_cm"] = (events["distance_cm"] - events["delta_cm"]).round(2)
    events["type"] = np.where(events["delta_cm"] < 0, "acercamiento", "alejamiento")
    events["transient"] = events["outlier"]
    events = events[["epoch", "time", "previous_cm", "distance_cm", "delta_cm", "type", "transient", "session"]]

    # Episodios: tramos consecutivos con el mismo estado dentro de cada sesión.
    block = ((out["state"] != out["state"].shift()) | (out["session"] != out["session"].shift())).cumsum()
    episodes = (out.groupby(block)
                .agg(session=("session", "first"), state=("state", "first"), start=("time", "first"),
                     end=("time", "last"), readings=("epoch", "size"), mean_cm=("distance_filtered", "mean"))
                .reset_index(drop=True))
    episodes["duration_min"] = (episodes["readings"] * cfg.interval_s / 60).round(1)
    episodes["mean_cm"] = episodes["mean_cm"].round(2)

    agg = (out.set_index("time")
           .resample(cfg.resample)
           .agg(lecturas=("distance_cm", "size"), media_cm=("distance_filtered", "mean"),
                minimo_cm=("distance_filtered", "min"), maximo_cm=("distance_filtered", "max"),
                cambios=("change_event", "sum"),
                ocupacion_pct=("state", lambda s: 100 * (s == "objeto cercano").mean() if len(s) else np.nan)))
    agg = agg[agg["lecturas"] > 0].round(2).reset_index()

    return {"readings": out, "events": events, "episodes": episodes, "aggregated": agg}


def compare_alerts(events: pd.DataFrame, device_alerts: pd.DataFrame) -> dict:
    """Contrasta las alertas generadas en el borde (firmware) con las recalculadas en el pipeline."""
    if device_alerts.empty:
        return {"alertas_borde": 0, "coinciden": 0, "solo_borde": 0, "solo_pipeline": 0, "desde_epoch": None}
    start = int(pd.to_numeric(device_alerts["epoch"]).min())
    dev = set(pd.to_numeric(device_alerts["epoch"]).astype(int))
    pipe = set(events.loc[events["epoch"] >= start, "epoch"].astype(int))
    return {"alertas_borde": len(dev), "coinciden": len(dev & pipe), "solo_borde": len(dev - pipe),
            "solo_pipeline": len(pipe - dev), "desde_epoch": start}


# ----------------------------------------------------------------------------- Calidad
def quality(pre: pd.DataFrame, filt: pd.DataFrame, cfg: Config = Config()) -> dict:
    sessions = pre.groupby("session")["epoch"].agg(["min", "max", "size"])
    expected = int((((sessions["max"] - sessions["min"]) / cfg.interval_s).round() + 1).sum())
    lat = pre["latency_s"].dropna() if "latency_s" in pre else pd.Series(dtype=float)
    return {
        "lecturas_recibidas": int(len(pre)),
        "sesiones": int(pre["session"].nunique()),
        "lecturas_esperadas": expected,
        "completitud_pct": round(100 * len(pre) / expected, 2) if expected else None,
        "huecos": int(pre["gap"].sum()),
        "lecturas_perdidas": int(pre["missing_samples"].sum()),
        "fuera_de_rango": int((~pre["in_range"]).sum()),
        "picos_hampel": int(filt["outlier"].sum()),
        "latencia_mediana_s": round(float(lat.median()), 2) if len(lat) else None,
        "latencia_p95_s": round(float(lat.quantile(0.95)), 2) if len(lat) else None,
        "latencia_max_s": round(float(lat.max()), 2) if len(lat) else None,
        "desde": pre["time"].min().isoformat() if len(pre) else None,
        "hasta": pre["time"].max().isoformat() if len(pre) else None,
    }


# ----------------------------------------------------------------------------- 5. Carga
def _naive(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    for col in frame.columns:
        if isinstance(frame[col].dtype, pd.DatetimeTZDtype):
            frame[col] = frame[col].dt.tz_localize(None)
    return frame


def export(results: dict, qual: dict, comparison: dict, cfg: Config, outdir: Path) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    naive = {k: _naive(v) for k, v in results.items()}

    cols = ["epoch", "time", "distance_cm", "distance_filtered", "distance_norm", "delta_cm", "change_event",
            "state", "outlier", "session", "latency_s", "dt_s", "gap"]
    readings = naive["readings"][[c for c in cols if c in naive["readings"]]]
    readings.to_csv(outdir / "lecturas_procesadas.csv", index=False, encoding="utf-8")

    summary = pd.DataFrame({"indicador": list(qual) + list(comparison),
                            "valor": [str(v) for v in list(qual.values()) + list(comparison.values())]})
    params = pd.DataFrame({"parametro": list(asdict(cfg)), "valor": [str(v) for v in asdict(cfg).values()]})
    with pd.ExcelWriter(outdir / "datos_procesados.xlsx") as xw:
        readings.to_excel(xw, sheet_name="Lecturas", index=False)
        naive["events"].to_excel(xw, sheet_name="Cambios", index=False)
        naive["episodes"].to_excel(xw, sheet_name="Episodios", index=False)
        naive["aggregated"].to_excel(xw, sheet_name=f"Agregado_{cfg.resample}", index=False)
        summary.to_excel(xw, sheet_name="Calidad", index=False)
        params.to_excel(xw, sheet_name="Parametros", index=False)

    (outdir / "resumen.json").write_text(
        json.dumps({"calidad": qual, "alertas_borde_vs_pipeline": comparison, "parametros": asdict(cfg),
                    "cambios_detectados": int(len(results["events"])),
                    "cambios_transitorios": int(results["events"]["transient"].sum()),
                    "episodios": int(len(results["episodes"]))}, ensure_ascii=False, indent=2),
        encoding="utf-8")


def plot(results: dict, cfg: Config, outdir: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    r = results["readings"]
    ev = results["events"]
    tz = r["time"].dt.tz
    fmt = mdates.DateFormatter("%H:%M", tz=tz)
    plt.rcParams.update({"font.size": 9})

    sessions = sorted(r["session"].unique())
    fig, axes = plt.subplots(len(sessions), 1, figsize=(7.2, 2.3 * len(sessions)), squeeze=False)
    for ax, ses in zip(axes[:, 0], sessions):
        rs = r[r["session"] == ses]
        es = ev[ev["session"] == ses]
        ax.plot(rs["time"], rs["distance_cm"], color="#9aa5b1", lw=0.8, label="Cruda")
        ax.plot(rs["time"], rs["distance_filtered"], color="#1f5fa8", lw=1.3, label="Filtrada (Hampel)")
        ax.scatter(es["time"], es["distance_cm"], color="#d62728", s=22, zorder=3,
                   label=f"Cambio ≥ {cfg.change_threshold_cm:.0f} cm")
        ax.axhline(cfg.near_threshold_cm, color="#f28e2b", ls="--", lw=0.8, label="Umbral cercano/libre")
        ax.xaxis.set_major_formatter(fmt)
        ax.set_ylabel("Distancia (cm)")
        t0, t1 = rs["time"].min(), rs["time"].max()
        ax.set_title(f"Sesión {ses}: {t0:%d/%m/%Y %H:%M} – {t1:%H:%M} ({len(rs)} lecturas)", fontsize=9)
        ax.grid(alpha=0.3)
    axes[0, 0].legend(loc="center right", fontsize=7, ncol=2)
    fig.tight_layout()
    fig.savefig(outdir / "fig_serie_filtrada.png", dpi=200)
    plt.close(fig)

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.2, 2.5))
    a1.hist(r["distance_cm"], bins=40, color="#1f5fa8")
    a1.axvline(cfg.near_threshold_cm, color="#f28e2b", ls="--", lw=0.8)
    a1.set_xlabel("Distancia (cm)")
    a1.set_ylabel("Lecturas")
    a1.set_title("Distribución de distancias", fontsize=9)
    lat = r["latency_s"].dropna()
    a2.hist(lat, bins=30, color="#59a14f")
    a2.set_xlabel("Latencia lectura → Firebase (s)")
    a2.set_title(f"Latencia (mediana {lat.median():.2f} s)", fontsize=9)
    fig.tight_layout()
    fig.savefig(outdir / "fig_distribucion_latencia.png", dpi=200)
    plt.close(fig)

    agg = results["aggregated"]
    fig, ax = plt.subplots(figsize=(7.2, 2.4))
    ax.bar(agg["time"], agg["ocupacion_pct"], width=pd.Timedelta(cfg.resample) * 0.8, color="#f28e2b",
           label="% del tiempo con objeto cercano")
    ax2 = ax.twinx()
    ax2.plot(agg["time"], agg["cambios"], "o-", color="#d62728", ms=3, lw=1, label="Cambios detectados")
    ax.set_ylabel("Ocupación (%)")
    ax.set_ylim(0, 140)
    ax2.set_ylabel("Cambios")
    ax2.set_ylim(0, max(1, agg["cambios"].max()) * 1.4)
    ax.xaxis.set_major_formatter(fmt)
    ax.set_title(f"Agregación cada {cfg.resample}", fontsize=9)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="upper right", fontsize=7)
    fig.tight_layout()
    fig.savefig(outdir / "fig_agregado.png", dpi=200)
    plt.close(fig)


# ----------------------------------------------------------------------------- Orquestación
def run(measurements_raw: dict, alerts_raw: dict, outdir: Path, cfg: Config = Config(), figures: bool = True) -> dict:
    pre = preprocess(to_frame(measurements_raw), cfg)
    filt = filter_data(pre, cfg)
    results = transform(filt, cfg)
    qual = quality(pre, filt, cfg)
    comparison = compare_alerts(results["events"], to_frame(alerts_raw))
    export(results, qual, comparison, cfg, outdir)
    if figures:
        plot(results, cfg, outdir)
    return {"quality": qual, "comparison": comparison, "results": results}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", type=Path, help="Respaldo JSON con las claves 'measurements' y 'alerts'")
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "output")
    parser.add_argument("--db-url", default=DB_URL)
    args = parser.parse_args()

    if args.input:
        data = json.loads(args.input.read_text(encoding="utf-8-sig"))
        measurements, alerts = data.get("measurements", data), data.get("alerts", {})
    else:
        measurements, alerts = fetch("measurements", args.db_url), fetch("alerts", args.db_url)
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "respaldo_firebase.json").write_text(
            json.dumps({"measurements": measurements, "alerts": alerts}, ensure_ascii=False), encoding="utf-8")

    summary = run(measurements, alerts, args.output)
    events = summary["results"]["events"]
    print(json.dumps({"calidad": summary["quality"], "alertas_borde_vs_pipeline": summary["comparison"],
                      "cambios_detectados": len(events), "cambios_transitorios": int(events["transient"].sum()),
                      "episodios": len(summary["results"]["episodes"])}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
