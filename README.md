# VoxSwitch

> Nombre provisorio, a confirmar.

Switcher automático por audio para podcast y streaming, **gratuito y open source (GPLv3)**, exclusivo para NDI.

Escucha los micrófonos de la consola, detecta quién habla y corta la cámara correspondiente. El Program sale como fuente NDI (con audio embebido), en pantalla completa y con tally NDI. Opcionalmente controla vMix y OBS.

**Estado:** v0.1 en desarrollo. Ya funciona el [medidor de audio](tools/README.md), que es la etapa 1.

## Cómo funciona

```
Cámaras NDI (cualquier marca) ─┐
                               ├─► [Motor de audio → decisión de corte] ─► [Núcleo de video NDI] ─┬─► NDI Program (OBS / vMix / conversor)
Consola/interfaz USB ──────────┘                                                                  ├─► Pantalla completa
                                                                                                  ├─► Tally NDI
                                                                                                  └─► Control vMix / OBS / Companion
```

## Requisitos previstos

- Windows 10/11 64 bit.
- Cámaras NDI full o NDI|HX.
- Consola o interfaz de audio por USB con un canal por micrófono. Con una consola estéreo por USB alcanza para 2 micrófonos paneados L/R.
- Red gigabit dedicada al video.

## Estructura

| Carpeta | Contenido |
| --- | --- |
| `engine/` | Motor de audio: captura, medición, anti-cruce y reglas de corte (sin UI) |
| `engine/tests/` | Tests con grabaciones reales y cortes esperados |
| `video/` | Receptores NDI, framesync, emisión del Program, pantalla completa |
| `outputs/` | Salidas como plugins: NDI Program, tally, pantalla completa, vMix, OBS, Companion |
| `ui/` | Interfaz (PySide6) |
| `profiles/` | Esquema y ejemplos de perfiles |
| `installer/` | Instalador (Inno Setup) |
| `tools/` | Herramientas de diagnóstico, por ejemplo el [medidor de audio](tools/README.md) |
| `docs/` | Manual ES/EN |

Ver [ROADMAP.md](ROADMAP.md) y [CONTRIBUTING.md](CONTRIBUTING.md).

## Licencia

GPLv3. Ver [LICENSE](LICENSE).

NDI® is a registered trademark of Vizrt NDI AB. Este proyecto no está afiliado a Vizrt. El NDI SDK no se incluye en este repositorio: se descarga desde el sitio oficial de NDI bajo su propia licencia.
