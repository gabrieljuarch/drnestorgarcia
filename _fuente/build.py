"""Genera el sitio del Dr. Néstor García en páginas separadas (una URL por sección).

Fuente:   _fuente/plantilla.html  (todo el sitio en un archivo, con rutas #/vista)
          _fuente/seo.json        (título, descripción y ruta de cada página)
          _fuente/img/*.jpg       (fotos originales)
Salida:   index.html, sobre-mi/index.html, … , 404.html, img/*.webp,
          sitemap.xml, robots.txt, .htaccess

Uso:      python3 _fuente/build.py
"""
import html
import json
import os
import re
import urllib.parse
from datetime import date

from PIL import Image

FUENTE = os.path.dirname(os.path.abspath(__file__))
SITIO = os.path.dirname(FUENTE)
cfg = json.load(open(os.path.join(FUENTE, 'seo.json'), encoding='utf-8'))
DOMINIO = cfg['dominio'].rstrip('/')
PAGINAS = cfg['paginas']
RUTA = {p['vista']: p['ruta'] for p in PAGINAS}
HOY = date.today().isoformat()

t = open(os.path.join(FUENTE, 'plantilla.html'), encoding='utf-8').read()


# ------------------------------------------------------------------
# 1. Imágenes: WebP en dos tamaños (800 px para celular y 1600 px)
# ------------------------------------------------------------------
TAM = {}
os.makedirs(os.path.join(SITIO, 'img'), exist_ok=True)
for f in sorted(os.listdir(os.path.join(FUENTE, 'img'))):
    if not f.endswith('.jpg'):
        continue
    nombre = f[:-4]
    im = Image.open(os.path.join(FUENTE, 'img', f)).convert('RGB')
    if nombre == 'og-image':                      # vista previa al compartir: se queda en JPG
        im.save(os.path.join(SITIO, 'img', 'og-image.jpg'), quality=82, optimize=True)
        continue
    grande = im.copy(); grande.thumbnail((1600, 1600))
    chica = im.copy(); chica.thumbnail((800, 800))
    grande.save(os.path.join(SITIO, 'img', nombre + '.webp'), quality=78, method=6)
    chica.save(os.path.join(SITIO, 'img', nombre + '-800.webp'), quality=76, method=6)
    TAM[nombre] = grande.size


def img_tag(m, pre):
    """Convierte <img src="img/x.jpg" …> en WebP con srcset, sizes y medidas."""
    contenedor, attrs, nombre, resto = m.group(1) or '', m.group(2), m.group(3), m.group(4)
    w, h = TAM[nombre]
    tamanos = '(max-width:680px) 100vw, 220px' if contenedor else '(max-width:1180px) 100vw, 50vw'
    out = (f'{contenedor}<img{attrs}src="{pre}img/{nombre}.webp" '
           f'srcset="{pre}img/{nombre}-800.webp 800w, {pre}img/{nombre}.webp {w}w" sizes="{tamanos}"{resto}')
    if 'width=' not in out:
        out = out[:-1] + f' width="{w}" height="{h}">'
    else:
        out = re.sub(r'width="\d+" height="\d+"', f'width="{w}" height="{h}"', out)
    return out


# ------------------------------------------------------------------
# 2. Partes comunes de la plantilla
# ------------------------------------------------------------------
head = t[:t.index('</head>')]
cuerpo_ini = t[t.index('<body'):t.index('<main id="main">') + len('<main id="main">')]
fin_main = t.index('</main>')
cola = t[fin_main:]
vistas_html = t[t.index('<main id="main">') + len('<main id="main">'):fin_main]

VISTAS = {}
for bloque in re.split(r'<!-- =+\n\s+VISTA[^\n]*\n\s+=+ -->', vistas_html):
    m = re.search(r'<section class="view" data-view="(\w+)"[^>]*>', bloque)
    if m:
        VISTAS[m.group(1)] = bloque.replace(m.group(0), f'<section class="view on" data-view="{m.group(1)}">').strip()

