# Brand Mockup

<p align="center">
  <picture>
    <source media="(max-width: 767px)" srcset="docs/demo-9x16.gif">
    <img src="docs/demo-16x9.gif" alt="Exemplo gerado para a TGL Solutions">
  </picture>
</p>
<p align="center"><sub>Exemplo gerado para a TGL Solutions: 16:9 no desktop, 9:16 no celular. O GIF é mudo — o vídeo final sai em MP4 com trilha.</sub></p>

Gera um vídeo **brand reveal em stop-motion** para qualquer marca:
construção geométrica do símbolo → revelação → ~35 cortes rápidos de mockups fotográficos
com o logo **travado no centro e sempre do mesmo tamanho** → construção ao contrário.
Trilha cinemática original sintetizada e sincronizada com os cortes.

Formatos: `9x16` (Reels/Shorts/TikTok), `16x9` (YouTube), `1x1`, `4x5`.

## Instalação
```
pip install -r requirements.txt
```
Também precisa do **ffmpeg** no PATH. No Windows, o pycairo/cairosvg precisam do GTK/cairo;
o jeito mais simples é rodar no WSL ou num Linux/macOS.

## Uso
```
python make.py --brand brands/tgl/brand.json --formato 9x16
python make.py --brand brands/tgl/brand.json --formato 16x9
```
Liste os mockups disponíveis com `python make.py --listar`.

Saída em `saida/<marca>/<formato>/`: o MP4, `prancha.jpg` (todos os quadros, para conferir)
e `creditos.txt` (fotos usadas). Os quadros ficam em cache (`quadros/`); use `--refazer`
para forçar, ou `--so-quadros mug phone` para testar só alguns.

## Nova marca (tudo escolhido pelo usuário)
Crie `brands/<marca>/` com o **logo em SVG** (só o símbolo) e um `brand.json`:
```json
{
  "nome": "Minha Marca",
  "logo": "logo.svg",
  "cores": { "primary": "#E4572E", "dark": "#1B0F0B", "light": "#FFB59E" },
  "musica": { "estilo": "eletronica" },
  "direcao": {
    "categorias": ["digital", "merch"],
    "mockups": [],
    "excluir": ["neon"],
    "quantidade": 12,
    "tom": "misto",
    "ordem": "alternada",
    "graficos": true,
    "graficos_a_cada": 3,
    "abertura": true,
    "fechamento": true,
    "ritmo": 4
  }
}
```

**Cores** — só `primary` é obrigatória; `dark`, `light`, `background`, `lockup_lines`, `glow_a`, `glow_b` são derivadas se faltarem.

**Música** (`musica.estilo`):
| estilo | como é |
|---|---|
| `cinematica` | drone, risers, impactos graves na revelação e no fim, pulso crescente |
| `sinos` | sinos e pluck agudos, sem grave, ticks em cada corte (leve/elegante) |
| `eletronica` | batida four-on-the-floor presa aos cortes, hi-hats, baixo com sidechain, stabs |
| `arquivo` | música do usuário: `{"estilo": "arquivo", "arquivo": "minha.mp3", "inicio": 12.5}` (corta no tamanho do vídeo, fade e normaliza a -14 LUFS) |
| `nenhuma` | sem áudio (para colocar música dentro do Instagram) |

As trilhas sintetizadas são originais e se ajustam sozinhas à duração e aos cortes.

**Direção de mockups** (`direcao`):
| campo | opções |
|---|---|
| `categorias` | qualquer combinação de `digital`, `papelaria`, `merch`, `ambiente` |
| `mockups` | lista exata de mockups (ignora `categorias`); veja `python make.py --listar` |
| `excluir` | mockups a tirar |
| `quantidade` | quantos mockups usar |
| `tom` | `misto`, `claro` (fundos claros) ou `escuro` (fundos escuros) |
| `ordem` | `alternada` (claro/escuro), `aleatoria` (use `semente` para variar) ou `lista` |
| `graficos` / `graficos_a_cada` | intercala quadros gráficos (logo no preto, cromado, pôster...) a cada N mockups |
| `abertura` / `fechamento` | construção geométrica no início / de volta no fim |
| `ritmo` | frames (a 30fps) por quadro: `3` rápido, `4` padrão, `6` calmo |

A duração sai da quantidade × ritmo (ex.: 25 mockups, gráficos, abertura e fechamento, ritmo 4 ≈ 7,7s).
Para controle total, `sequencia` (lista de quadros) substitui a `direcao`.

**Construção (opcional)** — `construcao` (elipses/retângulos/linhas em coordenadas normalizadas do logo:
origem no canto superior esquerdo, unidade = altura do logo) e `grid` deixam a abertura fiel ao desenho
do símbolo; sem eles, a construção é automática. Exemplo completo em `brands/tgl/brand.json`.

`brands/exemplo/` é uma marca fictícia para teste (direção digital+merch, ritmo rápido, música eletrônica).

## Biblioteca de mockups (`library/`)
`library/mockups.json` descreve cada foto — isso **não depende da marca**:

| campo | significado |
|---|---|
| `file` | foto em `library/fotos/` |
| `anchor` | ponto da foto (px) onde o centro do logo vai ficar |
| `ls` | altura do logo na foto (px) |
| `rot` | graus para nivelar objetos inclinados |
| `16x9` / `1x1` / `4x5` | sobrescreve `anchor`/`ls` naquele formato |
| `erase` | limpezas antes de aplicar (texto/logo existente na foto) |
| `categoria` | `digital`, `papelaria`, `merch` ou `ambiente` (usado na direção) |
| `tom` | brilho médio da foto 0–1 (claro ≥ 0,5), usado para alternar claro/escuro |
| `material` | como o logo é aplicado: `ink`, `embroidery`, `screenprint`, `foil`, `seal`, `patch`, `glass`, `neon`, `screen_phone`, `screen_color`, `screen_watch` |

### Adicionar uma foto nova
1. Foto **frontal**, objeto em branco, alta resolução (Unsplash funciona; guarde o crédito).
2. Coloque em `library/fotos/` e adicione uma entrada em `mockups.json` com `anchor`, `ls` e `material`.
3. Teste: `python make.py --brand brands/tgl/brand.json --so-quadros <nome>` e confira o PNG em `saida/`.
4. Inclua o nome em `sequencia` (no brand.json) ou em `DEFAULT_SEQUENCE` (make.py).

Evite fotos em perspectiva forte: o logo nunca é distorcido (é o que mantém ele "parado").

## Estrutura
```
make.py                 CLI
brandmockup/core.py     formatos, cores e helpers de desenho
brandmockup/logo.py     logo a partir do SVG
brandmockup/graphics.py quadros gráficos (construção, grid, lockup, cromado...)
brandmockup/photos.py   mockups fotográficos e materiais
brandmockup/audio.py    trilhas (cinematica, sinos, eletronica, arquivo do usuário)
library/                fotos + mockups.json
brands/                 uma pasta por marca
```

## Licença das fotos
Fotos do Unsplash (Unsplash License: uso comercial livre, crédito não obrigatório; não é
permitido redistribuí-las como coleção). **Mantenha este repositório privado.**
