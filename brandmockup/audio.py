"""Original cinematic brand-reveal score (drone, risers, sub-boom hits, whooshes, pulse ostinato), synced to the cuts."""
import wave

import numpy as np
from scipy.signal import fftconvolve, butter, sosfilt

SR = 44100


def cinematic(path, n_states, hit1, hit2, cut=4 / 30, seed=11):
    """hit1 = index of the reveal state, hit2 = index where the reverse construction starts."""
    DUR = n_states * cut
    n = int(DUR * SR)
    L = np.zeros(n); R = np.zeros(n)
    rng = np.random.default_rng(seed)
    cut_t = [k * cut for k in range(n_states)]

    def hz(m): return 440 * 2 ** ((m - 69) / 12)
    def T(d): return np.arange(int(d * SR)) / SR
    def lp(x, f, o=2): return sosfilt(butter(o, f, 'low', fs=SR, output='sos'), x)
    def hp(x, f, o=2): return sosfilt(butter(o, f, 'high', fs=SR, output='sos'), x)
    def bp(x, a, b, o=2): return sosfilt(butter(o, [a, b], 'band', fs=SR, output='sos'), x)


    def add(sig, t0, pan=0.0, gain=1.0, width=0.0):
        i = int(t0 * SR)
        if i >= n or i + len(sig) <= 0: return
        if i < 0: sig = sig[-i:]; i = 0
        sig = sig[: n - i] * gain
        l = sig * np.sqrt((1 - pan) / 2); r = sig * np.sqrt((1 + pan) / 2)
        if width:
            d = int(width * SR); r = np.concatenate([np.zeros(d), r])[:len(sig)]
        L[i:i + len(sig)] += l; R[i:i + len(sig)] += r


    def saw(f, t):
        ph = (f * t) % 1.0
        return 2 * ph - 1


    def varsweep(fs, dur):  # phase-integrated frequency curve
        return np.cumsum(fs) / SR


    # ---- elements ----
    def sub_boom(dur=2.5, f0=62, f1=32):
        t = T(dur)
        f = f1 + (f0 - f1) * np.exp(-t * 7)
        s = np.sin(2 * np.pi * varsweep(f, dur))
        s = s * (1 - np.exp(-t * 400)) * np.exp(-t * 1.6)
        return s + 0.35 * hp(np.tanh(4 * s), 120)  # harmonics so it reads on phone speakers


    def impact(dur=1.8):
        t = T(dur)
        nz = rng.standard_normal(len(t))
        body = lp(nz, 900) * np.exp(-t * 9) * 1.4
        crack = hp(nz, 2500) * np.exp(-t * 30) * 0.9
        tail = bp(nz, 300, 3000) * np.exp(-t * 2.2) * 0.12
        return body + crack + tail


    def braam(root, dur=2.4, bright=1.0):
        t = T(dur)
        s = sum(saw(hz(m) * d, t) for m in (root, root + 7, root + 12) for d in (0.995, 1.0, 1.006))
        env = (1 - np.exp(-t * 60)) * np.exp(-t * 1.3)
        # moving filter: open fast then close
        out = np.zeros_like(s); seg = 2048
        for i in range(0, len(s), seg):
            tt = i / SR
            fc = 300 + bright * 2600 * np.exp(-tt * 2.4)
            out[i:i + seg] = lp(s[max(0, i - 512):i + seg], fc)[-len(s[i:i + seg]):]
        return out * env / 9


    def riser(dur, f_start=300, f_end=6000):
        t = T(dur)
        nz = rng.standard_normal(len(t))
        out = np.zeros_like(nz); seg = 1024
        for i in range(0, len(nz), seg):
            u = i / len(nz)
            fc = f_start * (f_end / f_start) ** u
            out[i:i + seg] = bp(nz[max(0, i - 512):i + seg], fc * 0.7, min(fc * 1.3, 20000))[-len(nz[i:i + seg]):]
        tone_f = 110 * (4 ** (t / dur))
        tone = np.sin(2 * np.pi * varsweep(tone_f, dur)) * 0.25
        env = (t / dur) ** 2.2
        return (out * 0.9 + tone) * env


    def whoosh(dur=0.5, peak=0.55):
        t = T(dur)
        nz = rng.standard_normal(len(t))
        env = np.where(t < dur * peak, (t / (dur * peak)) ** 2, np.exp(-(t - dur * peak) * 14))
        out = np.zeros_like(nz); seg = 512
        for i in range(0, len(nz), seg):
            u = i / len(nz)
            fc = 400 + 3500 * np.sin(np.pi * u)
            out[i:i + seg] = bp(nz[max(0, i - 256):i + seg], fc * 0.6, fc * 1.4)[-len(nz[i:i + seg]):]
        return out * env


    def tick(level=1.0):
        t = T(0.04)
        s = hp(rng.standard_normal(len(t)), 3000) * np.exp(-t * 260) + 0.5 * np.sin(2 * np.pi * 1800 * t) * np.exp(-t * 180)
        return s * level * 1.6


    def pulse(m, dur=0.22):
        t = T(dur)
        s = saw(hz(m), t) + 0.5 * saw(hz(m) * 1.004, t) + 0.6 * np.sin(2 * np.pi * hz(m - 12) * t)
        return lp(s, 900) * (1 - np.exp(-t * 300)) * np.exp(-t * 11)


    def low_tom(f=70):
        t = T(0.6)
        fs = f * (1 + 0.6 * np.exp(-t * 30))
        return np.sin(2 * np.pi * varsweep(fs, 0.6)) * np.exp(-t * 8) + lp(rng.standard_normal(len(t)), 400) * np.exp(-t * 40) * 0.3


    def drone(dur, root):
        t = T(dur)
        s = sum(saw(hz(m) * d, t) for m in (root, root + 7) for d in (0.997, 1.003))
        s = lp(s, 380)
        lfo = 0.8 + 0.2 * np.sin(2 * np.pi * 0.7 * t)
        env = np.minimum(1, t / 0.6) * np.minimum(1, (dur - t) / 0.5).clip(0)
        return s * env * lfo / 4



    D2, F2, A2, Bb1, C2, D3, F3, A3, C3, Bb2 = 38, 41, 45, 34, 36, 50, 53, 57, 48, 46

    HIT1 = cut_t[hit1]
    HIT2 = cut_t[hit2]
    END = cut_t[n_states - 1]

    # construction: drone + ticks + riser into first hit
    add(drone(HIT1 + 0.3, D2), 0, gain=0.5, width=0.012)
    for k in range(1, hit1):
        add(tick(0.35), cut_t[k], pan=rng.uniform(-0.5, 0.5))
    add(riser(HIT1, 250, 7000), 0, gain=0.5, width=0.01)
    add(whoosh(0.35, 0.8), HIT1 - 0.3, gain=0.7, pan=-0.3)

    # HIT 1
    add(sub_boom(2.6), HIT1, gain=0.95)
    add(impact(1.8), HIT1, gain=0.55, width=0.008)
    add(braam(D2, 2.4, 1.0), HIT1, gain=0.55, width=0.015)

    # mockup run: pulse ostinato on every 2 cuts, tom accents every 6 cuts, whooshes on chord changes
    start, end = hit1 + 1, hit2
    prog = [D2, Bb1 + 12, F2, C2 + 12]
    pat = [0, 0, 12, 0, 7, 0]
    for i, k in enumerate(range(start, end, 2)):
        root = prog[((k - start) // 12) % 4]
        add(pulse(root + 12 + pat[i % 6]), cut_t[k], pan=0.35 if i % 2 else -0.35, gain=0.3 + 0.25 * (k - start) / (end - start))
    for k in range(start + 1, end, 6):
        add(low_tom(72), cut_t[k], gain=0.45)
    for k in range(start, end, 12):
        root = prog[((k - start) // 12) % 4]
        add(drone(min(12, end - k) * cut + 0.4, root), cut_t[k], gain=0.35, width=0.012)
        if k > start:
            add(whoosh(0.45, 0.7), cut_t[k] - 0.31, gain=0.6, pan=rng.uniform(-0.6, 0.6))
    for k in range(start, end):
        add(tick(0.15), cut_t[k], pan=rng.uniform(-0.6, 0.6))
    add(riser(1.3, 400, 9000), HIT2 - 1.3, gain=0.55, width=0.01)

    # HIT 2 (smaller) + reverse construction
    add(sub_boom(2.0, 58, 34), HIT2, gain=0.75)
    add(impact(1.2), HIT2, gain=0.4, width=0.008)
    add(braam(Bb1 + 12, 1.6, 0.6), HIT2, gain=0.35, width=0.015)
    for k in range(hit2 + 1, n_states - 1):
        add(tick(0.3 * (1 - (k - hit2 - 1) / max(1, n_states - hit2))), cut_t[k], pan=rng.uniform(-0.5, 0.5))
    add(drone(DUR - HIT2, D2), HIT2, gain=0.3)
    add(sub_boom(1.0, 50, 36), END, gain=0.35)


    # reverb
    ir_len = int(1.8 * SR); t = T(1.8)
    irs = []
    for s in (3, 4):
        r = np.random.default_rng(s).standard_normal(ir_len) * np.exp(-t * 3.0)
        r = lp(r, 5000, 1)
        irs.append(r / np.sqrt((r ** 2).sum()))
    wl = fftconvolve(hp(L, 200), irs[0])[:n]; wr = fftconvolve(hp(R, 200), irs[1])[:n]
    L2 = L + 0.28 * wl; R2 = R + 0.28 * wr
    L2 = hp(L2, 25); R2 = hp(R2, 25)
    fo = np.minimum(1, (n - np.arange(n)) / (0.25 * SR)); fi = np.minimum(1, np.arange(n) / (0.02 * SR))
    L2 *= fo * fi; R2 *= fo * fi
    pk = max(abs(L2).max(), abs(R2).max())
    L2 = np.tanh(1.8 * L2 / pk); R2 = np.tanh(1.8 * R2 / pk)
    pk = max(abs(L2).max(), abs(R2).max())
    st = np.stack([L2, R2], 1) * 0.89 / pk
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((st * 32767).astype(np.int16).tobytes())
    return path


# ------------------------------------------------------------------ shared mixer for the other styles
class _Mix:
    def __init__(self, n_states, cut, seed):
        self.cut = cut
        self.n = int(n_states * cut * SR)
        self.L = np.zeros(self.n); self.R = np.zeros(self.n)
        self.rng = np.random.default_rng(seed)
        self.t = [k * cut for k in range(n_states)]

    def add(self, sig, t0, pan=0.0, gain=1.0):
        i = int(t0 * SR)
        if i >= self.n or i + len(sig) <= 0:
            return
        if i < 0:
            sig = sig[-i:]; i = 0
        sig = sig[: self.n - i] * gain
        self.L[i:i + len(sig)] += sig * np.sqrt((1 - pan) / 2)
        self.R[i:i + len(sig)] += sig * np.sqrt((1 + pan) / 2)

    def finish(self, path, reverb=0.3, hp_hz=30, drive=2.0):
        n = self.n
        t = np.arange(int(1.3 * SR)) / SR
        irs = []
        for s in (1, 2):
            r = np.random.default_rng(s).standard_normal(len(t)) * np.exp(-t * 4.2)
            r = sosfilt(butter(1, 6000, 'low', fs=SR, output='sos'), r)
            irs.append(r / np.sqrt((r ** 2).sum()))
        L = self.L + reverb * fftconvolve(self.L, irs[0])[:n]
        R = self.R + reverb * fftconvolve(self.R, irs[1])[:n]
        hp = butter(2, hp_hz, 'high', fs=SR, output='sos')
        L = sosfilt(hp, L); R = sosfilt(hp, R)
        env = np.minimum(1, np.arange(n) / (0.01 * SR)) * np.minimum(1, (n - np.arange(n)) / (0.3 * SR))
        L *= env; R *= env
        pk = max(abs(L).max(), abs(R).max()) + 1e-9
        L = np.tanh(drive * L / pk); R = np.tanh(drive * R / pk)
        pk = max(abs(L).max(), abs(R).max()) + 1e-9
        st = np.stack([L, R], 1) * 0.89 / pk
        with wave.open(str(path), 'wb') as w:
            w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
            w.writeframes((st * 32767).astype(np.int16).tobytes())
        return path


def _hz(m): return 440 * 2 ** ((m - 69) / 12)
def _T(d): return np.arange(int(d * SR)) / SR


def sinos(path, n_states, hit1, hit2, cut=4 / 30, seed=7):
    """Bright bell/pluck arpeggios + cut-synced ticks, no bass (Bb major)."""
    mx = _Mix(n_states, cut, seed); rng = mx.rng; ct = mx.t

    def bell(f, dur=1.6, bright=1.0):
        t = _T(dur); idx = bright * 2.2 * np.exp(-t * 9)
        car = np.sin(2 * np.pi * f * t + np.sin(2 * np.pi * f * 3.5 * t) * idx)
        car += 0.25 * np.sin(2 * np.pi * f * 2.0 * t) * np.exp(-t * 6)
        return car * (1 - np.exp(-t * 900)) * np.exp(-t * 3.2)

    def pluck(f, dur=0.9):
        t = _T(dur)
        return sum(np.sin(2 * np.pi * f * k * t) * np.exp(-t * (7 + 5 * k)) / k for k in range(1, 6)) * (1 - np.exp(-t * 1500))

    def tick(level):
        t = _T(0.03)
        s = sosfilt(butter(2, [3500, 9000], 'band', fs=SR, output='sos'), rng.standard_normal(len(t)) * np.exp(-t * 400)) * 2.2
        return (s + 0.35 * np.sin(2 * np.pi * 2600 * t) * np.exp(-t * 250)) * level * 1.7

    def pad(freqs, dur):
        t = _T(dur)
        s = sum(np.sin(2 * np.pi * f * t) + 0.6 * np.sin(2 * np.pi * f * 1.003 * t + 1) for f in freqs)
        env = np.minimum(1, t / 0.35) * np.minimum(1, (dur - t) / 0.4).clip(0)
        return sosfilt(butter(2, 2200, 'low', fs=SR, output='sos'), s * env) / len(freqs)

    B4, C5, D5, Eb5, F5, G5, A5, Bb5, D6 = 70, 72, 74, 75, 77, 79, 81, 82, 86
    for k in range(1, hit1):
        mx.add(tick(0.55), ct[k], pan=rng.uniform(-0.4, 0.4))
    for j, m in enumerate([B4, C5, D5]):
        if 1 + 3 * j < hit1:
            mx.add(bell(_hz(m), 1.4, 0.8), ct[1 + 3 * j], pan=-0.3 + 0.3 * j, gain=0.5)
    for m, p in zip([B4, D5, F5, Bb5, D6], [-0.5, -0.2, 0.1, 0.35, 0.6]):
        mx.add(bell(_hz(m), 2.2, 1.0), ct[hit1], pan=p, gain=0.32)
    prog = [[Eb5, G5, Bb5, D6], [B4, D5, F5, Bb5], [G5 - 12, B4, D5, F5], [F5 - 12, A5 - 12, C5, F5]]
    pattern = [0, 2, 1, 3, 2, 1]
    start, end = hit1 + 1, hit2
    for step, k in enumerate(range(start, end, 2)):
        chord = prog[((k - start) // 12) % 4]
        m = chord[pattern[step % 6]] + (12 if step % 6 == 5 else 0)
        mx.add(pluck(_hz(m)), ct[k], pan=0.45 if step % 2 else -0.45, gain=0.42)
        mx.add(bell(_hz(m + 12), 0.7, 1.2), ct[k], pan=-0.2 if step % 2 else 0.2, gain=0.2)
    for k in range(start, end):
        mx.add(tick(0.22), ct[k], pan=rng.uniform(-0.6, 0.6))
    for i, k in enumerate(range(start, end, 12)):
        mx.add(pad([_hz(m - 12) for m in prog[i % 4]], min(12, end - k) * cut + 0.3), ct[k], gain=0.10)
    for k in range(hit2, n_states - 1):
        mx.add(tick(0.5), ct[k], pan=rng.uniform(-0.4, 0.4))
    for j, m in enumerate([Bb5, F5, D5]):
        if hit2 + 3 * j < n_states:
            mx.add(bell(_hz(m), 1.4, 0.8), ct[hit2 + 3 * j], pan=0.3 - 0.3 * j, gain=0.45)
    for m in (B4, F5, Bb5):
        mx.add(bell(_hz(m), 2.0, 0.6), ct[-1], gain=0.22)
    return mx.finish(path, reverb=0.32, hp_hz=220, drive=2.2)


def eletronica(path, n_states, hit1, hit2, cut=4 / 30, seed=5):
    """Tech/corporate electronic: four-on-the-floor kick locked to the cuts, hats, sidechained bass, chord stabs."""
    mx = _Mix(n_states, cut, seed); rng = mx.rng; ct = mx.t
    lp = lambda x, f: sosfilt(butter(2, f, 'low', fs=SR, output='sos'), x)
    hpf = lambda x, f: sosfilt(butter(2, f, 'high', fs=SR, output='sos'), x)
    saw = lambda f, t: 2 * ((f * t) % 1.0) - 1

    def kick():
        t = _T(0.45); f = 45 + 110 * np.exp(-t * 35)
        s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 7)
        return s + 0.3 * hpf(np.tanh(3 * s), 150) + hpf(rng.standard_normal(len(t)), 3000) * np.exp(-t * 200) * 0.15

    def hat(level=1.0, open_=False):
        t = _T(0.2 if open_ else 0.05)
        return hpf(rng.standard_normal(len(t)), 7000) * np.exp(-t * (18 if open_ else 90)) * level

    def clap():
        t = _T(0.25); nz = rng.standard_normal(len(t))
        env = sum(np.exp(-np.clip(t - d, 0, None) * 60) * (t >= d) for d in (0, 0.01, 0.02))
        return sosfilt(butter(2, [900, 5000], 'band', fs=SR, output='sos'), nz) * env * 0.6

    def stab(notes, dur=0.35):
        t = _T(dur)
        s = sum(saw(_hz(m) * d, t) for m in notes for d in (0.994, 1.0, 1.006))
        return lp(s, 2500) * np.exp(-t * 7) * (1 - np.exp(-t * 400)) / (3 * len(notes))

    def bass(m, dur):
        t = _T(dur)
        s = saw(_hz(m), t) + 0.5 * np.sin(2 * np.pi * _hz(m - 12) * t)
        duck = 1 - 0.85 * np.exp(-((t % (cut * 2)) / 0.06))  # sidechain to the kick
        return lp(s, 420) * duck * np.minimum(1, t / 0.01) * np.minimum(1, (dur - t) / 0.02).clip(0)

    def riser(dur):
        t = _T(dur); nz = rng.standard_normal(len(t))
        return hpf(nz, 2000) * (t / dur) ** 2.5 * 0.5

    A2, C3, E3, F2, G2, D3 = 45, 48, 52, 41, 43, 50
    prog = [(A2, [69, 72, 76]), (F2, [65, 69, 72]), (C3, [67, 72, 76]), (G2, [67, 71, 74])]
    # intro: ticking hats + riser
    for k in range(1, hit1):
        mx.add(hat(0.8), ct[k], pan=rng.uniform(-0.5, 0.5))
    if hit1 > 0:
        mx.add(riser(ct[hit1]), 0, gain=0.8)
    # reveal
    mx.add(kick(), ct[hit1], gain=1.0)
    mx.add(stab(prog[0][1] + [81], 0.8), ct[hit1], gain=2.0)
    mx.add(clap(), ct[hit1], gain=0.8)
    # groove
    start, end = hit1 + 1, hit2
    for k in range(start, end):
        i = k - start
        if i % 2 == 0:
            mx.add(kick(), ct[k], gain=0.55)
        mx.add(hat(1.1 if i % 2 else 0.6, open_=(i % 4 == 1)), ct[k], pan=0.3 if i % 2 else -0.3)
        if i % 4 == 2:
            mx.add(clap(), ct[k], gain=1.3)
        if i % 16 in (0, 3, 6, 10, 13):
            root, ch = prog[(i // 16) % 4]
            mx.add(stab(ch), ct[k], pan=rng.uniform(-0.4, 0.4), gain=1.6)
    for j, k in enumerate(range(start, end, 16)):
        root, _ = prog[j % 4]
        mx.add(bass(root, min(16, end - k) * cut), ct[k], gain=0.3)
    if hit2 - 8 > start:
        mx.add(riser(ct[hit2] - ct[hit2 - 8]), ct[hit2 - 8], gain=0.7)
    # outro
    mx.add(kick(), ct[hit2], gain=1.0)
    mx.add(stab(prog[0][1] + [81], 1.2), ct[hit2], gain=1.8)
    for k in range(hit2 + 1, n_states - 1):
        mx.add(hat(0.3 * (1 - (k - hit2) / max(1, n_states - hit2))), ct[k], pan=rng.uniform(-0.5, 0.5))
    return mx.finish(path, reverb=0.18, hp_hz=35, drive=1.4)


def trilha_do_usuario(src, path, dur, inicio=0.0, fade_out=0.4):
    """Cut the user's own track to the video length (optionally starting at `inicio` seconds), with fades."""
    import subprocess
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', str(inicio), '-i', str(src), '-t', f'{dur:.3f}',
                    '-af', f'afade=t=in:d=0.02,afade=t=out:st={max(0, dur - fade_out):.3f}:d={fade_out},loudnorm=I=-14:TP=-1',
                    '-ar', str(SR), '-ac', '2', str(path)], check=True)
    return path


ESTILOS = {'cinematica': cinematic, 'sinos': sinos, 'eletronica': eletronica}