# Navegación: en lugar del enrutador por #/vista, cada archivo es una página
cola = re.sub(r'/\* -+ Navegación entre "páginas".*?window\.addEventListener\(\'hashchange\', route\);\n',
              '/* ---------- Página actual ---------- */\n'
              'function initPage(){ buildForms(document); observe(document); }\n',
              cola, flags=re.S)
cola = cola.replace('\nroute();\n</script>', '\ninitPage();\n</script>')
assert 'initPage();' in cola and 'hashchange' not in cola

# Iconos del sitio (archivo real para que Google lo muestre en los resultados)
icono = re.search(r'<link rel="icon" href="data:image/svg\+xml,([^"]+)">', head)
open(os.path.join(SITIO, 'favicon.svg'), 'w', encoding='utf-8').write(urllib.parse.unquote(icono.group(1)))


def enlaces(s, pre):
    """#/vista → ruta relativa real, y fotos con la ruta correcta."""
    def ruta(m):
        r = RUTA.get(m.group(1) or 'inicio', '')
        return f'href="{pre}{r + "/" if r else ""}"' if (pre or r) else 'href="./"'
    s = re.sub(r'href="#/(\w*)"', ruta, s)
    s = re.sub(r'(<div class="pimg">)?<img([^>]*?\s)src="img/([\w-]+)\.jpg"([^>]*>)', lambda m: img_tag(m, pre), s)
    return s


def aligerar(s):
    """Redondea a un decimal las coordenadas de los logotipos en SVG (pesan menos, se ven igual)."""
    def num(n):
        v = f'{float(n.group()):.1f}'.rstrip('0').rstrip('.')
        return '0' if v == '-0' else v
    return re.sub(r' d="([^"]+)"', lambda m: ' d="' + re.sub(r'-?\d+\.\d{2,}', num, m.group(1)) + '"', s)


def texto(s):
    return html.unescape(re.sub(r'<[^>]+>', '', s)).strip()


# ------------------------------------------------------------------
# 3. Datos estructurados (Schema.org)
# ------------------------------------------------------------------
MEDICO = {
    "@context": "https://schema.org",
    "@type": "Physician",
    "@id": DOMINIO + "/#consultorio",
    "name": "Dr. Néstor García · Cirujano plástico y reconstructivo",
    "alternateName": "Dr. Néstor Misael García Herrera",
    "description": "Cirujano plástico, estético y reconstructivo certificado por el CMCPER, especialista en lipoescultura y aumento mamario en León, Guanajuato.",
    "url": DOMINIO + "/",
    "image": DOMINIO + "/img/og-image.jpg",
    "logo": DOMINIO + "/apple-touch-icon.png",
    "telephone": "+52 477 765 3849",
    "email": "drnestorgarciacirugiaplastica@gmail.com",
    "medicalSpecialty": "PlasticSurgery",
    "address": {
        "@type": "PostalAddress",
        "streetAddress": "Calle del Prado 208, Jardines del Moral",
        "addressLocality": "León",
        "addressRegion": "Guanajuato",
        "postalCode": "37160",
        "addressCountry": "MX"
    },
    "geo": {"@type": "GeoCoordinates", "latitude": 21.1504566, "longitude": -101.6919248},
    "hasMap": "https://maps.app.goo.gl/Kqccn2uwh1JV8Kvp6",
    "openingHoursSpecification": [{
        "@type": "OpeningHoursSpecification",
        "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
        "opens": "09:30", "closes": "12:30"
    }],
    "areaServed": {"@type": "City", "name": "León, Guanajuato"},
    "paymentAccepted": "Efectivo, transferencia, tarjeta de crédito",
    "sameAs": [
        "https://www.instagram.com/dr.nestor_cirugiaplastica/",
        "https://www.facebook.com/profile.php?id=61572596087909"
    ]
}


def jsonld(obj):
    return '<script type="application/ld+json">' + json.dumps(obj, ensure_ascii=False) + '</script>'


