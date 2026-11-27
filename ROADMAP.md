# Roadmap

Cada versión se publica solo cuando cumple su criterio de salida en un podcast real.

| Versión | Alcance | Criterio de salida |
| --- | --- | --- |
| v0.1 — Motor de audio | Captura, medición, anti-cruce y reglas de corte. Interfaz mínima. Dos salidas: control de vMix por API y NDI Program básico. | En 3 grabaciones reales, al menos 90 % de los cortes automáticos son correctos y no hay ping-pong. |
| v1.0 — Switcher NDI | Receptores con framesync, NDI Program con audio, tally NDI, fail-safes, perfiles, asistente de configuración, modo aprendizaje. | 4 horas seguidas con 4 cámaras sin caída de la salida ni pérdida de sync. |
| v2.0 — Salidas y control | Pantalla completa multi-monitor, preview NDI, control OBS, Companion, modo liviano por routing NDI, control PTZ (VISCA over IP y PTZ NDI) con presets. | Probado en al menos 3 setups distintos de la comunidad. |
| v3.0 — Grabación y post | ISO por cámara, audio multipista, editor de cortes, export FCPXML/EDL para DaVinci y Premiere. | Un episodio completo re-editado y exportado sin pasos manuales. |

## Decisiones tomadas

- Solo cortes secos, sin mix ni DVE.
- Cámaras NDI de cualquier marca, full o HX.
- Audio: cualquier consola o interfaz USB. Se pueden leer varios dispositivos a la vez.
- Sin telemetría ni login: funciona 100 % offline.
