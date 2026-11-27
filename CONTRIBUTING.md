# Cómo contribuir

¡Gracias por sumarte! Este proyecto es gratuito y open source (GPLv3).

## Antes de empezar

1. Abrí un issue describiendo el cambio, el bug o el setup (cámaras, consola, red) antes de escribir código grande.
2. Revisá el [ROADMAP](ROADMAP.md): lo que está fuera de la versión actual puede esperar.

## Reglas

- El motor (`engine/`) no importa nada de `ui/` ni de `video/`.
- Una salida nueva va en `outputs/` e implementa el contrato común: `on_cut`, `on_preview`, `on_tally`, `status`.
- Todo cambio en el motor viene con un test en `engine/tests/`.
- El camino de video nunca debe bloquearse: nada de I/O de red o disco en el hilo de video.
- Textos de la interfaz en español e inglés.
- No se suben el NDI SDK ni binarios de terceros al repositorio.

## Licencia

Al contribuir aceptás que tu código se publique bajo GPLv3.
