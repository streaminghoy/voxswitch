import numpy as np

from engine.levels import (ChannelMeter, MeterConfig, VoiceBandFilter, dominant,
                           to_dbfs)

FS = 48000
BLOCK = 480


def tone(freq, seconds, amp=0.1, fs=FS):
    t = np.arange(int(seconds * fs)) / fs
    return amp * np.sin(2 * np.pi * freq * t)


def run(meter, signal):
    """Procesa una señal (frames, ch) por bloques y devuelve la última lectura."""
    reading = None
    for i in range(0, len(signal) - BLOCK + 1, BLOCK):
        reading = meter.process(signal[i:i + BLOCK])
    return reading


def test_dbfs_full_scale_and_floor():
    assert np.isclose(to_dbfs(1.0), 0.0)
    assert np.isclose(to_dbfs(0.1), -20.0)
    assert to_dbfs(0.0) == -100.0


def test_voice_filter_rejects_hum_and_passes_voice():
    f = VoiceBandFilter(FS, 1)
    hum = f.process(tone(50, 1.0)[:, None])[FS // 2:]
    f = VoiceBandFilter(FS, 1)
    voice = f.process(tone(1000, 1.0)[:, None])[FS // 2:]
    rms = lambda x: np.sqrt(np.mean(x ** 2))
    assert to_dbfs(rms(hum)) < to_dbfs(rms(voice)) - 40


def test_noise_floor_and_activation():
    rng = np.random.default_rng(0)
    noise = rng.normal(0, 0.001, (FS * 3, 1))          # ~ -60 dBFS de ruido
    meter = ChannelMeter(1, MeterConfig())
    quiet = run(meter, noise)
    assert not quiet.active[0]
    assert quiet.floor_db[0] < -55
    loud = run(meter, noise[: FS // 2] + tone(800, 0.5, amp=0.1)[:, None])
    assert loud.active[0]
    assert loud.level_db[0] > loud.threshold_db[0]


def test_release_drops_quickly_after_speech():
    rng = np.random.default_rng(3)
    meter = ChannelMeter(1, MeterConfig())
    run(meter, rng.normal(0, 0.001, (FS * 3, 1)))
    assert run(meter, tone(800, 0.5, amp=0.15)[:, None]).active[0]
    after = run(meter, rng.normal(0, 0.001, (int(FS * 0.3), 1)))
    assert not after.active[0]                         # suelta en < 300 ms


def test_manual_threshold_overrides_auto():
    meter = ChannelMeter(1, MeterConfig(), threshold_db=[-10.0])
    r = run(meter, tone(800, 0.5, amp=0.1)[:, None])  # ~ -23 dBFS
    assert r.threshold_db[0] == -10.0
    assert not r.active[0]


def test_dominant_picks_clear_winner_only():
    meter = ChannelMeter(2, MeterConfig())
    rng = np.random.default_rng(1)
    base = rng.normal(0, 0.001, (FS * 2, 2))
    run(meter, base)                                   # aprende el piso
    a = tone(700, 0.5, amp=0.2)
    clear = base[: FS // 2].copy()
    clear[:, 0] += a
    clear[:, 1] += a * 0.1                             # cruce 20 dB abajo
    assert dominant(run(meter, clear)) == 0
    both = base[: FS // 2].copy()
    both[:, 0] += a
    both[:, 1] += a * 0.9                              # hablan los dos parejo
    assert dominant(run(meter, both)) is None
