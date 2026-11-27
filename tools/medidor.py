"""Medidor de audio por canal — etapa 1 de la v0.1.

Sirve para validar el setup antes de que exista el motor de corte:
  - que cada micrófono llegue por su canal (p. ej. mic 1 en L, mic 2 en R),
  - el piso de ruido real de la sala,
  - el umbral automático y quién "gana" cuando hablan.

Uso (desde la raíz del repo):
  python -m tools.medidor --list
  python -m tools.medidor --device 12 --channels 1,2 --names Gus,Invitado
  python -m tools.medidor --wav charla.wav --channels 1,2 --names Gus,Invitado
  python -m tools.medidor --device 12 --log niveles.csv

Ctrl+C termina y muestra un resumen con valores sugeridos.
"""

from __future__ import annotations

import argparse
import csv
import os
import queue
import sys
import time

import numpy as np

from engine.levels import ChannelMeter, MeterConfig, dominant
from engine.sources import LiveSource, WavSource, list_input_devices

BAR_MIN_DB, BAR_MAX_DB, BAR_WIDTH = -70.0, 0.0, 50
REFRESH_S = 1 / 15  # 15 fps en pantalla; la medición sigue a 100 bloques/s

GREEN, YELLOW, RED, DIM, BOLD, RESET = ("\033[32m", "\033[33m", "\033[31m",
                                        "\033[2m", "\033[1m", "\033[0m")


def enable_ansi() -> None:
    """Activa secuencias ANSI en la consola de Windows 10/11."""
    if os.name == "nt":
        os.system("")


