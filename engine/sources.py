"""Fuentes de audio: placa en vivo (PortAudio) o archivo WAV.

Ambas entregan bloques float32 de forma (frames, canales) con solo los
canales pedidos, para que el resto del motor no sepa de dónde viene el audio.
"""

from __future__ import annotations

import queue
import time
from typing import Iterator

import numpy as np


def list_input_devices() -> list[dict]:
    """Dispositivos con entradas, con el nombre del host API (MME, WASAPI, ASIO…)."""
    import sounddevice as sd

    hostapis = sd.query_hostapis()
    out = []
    for idx, dev in enumerate(sd.query_devices()):
        if dev["max_input_channels"] > 0:
            out.append({
                "index": idx,
                "name": dev["name"],
                "api": hostapis[dev["hostapi"]]["name"],
                "inputs": dev["max_input_channels"],
                "samplerate": int(dev["default_samplerate"]),
            })
    return out


class LiveSource:
    """Captura en vivo. El callback solo copia y encola: nada de cálculo ahí.

    channels: lista 1-based de canales físicos a usar, p. ej. [1, 2] = L y R.
    """

    def __init__(self, device: int | str | None, channels: list[int],
                 samplerate: int = 48000, block_frames: int = 480):
        self.device = device
        self.channels = channels
        self.cols = [c - 1 for c in channels]
        self.samplerate = samplerate
        self.block_frames = block_frames
        self.q: queue.Queue[np.ndarray] = queue.Queue(maxsize=200)  # ~2 s de colchón
        self.overflows = 0   # la placa perdió muestras
        self.dropped = 0     # el consumidor se atrasó
        self._stream = None

    def _callback(self, indata, frames, time_info, status):
        if status.input_overflow:
            self.overflows += 1
        try:
            self.q.put_nowait(indata[:, self.cols].copy())
        except queue.Full:
            self.dropped += 1

    def start(self) -> None:
        import sounddevice as sd

        self._stream = sd.InputStream(
            device=self.device,
            channels=max(self.channels),
            samplerate=self.samplerate,
            blocksize=self.block_frames,
            dtype="float32",
            latency="low",
            callback=self._callback,
        )
        self._stream.start()

    def stop(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def blocks(self, timeout: float = 1.0) -> Iterator[np.ndarray]:
        while True:
            yield self.q.get(timeout=timeout)


class WavSource:
    """Lee un WAV por bloques. realtime=True respeta el tiempo real (simulación)."""

    def __init__(self, path: str, channels: list[int], block_frames: int = 480,
                 realtime: bool = True):
        import soundfile as sf

        self._sf = sf.SoundFile(path)
        self.samplerate = self._sf.samplerate
        self.channels = channels
        self.cols = [c - 1 for c in channels]
        if max(channels) > self._sf.channels:
            raise ValueError(f"El archivo tiene {self._sf.channels} canales; "
                             f"se pidió el canal {max(channels)}.")
        self.block_frames = block_frames
        self.realtime = realtime
        self.overflows = 0
        self.dropped = 0

    def start(self) -> None:
        pass

    def stop(self) -> None:
        self._sf.close()

    def blocks(self, timeout: float = 1.0) -> Iterator[np.ndarray]:
        period = self.block_frames / self.samplerate
        t_next = time.perf_counter()
        for data in self._sf.blocks(blocksize=self.block_frames, dtype="float32",
                                    always_2d=True):
            if len(data) < self.block_frames:
                break
            yield data[:, self.cols]
            if self.realtime:
                t_next += period
                delay = t_next - time.perf_counter()
                if delay > 0:
                    time.sleep(delay)
