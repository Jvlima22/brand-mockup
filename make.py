#!/usr/bin/env python3
"""Brand Mockup — gera o vídeo brand reveal (stop-motion) de uma marca.

Uso:
  python make.py --brand brands/tgl/brand.json --formato 9x16
  python make.py --brand brands/tgl/brand.json --formato 16x9 --saida saida/
Formatos: 9x16, 16x9, 1x1, 4x5
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from brandmockup import core, logo, graphics, photos  # noqa: E402
from brandmockup.audio import ESTILOS, trilha_do_usuario  # noqa: E402
import random  # noqa: E402

# Default sequence: 58 states x 4 frames @30fps = 7.73s.
# Construction (0-9) -> reveal 'lockup' (10) -> mockups/graphics (11-47) -> reverse construction (48-57).
DEFAULT_SEQUENCE = [
    'blank', 'c1', 'c2', 'c3', 'c4', 'c5', 'c6', 'synth', 'grid', 'map',
    'lockup', 'mark_dark_on_light', 'silver', 'mark_white_on_black',
    'phone', 'laptop', 'book', 'color', 'app', 'watch', 'blackglow', 'stationery', 'envelope', 'card',
    'credit', 'badge', 'fleece', 'coffee', 'cap', 'tote', 'emboss', 'pin', 'lockup', 'keychain', 'mug',
    'bottle', 'poster', 'notebook', 'color', 'sticker', 'box', 'mark_white_on_black', 'acrylic', 'neon',
    'billboard', 'glass', 'mark_primary', 'silver',
    'map', 'grid', 'synth', 'c6', 'c5', 'c4', 'c3', 'c2', 'c1', 'blank',
]

ABERTURA = ['blank', 'c1', 'c2', 'c3', 'c4', 'c5', 'c6', 'synth', 'grid', 'map']
FECHAMENTO = ['map', 'grid', 'synth', 'c6', 'c5', 'c4', 'c3', 'c2', 'c1', 'blank']
GRAFICOS_CLAROS = ['mark_dark_on_light', 'silver', 'app', 'lockup', 'mark_primary']
GRAFICOS_ESCUROS = ['mark_white_on_black', 'color', 'blackglow', 'poster']
CATEGORIAS = ['digital', 'papelaria', 'merch', 'ambiente']


def montar_sequencia(d, manifest):
    """Build the state list from the user's direction (brand.json -> "direcao")."""
    if d.get('mockups'):
        pool = [m for m in d['mockups'] if m in manifest]
    else:
        cats = d.get('categorias') or CATEGORIAS
        pool = [k for k, e in manifest.items() if e.get('categoria') in cats]
    pool = [m for m in pool if m not in set(d.get('excluir', []))]
    tom = d.get('tom', 'misto')
    if tom == 'claro':
        pool = [m for m in pool if manifest[m].get('tom', 0.5) >= 0.45]
    elif tom == 'escuro':
        pool = [m for m in pool if manifest[m].get('tom', 0.5) < 0.6]
    rnd = random.Random(d.get('semente', 7))
    ordem = d.get('ordem', 'alternada')
    if ordem == 'aleatoria':
        rnd.shuffle(pool)
    elif ordem == 'alternada':
        claros = sorted([m for m in pool if manifest[m].get('tom', 0.5) >= 0.5], key=lambda _: rnd.random())
        escuros = sorted([m for m in pool if manifest[m].get('tom', 0.5) < 0.5], key=lambda _: rnd.random())
        pool = []
        while claros or escuros:
            for lst in (claros, escuros):
                if lst:
                    pool.append(lst.pop())
    q = d.get('quantidade')
    if q:
        pool = pool[:int(q)]
    if not pool:
        sys.exit('nenhum mockup sobrou com essa direção (categorias/tom/excluir)')

    corpo = []
    graf = d.get('graficos', True)
    gc = [g for g in GRAFICOS_CLAROS if tom != 'escuro']
    ge = [g for g in GRAFICOS_ESCUROS if tom != 'claro']
    gi = 0
    every = max(2, int(d.get('graficos_a_cada', 3)))
    for i, m in enumerate(pool):
        corpo.append(m)
        if graf and (i + 1) % every == 0 and i < len(pool) - 1:
            opts = (ge if manifest[m].get('tom', 0.5) >= 0.5 else gc) or gc or ge
            if opts:
                corpo.append(opts[gi % len(opts)]); gi += 1
    abertura = ABERTURA if d.get('abertura', True) else []
    fechamento = FECHAMENTO if d.get('fechamento', True) else ['lockup']
    inicio = ['lockup'] + (['mark_dark_on_light'] if graf and tom != 'escuro' else [])
    return abertura + inicio + corpo + fechamento