def bar(level_db: float, threshold_db: float, active: bool) -> str:
    span = BAR_MAX_DB - BAR_MIN_DB
    fill = int(np.clip((level_db - BAR_MIN_DB) / span, 0, 1) * BAR_WIDTH)
    mark = int(np.clip((threshold_db - BAR_MIN_DB) / span, 0, 1) * BAR_WIDTH)
    color = GREEN if active else DIM
    cells = []
    for i in range(BAR_WIDTH):
        if i == mark:
            cells.append(f"{YELLOW}|{RESET}")
        elif i < fill:
            cells.append(f"{color}█{RESET}")
        else:
            cells.append(f"{DIM}·{RESET}")
    return "".join(cells)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Medidor de audio por canal")
    p.add_argument("--list", action="store_true", help="listar dispositivos de entrada")
    p.add_argument("--device", help="índice o parte del nombre del dispositivo")
    p.add_argument("--wav", help="usar un archivo WAV en lugar de la placa")
    p.add_argument("--fast", action="store_true", help="con --wav: no esperar tiempo real")
    p.add_argument("--channels", default="1,2", help="canales 1-based, p. ej. 1,2")
    p.add_argument("--names", help="nombres por canal, p. ej. Gus,Invitado")
    p.add_argument("--samplerate", type=int, default=48000)
    p.add_argument("--margin", type=float, default=12.0, help="umbral = piso + margen (dB)")
    p.add_argument("--threshold", help="umbral manual por canal en dBFS, p. ej. -45,-48")
    p.add_argument("--log", help="guardar niveles cada 100 ms en un CSV")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    enable_ansi()

    if args.list:
        print(f"{'Idx':>4}  {'API':<22} {'Entradas':>8}  {'Hz':>6}  Nombre")
        for d in list_input_devices():
            print(f"{d['index']:>4}  {d['api']:<22} {d['inputs']:>8}  "
                  f"{d['samplerate']:>6}  {d['name']}")
        print("\nTip: para la MG12XU elegí la entrada 'Yamaha' / 'USB Audio CODEC' "
              "con 2 entradas. Si aparece por WASAPI, preferila sobre MME.")
        return 0

    channels = [int(c) for c in args.channels.split(",")]
    names = (args.names.split(",") if args.names
             else [f"CH{c}" for c in channels])
    if len(names) != len(channels):
        print("Error: --names debe tener un nombre por canal.", file=sys.stderr)
        return 2
    manual = None
    if args.threshold:
        manual = [float(t) for t in args.threshold.split(",")]
        if len(manual) != len(channels):
            print("Error: --threshold debe tener un valor por canal.", file=sys.stderr)
            return 2

    if args.wav:
        src = WavSource(args.wav, channels, realtime=not args.fast)
        cfg = MeterConfig(samplerate=src.samplerate, margin_db=args.margin)
        src.block_frames = cfg.block_frames
        origin = f"WAV {args.wav}"
    else:
        device = args.device
        if device is not None and device.isdigit():
            device = int(device)
        cfg = MeterConfig(samplerate=args.samplerate, margin_db=args.margin)
        src = LiveSource(device, channels, cfg.samplerate, cfg.block_frames)
        origin = f"dispositivo {args.device or 'por defecto'}"

    meter = ChannelMeter(len(channels), cfg, manual)
    log_file = open(args.log, "w", newline="") if args.log else None
    log = csv.writer(log_file) if log_file else None
    if log:
        log.writerow(["t_s"] + [f"{n}_dB" for n in names] + [f"{n}_activo" for n in names])

    # Estadísticas para el resumen final
    speech = [[] for _ in channels]
    talk_blocks = np.zeros(len(channels), dtype=int)
    clips = np.zeros(len(channels), dtype=int)
    n_blocks = 0
    last_draw = 0.0
    last_log_block = -10

    try:
        src.start()
    except Exception as exc:  # PortAudio da errores muy variados según driver
        print(f"No pude abrir el audio ({origin}): {exc}", file=sys.stderr)
        print("Probá con --list y elegí otro índice o API (WASAPI suele ir mejor).",
              file=sys.stderr)
        return 1

    print("\033[2J", end="")
    try:
        for block in src.blocks():
            r = meter.process(block)
            n_blocks += 1
            talker = dominant(r)
            for i in range(len(channels)):
                if r.peak_db[i] > -0.5:
                    clips[i] += 1
            if talker is not None:
                talk_blocks[talker] += 1
                # "Voz normal" solo cuando ese canal domina: así el cruce
                # de la voz del otro no baja el promedio.
                speech[talker].append(r.level_db[talker])

            t = n_blocks * cfg.block_ms / 1000
            if log and n_blocks - last_log_block >= 10:
                last_log_block = n_blocks
                log.writerow([f"{t:.2f}"] + [f"{v:.1f}" for v in r.level_db]
                             + [int(a) for a in r.active])

            now = time.perf_counter()
            if now - last_draw < REFRESH_S:
                continue
            last_draw = now
            lines = [f"{BOLD}VoxSwitch · medidor{RESET}   {origin}   "
                     f"{cfg.samplerate} Hz   t={t:6.1f}s",
                     f"{DIM}barra: {BAR_MIN_DB:.0f}…{BAR_MAX_DB:.0f} dBFS (banda de voz)"
                     f"   {YELLOW}|{RESET}{DIM} = umbral{RESET}", ""]
            for i, name in enumerate(names):
                state = (f"{GREEN}{BOLD}HABLA{RESET}" if r.active[i]
                         else f"{DIM}  -  {RESET}")
                clip = f" {RED}CLIP{RESET}" if r.peak_db[i] > -0.5 else ""
                lines.append(f"{name[:10]:<10} {bar(r.level_db[i], r.threshold_db[i], r.active[i])}"
                             f" {r.level_db[i]:6.1f} dB  {state}{clip}")
                lines.append(f"{'':<10} {DIM}piso {r.floor_db[i]:6.1f}  "
                             f"umbral {r.threshold_db[i]:6.1f}{RESET}")
            lines.append("")
            who = names[talker] if talker is not None else "—"
            lines.append(f"Al aire iría: {BOLD}{who}{RESET}")
            lines.append(f"{DIM}overflows placa: {src.overflows}   "
                         f"bloques descartados: {src.dropped}   Ctrl+C para salir{RESET}")
            print("\033[H" + "\n".join(f"{ln}\033[K" for ln in lines), end="", flush=True)
    except KeyboardInterrupt:
        pass
    except queue.Empty:
        print("\n\nNo llega audio del dispositivo (1 s sin bloques).", file=sys.stderr)
    finally:
        src.stop()
        if log_file:
            log_file.close()

    # Resumen con valores sugeridos para el perfil
    dur = n_blocks * cfg.block_ms / 1000
    print(f"\n\n{BOLD}Resumen{RESET} ({dur:.0f} s medidos)")
    for i, name in enumerate(names):
        voz = f"{np.median(speech[i]):.1f} dBFS" if speech[i] else "sin voz detectada"
        share = 100 * talk_blocks[i] / max(1, n_blocks)
        print(f"  {name:<10} piso {meter.floor.value[i]:6.1f} dBFS · voz normal {voz} · "
              f"habló claro {share:4.1f} % · clips {clips[i]}")
    if src.overflows or src.dropped:
        print(f"  {YELLOW}Atención:{RESET} overflows={src.overflows} descartados={src.dropped}. "
              "Probá otra API (WASAPI) o cerrá programas que usen la placa.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
