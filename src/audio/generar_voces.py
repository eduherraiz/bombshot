#!/usr/bin/env python3
"""
Genera TODAS las locuciones cortas del juego, siempre como clips
separados y nunca como una frase larga: "Has perdido.", "Bebe un
chupito.", "Has ganado.", "Coge un chicle.", "No se puede armar...".

Separarlas y bajar un poco la velocidad de voz mejora mucho la claridad:
con una sola frase larga la primera mitad salia enredada. Y en clips
sueltos el juego puede meter una pausa entre medias, que en una fiesta
con ruido se agradece.

Usa el mismo motor que los digitos (espeak-ng via ctypes, ver
generar_digitos.py para el porque de ctypes en vez del binario).

Salida (en ./out/): un .flac por entrada de FRASES.

Uso:
  python3 generar_voces.py
  python3 generar_voces.py --velocidad 130
"""

import argparse
import ctypes
import ctypes.util
import os
import subprocess
import wave

AUDIO_OUTPUT_RETRIEVAL = 1
ESPEAK_CHARS_UTF8 = 1
ESPEAK_RATE = 1  # id del parametro "velocidad" en espeak-ng

FRASES = {
    # Derrota
    "perdiste": "Has perdido.",
    "chupito": "Bebe un chupito.",
    # Victoria (misma estructura: veredicto + premio)
    "ganado": "Has ganado.",
    "chicle": "Coge un chicle.",
    # Aviso al intentar armar con un cable ya cortado
    "no_armar": "No se puede armar. Repara los cables antes de empezar.",
}


def cargar_libreria():
    nombre = ctypes.util.find_library("espeak-ng") or "libespeak-ng.so.1"
    lib = ctypes.CDLL(nombre)
    lib.espeak_Synth.argtypes = [
        ctypes.c_char_p, ctypes.c_size_t, ctypes.c_uint, ctypes.c_int,
        ctypes.c_uint, ctypes.c_uint, ctypes.POINTER(ctypes.c_uint), ctypes.c_void_p,
    ]
    return lib


def sintetizar(lib, texto):
    muestras = bytearray()

    CALLBACK = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.POINTER(ctypes.c_short),
                                 ctypes.c_int, ctypes.c_void_p)

    def on_audio(wav, numsamples, events):
        if numsamples > 0 and wav:
            muestras.extend(ctypes.string_at(wav, numsamples * 2))
        return 0

    sintetizar.cb = CALLBACK(on_audio)
    lib.espeak_SetSynthCallback(sintetizar.cb)

    texto_c = texto.encode("utf-8") + b"\0"
    uid = ctypes.c_uint(0)
    lib.espeak_Synth(texto_c, len(texto_c), 0, 0, 0, ESPEAK_CHARS_UTF8,
                      ctypes.byref(uid), None)
    lib.espeak_Synchronize()
    return bytes(muestras)


def guardar_flac(pcm, sample_rate, ruta_wav, ruta_flac):
    with wave.open(ruta_wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm)

    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error", "-i", ruta_wav,
            "-af",
            "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,"
            "areverse,"
            "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,"
            "areverse,"
            "apad=pad_dur=0.15",
            "-ar", "48000", "-ac", "1", ruta_flac,
        ],
        check=True,
    )
    os.remove(ruta_wav)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--velocidad", type=int, default=135,
                     help="palabras por minuto (espeak-ng, defecto ~175)")
    ap.add_argument("--voz", default="es")
    ap.add_argument("--out", default="out")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)

    lib = cargar_libreria()
    sample_rate = lib.espeak_Initialize(AUDIO_OUTPUT_RETRIEVAL, 0, None, 0)
    if sample_rate <= 0:
        raise RuntimeError("No se pudo inicializar espeak-ng")
    if lib.espeak_SetVoiceByName(args.voz.encode()) != 0:
        raise RuntimeError(f"Voz '{args.voz}' no encontrada")
    lib.espeak_SetParameter(ESPEAK_RATE, args.velocidad, 0)

    for nombre, texto in FRASES.items():
        print(f"Generando '{nombre}': '{texto}'")
        pcm = sintetizar(lib, texto)
        wav_tmp = os.path.join(args.out, f"{nombre}.wav")
        flac_out = os.path.join(args.out, f"{nombre}.flac")
        guardar_flac(pcm, sample_rate, wav_tmp, flac_out)
        print(f"  {flac_out}")

    lib.espeak_Terminate()


if __name__ == "__main__":
    main()