def faq_schema(vista_html):
    preguntas = re.findall(r'<summary>(.*?)</summary><div class="ans">(.*?)</div>', vista_html, flags=re.S)
    if not preguntas:
        return ''
    return jsonld({
        "@context": "https://schema.org", "@type": "FAQPage",
        "mainEntity": [{"@type": "Question", "name": texto(q),
                        "acceptedAnswer": {"@type": "Answer", "text": texto(a)}} for q, a in preguntas]
    })


# ------------------------------------------------------------------
# 4. Encabezado <head> de cada página
# ------------------------------------------------------------------
def head_pagina(p, pre, url, indexar, extra=''):
    h = head
    h = re.sub(r'<title>.*?</title>', f'<title>{html.escape(p["titulo"], quote=False)}</title>', h)
    h = re.sub(r'<meta name="description" content="[^"]*">',
               f'<meta name="description" content="{html.escape(p["descripcion"])}">', h)
    h = re.sub(r'<meta name="keywords"[^>]*>\n', '', h)
    h = re.sub(r'<link rel="canonical"[^\n]*\n',
               (f'<link rel="canonical" href="{url}">\n' if indexar else '') +
               f'<meta name="robots" content="{"index, follow, max-image-preview:large" if indexar else "noindex, follow"}">\n', h)
    h = re.sub(r'<meta property="og:title" content="[^"]*">',
               f'<meta property="og:title" content="{html.escape(p["titulo"])}">\n'
               f'<meta property="og:url" content="{url}">\n'
               f'<meta property="og:site_name" content="Dr. Néstor García · Cirujano plástico">', h)
    h = re.sub(r'<meta property="og:description" content="[^"]*">',
               f'<meta property="og:description" content="{html.escape(p["descripcion"])}">', h)
    h = re.sub(r'<meta property="og:image" content="[^"]*">',
               f'<meta property="og:image" content="{DOMINIO}/img/og-image.jpg">\n'
               f'<meta name="twitter:card" content="summary_large_image">', h)
    h = re.sub(r'<link rel="icon" href="data:[^"]+">',
               f'<link rel="icon" href="{pre}favicon.svg" type="image/svg+xml">\n'
               f'<link rel="icon" href="{pre}favicon-48.png" sizes="48x48" type="image/png">\n'
               f'<link rel="apple-touch-icon" href="{pre}apple-touch-icon.png">', h)
    h = h.replace('     Un solo archivo: HTML + CSS + JS. Las fotos viven en /img.\n',
                  '     Archivo generado con _fuente/build.py: los cambios se hacen en\n'
                  '     _fuente/plantilla.html y _fuente/seo.json, no aquí.\n')
    return h + extra + jsonld(MEDICO) + '\n</head>\n'


# ------------------------------------------------------------------
# 5. Páginas
# ------------------------------------------------------------------
REDIRECCION_HASH = ('<script>/* enlaces antiguos (#/vista) → página nueva */'
                    '(function(){var r=' + json.dumps({k: v for k, v in RUTA.items() if v}) +
                    ',h=location.hash.replace("#/","");if(location.hash.indexOf("#/")===0&&r[h])location.replace(r[h]+"/");})();</script>\n')

for p in PAGINAS:
    v = p['vista']
    pre = '../' if p['ruta'] else ''
    url = DOMINIO + '/' + (p['ruta'] + '/' if p['ruta'] else '')
    extra = ''
    if v == 'inicio':
        extra = (f'<link rel="preload" as="image" href="img/hero-doctor.webp" '
                 f'imagesrcset="img/hero-doctor-800.webp 800w, img/hero-doctor.webp {TAM["hero-doctor"][0]}w" '
                 f'imagesizes="(max-width:1180px) 100vw, 50vw" fetchpriority="high">\n' + REDIRECCION_HASH)
    if v == 'preguntas':
        extra += faq_schema(VISTAS[v]) + '\n'
    ini = cuerpo_ini.replace(f'data-nav="{v}">', f'data-nav="{v}" class="active" aria-current="page">')
    pagina = head_pagina(p, pre, url, p['indexar'], extra) + '\n' + enlaces(ini + '\n\n' + VISTAS[v] + '\n\n' + cola, pre)
    destino = os.path.join(SITIO, p['ruta'], 'index.html') if p['ruta'] else os.path.join(SITIO, 'index.html')
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    open(destino, 'w', encoding='utf-8').write(aligerar(pagina))

