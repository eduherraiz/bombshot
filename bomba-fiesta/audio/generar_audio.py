#!/usr/bin/env python3
"""
Genera los ficheros de audio de la bomba de juguete.

Salida (en ./out/):
  bomba_60.mp3   tic-tac acelerando durante 60 s + explosión final
  bomba_boom.mp3 explosión suelta (corte del cable equivocado)
  bomba_ok.mp3   sonido de desactivada

Uso:
  python3 generar_audio.py            # 60 segundos por defecto
  python3 generar_audio.py --seg 90   # otra duración

Requisitos: numpy y ffmpeg en el PATH.
"""

import argparse
import os
import subprocess
import numpy as np

SR = 44100


# ---------------------------------------------------------------- utilidades
def envolvente(n, ataque=0.002, decay=25.0):
    """Envolvente percusiva: ataque muy corto y caída exponencial."""
    t = np.arange(n) / SR
    env = np.exp(-decay * t)
    na = max(1, int(ataque * SR))
    env[:na] *= np.linspace(0, 1, na)
    return env


def paso_bajo(x, alpha=0.15):
    """Filtro paso bajo de un polo. Suficiente para dar cuerpo al ruido."""
    y = np.zeros_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc += alpha * (x[i] - acc)
        y[i] = acc
    return y


def ruido_marron(n, rng):
    """Ruido marrón = ruido blanco integrado. Da el 'rumble' grave."""
    x = np.cumsum(rng.standard_normal(n))
    x -= np.linspace(x[0], x[-1], n)   # quita la deriva DC
    return x / (np.max(np.abs(x)) + 1e-9)


def mezclar(destino, muestra, pos):
    """Suma `muestra` sobre `destino` a partir de la posición `pos`."""
    ini = int(pos * SR)
    fin = min(ini + len(muestra), len(destino))
    if ini >= len(destino):
        return
    destino[ini:fin] += muestra[: fin - ini]


