# Herramientas

## Medidor de audio (`medidor.py`)

Etapa 1 de la v0.1. Muestra el nivel de cada micrófono en vivo, el piso de ruido, el umbral automático y quién "iría al aire". Sirve para validar el setup antes de usar el motor de corte.

### Instalación (Windows, una sola vez)

1. Instalá Python 3.12 o 3.13 desde python.org y tildá **Add python.exe to PATH**.
2. En PowerShell, parado en la carpeta del repo:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Uso

1. Listar las placas de audio y anotar el índice de la consola. Para la MG12XU, buscá la entrada de 2 canales, mejor si es por WASAPI:

```powershell
python -m tools.medidor --list
```

2. Medir en vivo. En la consola, el mic 1 va paneado todo a L y el mic 2 todo a R:

```powershell
python -m tools.medidor --device 12 --channels 1,2 --names Gus,Invitado
```

3. Probar con un archivo grabado en vez de la placa:

```powershell
python -m tools.medidor --wav charla.wav --channels 1,2 --names Gus,Invitado
```

### Qué mirar

- **Cada barra se mueve solo con su micrófono.** Si las dos se mueven parejo, el paneo no está a fondo.
- **Piso:** con la sala en silencio, idealmente por debajo de -60 dBFS.
- **Voz:** hablando normal, entre -30 y -15 dBFS. Si aparece **CLIP**, bajá la ganancia o el fader master.
- **"Al aire iría":** tiene que seguir a quien habla. Cuando hablan los dos a la vez muestra "—", y eso es lo correcto.

Con Ctrl+C sale y muestra un resumen por canal: piso, voz normal y porcentaje de tiempo hablando. Esos valores se usan después para el perfil.

### Opciones

| Opción | Para qué |
| --- | --- |
| `--margin 12` | Umbral = piso + margen, en dB. Subilo si la sala es ruidosa. |
| `--threshold -45,-48` | Umbral manual por canal, en dBFS. Reemplaza al automático. |
| `--log niveles.csv` | Guarda los niveles cada 100 ms, por ejemplo para mandármelos. |
| `--fast` | Con `--wav`: procesa sin esperar el tiempo real. |