# Página 404 (rutas absolutas porque se muestra en cualquier dirección)
p404 = {"titulo": "Página no encontrada | Dr. Néstor García",
        "descripcion": "La página que buscas no existe. Vuelve al inicio del sitio del Dr. Néstor García."}
vista404 = '''<section class="view on" data-view="404">
  <div class="page-hero page-hero--compact">
    <div class="ph-txt">
      <div class="kicker">Error 404</div>
      <h1>Esta página no existe</h1>
      <p class="lead">Es posible que la dirección esté mal escrita o que la página se haya movido. Desde el inicio puedes encontrar todo sobre mis procedimientos.</p>
      <p style="margin-top:34px"><a class="btn" href="/">Volver al inicio</a></p>
    </div>
    <div class="ph-img"><img src="img/contacto.jpg" alt="Dr. Néstor García, cirujano plástico en León" style="object-position:50% 15%"></div>
  </div>
</section>'''
ini404 = re.sub(r'<div id="loader".*?</div>\n</div>\n', '', cuerpo_ini, flags=re.S).replace('<body class="loading">', '<body class="loaded">')
pagina404 = head_pagina(p404, '/', DOMINIO + '/404.html', False) + '\n' + enlaces(ini404 + '\n\n' + vista404 + '\n\n' + cola, '/')
open(os.path.join(SITIO, '404.html'), 'w', encoding='utf-8').write(aligerar(pagina404))

# ------------------------------------------------------------------
# 6. sitemap.xml, robots.txt y .htaccess
# ------------------------------------------------------------------
urls = ''.join(
    f'  <url><loc>{DOMINIO}/{p["ruta"] + "/" if p["ruta"] else ""}</loc><lastmod>{HOY}</lastmod>'
    f'<priority>{p["prioridad"]}</priority></url>\n' for p in PAGINAS if p['indexar'])
open(os.path.join(SITIO, 'sitemap.xml'), 'w', encoding='utf-8').write(
    '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + urls + '</urlset>\n')

open(os.path.join(SITIO, 'robots.txt'), 'w', encoding='utf-8').write(
    f'User-agent: *\nAllow: /\nDisallow: /_fuente/\n\nSitemap: {DOMINIO}/sitemap.xml\n')

host = DOMINIO.split('://')[1]
open(os.path.join(SITIO, '.htaccess'), 'w', encoding='utf-8').write(f'''# Servidor Hostinger (Apache/LiteSpeed)
Options -Indexes
RewriteEngine On

# Forzar HTTPS y versión sin www (versión canónica: https://{host})
RewriteCond %{{HTTPS}} off [OR]
RewriteCond %{{HTTP_HOST}} ^www\\. [NC]
RewriteRule ^(.*)$ https://{host}/$1 [L,R=301]

# Archivos de trabajo que no deben verse en internet
RewriteRule ^(_fuente|\\.git)(/|$) - [F,L]

# Página de error personalizada
ErrorDocument 404 /404.html

# Compresión
<IfModule mod_deflate.c>
  AddOutputFilterByType DEFLATE text/html text/css text/plain application/javascript application/json application/xml image/svg+xml
</IfModule>

# Caché del navegador (las fotos cambian de nombre cuando se reemplazan)
<IfModule mod_expires.c>
  ExpiresActive On
  ExpiresByType image/webp "access plus 1 month"
  ExpiresByType image/jpeg "access plus 1 month"
  ExpiresByType image/png "access plus 1 month"
  ExpiresByType image/svg+xml "access plus 1 month"
  ExpiresByType text/html "access plus 0 seconds"
</IfModule>
''')

print('Sitio generado:', len(PAGINAS), 'páginas + 404 ·', len(TAM), 'fotos en WebP')