# ---------------------------------------------------------------- sonidos
def click(f0=1500.0, dur=0.05, decay=55.0, rng=None):
    """Tic mecánico: sinusoide percusiva + pizca de ruido en el ataque."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    cuerpo = np.sin(2 * np.pi * f0 * t) + 0.35 * np.sin(2 * np.pi * f0 * 2.7 * t)
    transitorio = np.zeros(n)
    nt = int(0.004 * SR)
    if rng is not None:
        transitorio[:nt] = rng.standard_normal(nt) * 0.8
    return (cuerpo + transitorio) * envolvente(n, decay=decay) * 0.5


def explosion(dur=3.5, rng=None):
    """Crack inicial + rumble grave con caída de tono."""
    n = int(dur * SR)
    t = np.arange(n) / SR

    # Golpe seco de entrada
    crack = rng.standard_normal(n) * np.exp(-30.0 * t)

    # Cuerpo grave: ruido marrón filtrado con caída lenta
    cuerpo = paso_bajo(ruido_marron(n, rng), alpha=0.03)
    cuerpo *= np.exp(-1.6 * t)

    # Barrido descendente que da la sensación de "boom"
    f = 220.0 * np.exp(-1.9 * t) + 28.0
    fase = 2 * np.pi * np.cumsum(f) / SR
    sub = np.sin(fase) * np.exp(-1.1 * t)

    mix = 0.45 * crack + 1.0 * cuerpo + 0.8 * sub
    return mix / (np.max(np.abs(mix)) + 1e-9) * 0.95


def explosion_grande(rng):
    """Varias explosiones encadenadas (boom... boom-BOOM) en vez de una
    sola corta: mas larga y mas contundente. Se solapan un poco para que
    no suene como golpes sueltos sino como una cadena continua."""
    duraciones = [1.6, 1.8, 3.5]
    intensidades = [0.55, 0.75, 1.0]
    offsets = [0.0, 0.5, 1.15]
    total_dur = offsets[-1] + duraciones[-1] + 0.3
    total = np.zeros(int(total_dur * SR))
    for dur, inten, off in zip(duraciones, intensidades, offsets):
        mezclar(total, explosion(dur=dur, rng=rng) * inten, off)
    pico = np.max(np.abs(total))
    if pico > 0:
        total = total / pico * 0.95
    return total


def desactivada(rng):
    """Dos pitidos ascendentes: 'a salvo'."""
    out = np.zeros(int(1.4 * SR))
    for i, f in enumerate((660.0, 990.0)):
        n = int(0.28 * SR)
        t = np.arange(n) / SR
        tono = np.sin(2 * np.pi * f * t) * 0.45
        tono *= np.minimum(1.0, np.exp(-4.0 * (t - 0.20).clip(0)))
        na = int(0.01 * SR)
        tono[:na] *= np.linspace(0, 1, na)
        mezclar(out, tono, 0.05 + i * 0.32)
    return out


# ---------------------------------------------------------------- cadencia
def intervalo(restante):
    """Cada cuánto suena el tic según los segundos que quedan."""
    if restante > 30:
        return 1.00
    if restante > 10:
        return 0.50
    if restante > 5:
        return 0.25
    return 0.12


def pista_cuenta_atras(segundos, rng):
    cola = 6.2  # explosion_grande dura mas que la explosion suelta
    total = np.zeros(int((segundos + cola) * SR))

    # --- tics ---
    t = 0.0
    alterna = False
    while t < segundos:
        restante = segundos - t
        # el tono sube un poco conforme aprieta el tiempo
        agudo = restante <= 10
        f0 = (1900.0 if agudo else 1400.0) * (1.08 if alterna else 1.0)
        mezclar(total, click(f0=f0, rng=rng), t)
        t += intervalo(restante)
        alterna = not alterna

    # --- drone de tensión en los últimos 12 s ---
    ini = max(0.0, segundos - 12.0)
    n = int((segundos - ini) * SR)
    td = np.arange(n) / SR
    f = 55.0 + 25.0 * (td / max(td[-1], 1e-9))
    drone = np.sin(2 * np.pi * np.cumsum(f) / SR)
    drone *= np.linspace(0.0, 0.28, n)
    mezclar(total, drone, ini)

    # --- explosión justo al agotarse el tiempo ---
    mezclar(total, explosion_grande(rng), segundos)

    return total


# ---------------------------------------------------------------- export
def guardar(nombre, datos, outdir, flac=False):
    """Escribe el sonido como MP3 y, si `flac`, tambien como FLAC 48 kHz
    mono 16 bits.

    El FLAC no es un capricho: es EXACTAMENTE el formato del
    `announcement_pipeline` del firmware del Voice PE (FLAC / 48000 / 1
    canal), asi que el ESP32 lo reproduce sin decodificar MP3 ni
    remuestrear de 44.1 a 48. Para la pista de cuenta atras -- 36 s, el
    fichero mas largo y el que daba problemas -- esa diferencia importa.
    Para los clips cortos el MP3 sobra.
    """
    pico = np.max(np.abs(datos))
    if pico > 0:
        datos = datos / pico * 0.89          # normaliza dejando headroom
    pcm = (datos * 32767).astype(np.int16)

    wav = os.path.join(outdir, nombre + ".wav")
    mp3 = os.path.join(outdir, nombre + ".mp3")

    import wave
    with wave.open(wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())

    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-b:a", "128k", mp3],
        check=True,
    )
    print(f"  {mp3}  ({len(datos)/SR:.1f} s)")

    if flac:
        dst = os.path.join(outdir, nombre + ".flac")
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", wav,
             "-ac", "1", "-ar", "48000", "-sample_fmt", "s16", "-c:a", "flac",
             dst],
            check=True,
        )
        print(f"  {dst}  ({len(datos)/SR:.1f} s)")

    os.remove(wav)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seg", type=int, default=60, help="duración de la partida")
    ap.add_argument("--out", default="out", help="carpeta de salida")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    rng = np.random.default_rng(args.seed)

    print("Generando audio...")
    # La cuenta atras se llama siempre igual (cuenta_atras.*) porque es el
    # nombre que espera esphome/standalone.yaml; los segundos van en el log.
    guardar("cuenta_atras", pista_cuenta_atras(args.seg, rng), args.out, flac=True)
    guardar("bomba_boom", explosion_grande(rng), args.out)
    guardar("bomba_ok", desactivada(rng), args.out)
    print()
    print("Listo. Copia cuenta_atras.flac y los mp3 a esphome/sounds/.")
    if args.seg != 30:
        print(f"OJO: has generado una cuenta atras de {args.seg} s. Cambia tambien")
        print("     el `delay: 30s` de bomba_partida en esphome/standalone.yaml,")
        print("     o el juego y el audio iran cada uno por su lado.")


if __name__ == "__main__":
    main()
