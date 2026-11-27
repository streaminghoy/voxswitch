"""Medición de nivel por canal para detección de voz.

Todo trabaja por bloques (por defecto 10 ms a 48 kHz) y por canal, sin
dependencias de UI ni de video. Pensado para correr dentro del callback
de audio o en el hilo de audio: sin I/O, sin locks, sin alocaciones
grandes por bloque.

Cadena por canal:
    bloque PCM -> filtro banda de voz -> RMS -> envolvente (ataque/release)
    -> dBFS -> piso de ruido (percentil) -> umbral -> activo sí/no
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.signal import butter, sosfilt

DB_MIN = -100.0  # piso numérico para evitar log(0)


def to_dbfs(rms: np.ndarray | float) -> np.ndarray:
    """RMS lineal (full scale = 1.0) a dBFS, recortado en DB_MIN."""
    rms = np.maximum(np.asarray(rms, dtype=np.float64), 10 ** (DB_MIN / 20))
    return 20.0 * np.log10(rms)


class VoiceBandFilter:
    """Pasabanda Butterworth 300 Hz - 3,4 kHz con estado por canal.

    Deja afuera golpes de mesa, ruido de aire y graves que inflan el RMS
    sin ser voz. El estado se conserva entre bloques (sin clicks).
    """

    def __init__(self, samplerate: int, channels: int,
                 low_hz: float = 300.0, high_hz: float = 3400.0, order: int = 4):
        self.sos = butter(order, [low_hz, high_hz], btype="bandpass",
                          fs=samplerate, output="sos")
        self.zi = np.zeros((self.sos.shape[0], 2, channels))

    def process(self, block: np.ndarray) -> np.ndarray:
        """block: (frames, channels) float. Devuelve el bloque filtrado."""
        out, self.zi = sosfilt(self.sos, block, axis=0, zi=self.zi)
        return out


class Envelope:
    """Seguidor de envolvente con ataque y release independientes, en dB.

    Se suaviza en dominio dB (no lineal) para que el release sea parejo:
    en lineal, caer 40 dB con 150 ms de constante tarda ~0,7 s y el canal
    queda "hablando" de más; en dB cae en ~0,2 s.
    """

    def __init__(self, channels: int, block_ms: float,
                 attack_ms: float = 20.0, release_ms: float = 150.0):
        self.a_att = float(np.exp(-block_ms / attack_ms))
        self.a_rel = float(np.exp(-block_ms / release_ms))
        self.state = np.full(channels, DB_MIN)

    def process(self, level_db: np.ndarray) -> np.ndarray:
        rising = level_db > self.state
        coef = np.where(rising, self.a_att, self.a_rel)
        self.state = coef * self.state + (1.0 - coef) * level_db
        return self.state


class NoiseFloor:
    """Piso de ruido = percentil bajo del nivel en una ventana deslizante.

    Guarda una muestra cada `decimate` bloques para que la ventana de 30 s
    no cueste CPU. Mientras no haya 1 s de historia devuelve `initial_db`.
    """

    def __init__(self, channels: int, block_ms: float, window_s: float = 30.0,
                 percentile: float = 10.0, decimate: int = 5,
                 initial_db: float = -70.0):
        self.decimate = decimate
        self.percentile = percentile
        size = max(1, int(window_s * 1000 / block_ms / decimate))
        self.buf = np.full((size, channels), np.nan)
        self.min_samples = max(1, int(1000 / block_ms / decimate))
        self.idx = 0
        self.count = 0
        self.tick = 0
        self.value = np.full(channels, initial_db)

    def process(self, level_db: np.ndarray) -> np.ndarray:
        self.tick += 1
        if self.tick % self.decimate:
            return self.value
        self.buf[self.idx] = level_db
        self.idx = (self.idx + 1) % len(self.buf)
        self.count = min(self.count + 1, len(self.buf))
        if self.count >= self.min_samples:
            self.value = np.nanpercentile(self.buf[: self.count] if self.count < len(self.buf)
                                          else self.buf, self.percentile, axis=0)
        return self.value


@dataclass
class MeterConfig:
    samplerate: int = 48000
    block_ms: float = 10.0
    attack_ms: float = 20.0
    release_ms: float = 150.0
    margin_db: float = 12.0        # umbral = piso + margen
    min_threshold_db: float = -60.0  # nunca por debajo de esto (sala muy silenciosa)
    floor_window_s: float = 30.0

    @property
    def block_frames(self) -> int:
        return int(self.samplerate * self.block_ms / 1000)


@dataclass
class MeterReading:
    level_db: np.ndarray      # envolvente en dBFS, banda de voz
    peak_db: np.ndarray       # pico del bloque, señal sin filtrar (para clip)
    floor_db: np.ndarray
    threshold_db: np.ndarray
    active: np.ndarray        # bool por canal


class ChannelMeter:
    """Medidor completo para N canales. Un objeto por dispositivo de audio."""

    def __init__(self, channels: int, config: MeterConfig | None = None,
                 threshold_db: list[float | None] | None = None):
        self.cfg = config or MeterConfig()
        self.channels = channels
        self.filter = VoiceBandFilter(self.cfg.samplerate, channels)
        self.env = Envelope(channels, self.cfg.block_ms,
                            self.cfg.attack_ms, self.cfg.release_ms)
        self.floor = NoiseFloor(channels, self.cfg.block_ms, self.cfg.floor_window_s)
        # Umbral manual por canal (None = automático)
        self.manual = np.array([np.nan if t is None else t
                                for t in (threshold_db or [None] * channels)])

    def process(self, block: np.ndarray) -> MeterReading:
        if block.ndim == 1:
            block = block[:, None]
        peak_db = to_dbfs(np.max(np.abs(block), axis=0))
        filtered = self.filter.process(block)
        rms = np.sqrt(np.mean(filtered ** 2, axis=0))
        level_db = self.env.process(to_dbfs(rms))
        floor_db = self.floor.process(level_db)
        auto = np.maximum(floor_db + self.cfg.margin_db, self.cfg.min_threshold_db)
        threshold_db = np.where(np.isnan(self.manual), auto, self.manual)
        return MeterReading(level_db, peak_db, floor_db, threshold_db,
                            level_db > threshold_db)


def dominant(reading: MeterReading, margin_db: float = 6.0) -> int | None:
    """Índice del canal que habla claramente por encima del resto, o None.

    Versión simple para el medidor: gana el canal activo más fuerte si
    supera al segundo por `margin_db`. El anti-cruce real llega en el motor.
    """
    active = np.flatnonzero(reading.active)
    if active.size == 0:
        return None
    if active.size == 1:
        return int(active[0])
    order = active[np.argsort(reading.level_db[active])[::-1]]
    first, second = reading.level_db[order[0]], reading.level_db[order[1]]
    return int(order[0]) if first - second >= margin_db else None
