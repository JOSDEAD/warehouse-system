Coloca aquí el archivo de sonido de alerta.
Nombre esperado: nuevo_pedido.mp3

El sonido debe ser corto (2-5 segundos).
Formatos soportados: .mp3, .wav, .ogg

Si usas un nombre diferente, actualiza SOUND_FILE en tu archivo .env:

    SOUND_FILE=sounds/mi_sonido.wav

---------------------------------------------------------------
NOTAS TÉCNICAS
---------------------------------------------------------------
- El archivo se carga al iniciar el daemon.
- Si el archivo no existe, el daemon usará un beep del sistema
  como respaldo y mostrará una advertencia en la terminal.
- Para el mejor rendimiento en reproducción repetida, se
  recomienda el formato .wav sin comprimir.
- En Windows, asegúrate de tener instalados los drivers de audio.
- En Linux, pygame requiere SDL2 con soporte de audio.
  Instala: sudo apt install libsdl2-mixer-2.0-0