def listar(manifest):
    for c in CATEGORIAS:
        itens = [f"{k} ({'claro' if e.get('tom', .5) >= .5 else 'escuro'})" for k, e in manifest.items() if e.get('categoria') == c]
        print(f'{c:10s} {len(itens):2d}: ' + ', '.join(itens))
    print('gráficos: ' + ', '.join(sorted(graphics.SCENES)))


DEFAULT_COLORS = {'background': '#FDFAFE', 'black': '#020203', 'white': '#F5F6F8'}


def mix(a, b, t):
    a, b = core.hexc(a), core.hexc(b)
    c = np.clip(a * (1 - t) + b * t, 0, 1)
    return '#' + ''.join(f'{int(round(v * 255)):02X}' for v in c)


def load_brand(path):
    b = json.loads(Path(path).read_text(encoding='utf-8'))
    c = dict(DEFAULT_COLORS)
    c.update(b.get('cores', {}))
    if 'primary' not in c:
        sys.exit('brand.json precisa de cores.primary')
    c.setdefault('dark', mix(c['primary'], '#000000', 0.8))
    c.setdefault('light', mix(c['primary'], '#FFFFFF', 0.5))
    c.setdefault('lockup_lines', mix(c['light'], c['background'], 0.55))
    c.setdefault('glow_a', mix(c['light'], '#FFFFFF', 0.2))
    c.setdefault('glow_b', mix(c['primary'], '#3399FF', 0.3))
    b['cores'] = c
    b['_dir'] = Path(path).resolve().parent
    return b


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--brand')
    ap.add_argument('--listar', action='store_true', help='mostra os mockups disponíveis por categoria')
    ap.add_argument('--formato', default='9x16', choices=list(core.FORMATS))
    ap.add_argument('--biblioteca', default=str(ROOT / 'library'))
    ap.add_argument('--saida', default=None)
    ap.add_argument('--so-quadros', nargs='*', help='renderiza só estes quadros (para testar)')
    ap.add_argument('--refazer', action='store_true', help='ignora o cache de quadros')
    args = ap.parse_args()

    if args.listar:
        listar(json.loads((Path(args.biblioteca) / 'mockups.json').read_text(encoding='utf-8')))
        return
    if not args.brand:
        sys.exit('informe --brand')
    brand = load_brand(args.brand)
    slug = Path(args.brand).resolve().parent.name
    out = Path(args.saida or ROOT / 'saida' / slug) / args.formato
    cache = out / 'quadros'
    cache.mkdir(parents=True, exist_ok=True)

    core.configure(args.formato, brand['cores'])
    logo.load(brand['_dir'] / brand['logo'])
    graphics.set_guides(brand.get('construcao'), brand.get('grid'))
    lib = Path(args.biblioteca)
    photos.LIB_DIR = lib
    manifest = json.loads((lib / 'mockups.json').read_text(encoding='utf-8'))

    direcao = brand.get('direcao', {})
    seq = brand.get('sequencia') or (montar_sequencia(direcao, manifest) if direcao else DEFAULT_SEQUENCE)
    ritmo = int(direcao.get('ritmo', 4))  # frames (a 30fps) por quadro: 3 = rápido, 4 = padrão, 6 = calmo
    cut = ritmo / 30
    print(f'{len(seq)} quadros, {len(seq) * cut:.1f}s')
    unknown = [n for n in seq if n not in graphics.SCENES and n not in manifest]
    if unknown:
        sys.exit(f'quadros desconhecidos na sequência: {unknown}')

    names = args.so_quadros or sorted(set(seq))
    for n in names:
        p = cache / f'{n}.png'
        if p.exists() and not args.refazer:
            continue
        if n in graphics.SCENES:
            img = graphics.SCENES[n]()
            if n in graphics.GRAIN:
                core.grain(img, 0.01)
        else:
            img = photos.render(manifest[n])
        core.save(img, p)
        print('quadro', n, flush=True)
    if args.so_quadros:
        return

    # frames in order
    seqdir = out / 'seq'
    shutil.rmtree(seqdir, ignore_errors=True); seqdir.mkdir()
    for i, n in enumerate(seq):
        shutil.copyfile(cache / f'{n}.png', seqdir / f'{i:03d}.png')

    # music
    musica = brand.get('musica') or {'estilo': {'cinematic': 'cinematica', 'none': 'nenhuma'}.get(brand.get('audio', 'cinematica'), brand.get('audio', 'cinematica'))}
    if isinstance(musica, str):
        musica = {'estilo': musica}
    estilo = musica.get('estilo', 'cinematica')
    wav = None
    hit1 = seq.index('lockup')
    tail = [i for i, n in enumerate(seq) if n == 'map' and i > hit1]
    hit2 = tail[-1] if tail else len(seq) - 1
    if estilo in ESTILOS:
        wav = ESTILOS[estilo](out / 'trilha.wav', len(seq), hit1, hit2, cut=cut)
    elif estilo == 'arquivo':
        wav = trilha_do_usuario((brand['_dir'] / musica['arquivo']).resolve(), out / 'trilha.wav',
                                len(seq) * cut, inicio=musica.get('inicio', 0))
    elif estilo != 'nenhuma':
        sys.exit(f'estilo de música desconhecido: {estilo}')

    mp4 = out / f"{slug}_brand_mockup_{args.formato}.mp4"
    cmd = ['ffmpeg', '-v', 'error', '-y', '-framerate', f'{30 / ritmo:.4f}', '-i', str(seqdir / '%03d.png')]
    if wav:
        cmd += ['-i', str(wav)]
    cmd += ['-vf', 'fps=30,format=yuv420p', '-c:v', 'libx264', '-preset', 'slow', '-crf', '14']
    if wav:
        cmd += ['-c:a', 'aac', '-b:a', '256k', '-shortest']
    cmd += ['-movflags', '+faststart', str(mp4)]
    subprocess.run(cmd, check=True)

    # contact sheet with centre crosshair (quality check) + photo credits
    tiles = [Image.open(seqdir / f'{i:03d}.png') for i in range(len(seq))]
    tw = 200 if core.ctx.H > core.ctx.W else 320
    th = int(tw * core.ctx.H / core.ctx.W)
    cols = 10 if core.ctx.H > core.ctx.W else 6
    sheet = Image.new('RGB', (cols * tw, ((len(tiles) + cols - 1) // cols) * th), 'white')
    for i, t in enumerate(tiles):
        sheet.paste(t.resize((tw, th), Image.LANCZOS), ((i % cols) * tw, (i // cols) * th))
    sheet.save(out / 'prancha.jpg', quality=88)
    used = [n for n in dict.fromkeys(seq) if n in manifest]
    lines = ['Fotos (Unsplash License — uso comercial livre, crédito não obrigatório):', '']
    lines += [f"- {n}: {manifest[n]['credit']['autor']} — {manifest[n]['credit']['link']}" for n in used]
    (out / 'creditos.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('OK', mp4)


if __name__ == '__main__':
    main()
