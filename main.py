import os
import time
import requests
import feedparser
import pytz
import re
import urllib3
import json
import io
from datetime import datetime, timedelta
from ntscraper import Nitter
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from urllib.parse import unquote
from PIL import Image, ImageDraw, ImageFont

# 1. OPTIMIZACIÓN DE RED
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
ua = UserAgent()

# --- CONFIGURACIÓN ---
TOKEN = os.environ.get('TELEGRAM_TOKEN')
ID_GRUPO = os.environ.get('TELEGRAM_CHAT_ID') 
ID_CANAL = os.environ.get('TELEGRAM_CHANNEL_ID') 
DESTINATARIOS = [id_ for id_ in [ID_GRUPO, ID_CANAL] if id_]

RSS_URL = "https://news.google.com/rss/search?q=Metro+CDMX+retraso+OR+falla+OR+caos+when:1h&hl=es-419&gl=MX&ceid=MX:es-419"

# --- DICCIONARIOS DE INTELIGENCIA ---
CAUSAS = {
    "retraso": "Retraso", "lento": "Marcha Lenta", "lenta": "Marcha Lenta",
    "falla": "Falla Técnica", "avería": "Avería", "desalojo": "Desalojo",
    "humo": "Humo", "fuego": "Conato Incendio", "quemado": "Olor Quemado",
    "zapatas": "Zapatas", "lluvia": "Lluvia", "mojado": "Lluvia", 
    "caos": "Aglomeración", "colapso": "Colapso", "espera": "Espera Alta", 
    "detenido": "Detenido", "suicida": "Persona en Vías", "arrollado": "Accidente",
    "corte": "Sin Energía", "bloqueo": "Bloqueo", "cerrada": "Cerrada",
    "sin servicio": "Sin Servicio"
}

PALABRAS_CLAVE = list(CAUSAS.keys()) + ["afectaciones", "avance", "servicio", "estaciones"]
PALABRAS_SOLUCION = ["restablece", "normal", "agiliza", "solucionado", "continuo", "reanuda", "opera con normalidad"]
IGNORAR = ["buenos días", "cubrebocas", "tarjeta", "arte", "exposición", "domingos y días festivos", "cultura", "museo", "simulacro"]
FIRMA = "\n\n— 🤖 <i>JJMex Bot</i>"

# Diseño: Colores Material Design / Metro Oficiales
COLORES = {
    "1": "#F04E98", "2": "#0057B8", "3": "#6D8D23", 
    "4": "#6FB19C", "5": "#FFCD00", "6": "#DB2228", 
    "7": "#E46F23", "8": "#009A44", "9": "#5B3A29", 
    "A": "#9F258F", "B": "#B0B3B2", "12": "#C19C2D",
    "BG": "#121417", "CARD": "#1E2329", "TEXT": "#FFFFFF", "SUBTEXT": "#9CA3AF",
    "ALERT_BG": "#3B1E1E", "ALERT_BORDER": "#EF4444", "OK_TEXT": "#34D399", "ALERT_TEXT": "#F87171"
}

# Líneas que requieren texto NEGRO por ser muy claras (Amarilla, Verde agua, Verde 8, Gris, Dorada)
LINEAS_CLARAS = ["4", "5", "8", "B", "12"]

MAPA_LINEAS = {
    "1": "L1", "uno": "L1", "rosa": "L1",
    "2": "L2", "dos": "L2", "azul": "L2",
    "3": "L3", "tres": "L3", "verde": "L3",
    "4": "L4", "cuatro": "L4", "cian": "L4",
    "5": "L5", "cinco": "L5", "amarilla": "L5",
    "6": "L6", "seis": "L6", "roja": "L6",
    "7": "L7", "siete": "L7", "naranja": "L7",
    "8": "L8", "ocho": "L8", 
    "9": "L9", "nueve": "L9", "café": "L9",
    "a": "LA", "férrea": "LA",
    "b": "LB", "gris": "LB",
    "12": "L12", "doce": "L12", "dorada": "L12"
}

def get_headers():
    return {'User-Agent': ua.random, 'Referer': 'https://news.google.com/'}

# --- MOTOR GRÁFICO HD (SUPER SAMPLING) ---
def descargar_fuente():
    try:
        url = "https://github.com/google/fonts/raw/main/apache/robotoslab/RobotoSlab-Bold.ttf" 
        return io.BytesIO(requests.get(url).content)
    except: return None

def dibujar_tarjeta_hd(draw, x, y, w, h, linea, estado, color_linea, f_linea, f_estado):
    """Dibuja una tarjeta en alta resolución con AJUSTE DE PROPORCIÓN"""
    # 1. Fondo de la tarjeta
    es_alerta = estado != "Normal"
    bg_color = COLORES["ALERT_BG"] if es_alerta else COLORES["CARD"]
    border_color = COLORES["ALERT_BORDER"] if es_alerta else "#2A3038"
    border_width = 6 if es_alerta else 2
    
    draw.rounded_rectangle([x, y, x+w, y+h], radius=24, fill=bg_color, outline=border_color, width=border_width)
    
    # 2. Icono de Línea (CÍRCULO)
    # Ajustamos el tamaño: Que sea grande pero deje aire
    padding_y = 20
    circle_size = h - (padding_y * 2) 
    
    cy = y + (h // 2)
    cx = x + 40 + (circle_size // 2) # Margen izquierdo fijo de 40px + radio
    
    x1, y1 = cx - (circle_size//2), cy - (circle_size//2)
    x2, y2 = cx + (circle_size//2), cy + (circle_size//2)
    
    draw.ellipse([x1, y1, x2, y2], fill=color_linea)
    
    # 3. Texto del Número de Línea (VISIBILIDAD EXTREMA)
    texto_num = linea.replace("L", "")
    color_num = "black" if texto_num in LINEAS_CLARAS else "white"
    
    # Centrado matemático
    bbox = f_linea.getbbox(texto_num)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    
    # Ajuste vertical fino (las fuentes suelen tener baseline variable)
    offset_y = 8 if texto_num in ["A", "B", "12"] else 5
    tx = cx - (tw / 2)
    ty = cy - (th / 2) - offset_y
    
    draw.text((tx, ty), texto_num, font=f_linea, fill=color_num)
    
    # 4. Texto de Estado
    text_x = x2 + 40 # Espacio generoso después del círculo
    text_y = cy - 20 # Centrado vertical visual
    
    color_status = COLORES["ALERT_TEXT"] if es_alerta else COLORES["OK_TEXT"]
    # Truncar texto si es muy largo
    estado_fmt = estado.upper() if len(estado) < 13 else estado[:13] + "."
    
    draw.text((text_x, text_y), estado_fmt, font=f_estado, fill=color_status)

def generar_tablero_visual(afectaciones):
    """Genera dashboard 2X para nitidez extrema - CORREGIDO"""
    # Dimensiones AUMENTADAS para evitar cortes
    # Antes H=1100 (muy poco), Ahora H=1400 (suficiente para 6 filas)
    W, H = 1600, 1400 
    
    img = Image.new('RGB', (W, H), color=COLORES["BG"])
    draw = ImageDraw.Draw(img)
    
    fb = descargar_fuente()
    try:
        f_title = ImageFont.truetype(fb, 75)
        # Fuente del número optimizada para no salirse del círculo
        f_line = ImageFont.truetype(fb, 80) 
        f_status = ImageFont.truetype(fb, 42)
        f_sub = ImageFont.truetype(fb, 32)
    except:
        f_title = f_line = f_status = f_sub = ImageFont.load_default()

    # Header
    now = datetime.now(pytz.timezone('America/Mexico_City'))
    draw.text((60, 60), "ESTADO DEL SERVICIO", font=f_title, fill="white")
    draw.text((60, 150), f"Actualización: {now.strftime('%I:%M %p • %d %b')}", font=f_sub, fill=COLORES["SUBTEXT"])
    
    # Línea divisoria
    draw.line([(60, 200), (W-60, 200)], fill="#333", width=3)

    # Grid Config
    lineas = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "A", "B", "12"]
    cols = 2
    
    # Coordenadas de inicio (debajo de la línea)
    start_x = 60
    start_y = 240
    
    # Cálculos de dimensiones de tarjeta
    gap_x = 40
    gap_y = 30
    
    # Ancho de tarjeta: (Ancho total - márgenes - espacio central) / 2
    card_w = (W - (start_x*2) - gap_x) // 2
    card_h = 150 # Altura cómoda

    for i, l_key in enumerate(lineas):
        col = i % cols
        row = i // cols
        
        x = start_x + (col * (card_w + gap_x))
        y = start_y + (row * (card_h + gap_y))
        
        l_name = f"L{l_key}"
        estado = afectaciones.get(l_name, "Normal")
        
        dibujar_tarjeta_hd(draw, x, y, card_w, card_h, l_key, estado, COLORES[l_key], f_line, f_status)

    # Footer
    draw.text((W-350, H-70), "JJMex Intelligence", font=f_sub, fill=COLORES["SUBTEXT"])
    
    # 5. RESAMPLING (Reducción de calidad cinematográfica)
    # Reducimos a la mitad exacta para máxima nitidez (800x700)
    img_final = img.resize((800, 700), resample=Image.Resampling.LANCZOS)
    
    bio = io.BytesIO()
    img_final.save(bio, 'PNG', quality=95)
    bio.seek(0)
    return bio

# --- TELEGRAM ---
def enviar_multimedia(texto, imagen):
    if not TOKEN or not DESTINATARIOS: return
    for chat_id in DESTINATARIOS:
        try:
            imagen.seek(0)
            requests.post(
                f"https://api.telegram.org/bot{TOKEN}/sendPhoto",
                data={'chat_id': chat_id, 'caption': texto, 'parse_mode': 'HTML'},
                files={'photo': ('status.png', imagen, 'image/png')},
                timeout=20
            )
        except Exception as e: print(f"Error TG: {e}")

def enviar_texto(texto):
    if not TOKEN or not DESTINATARIOS: return
    for chat_id in DESTINATARIOS:
        try:
            requests.post(
                f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                data={'chat_id': chat_id, 'text': texto, 'parse_mode': 'HTML', 'disable_web_page_preview': True},
                timeout=10
            )
        except: pass

# --- CEREBRO ---
def resolver_redireccion_google(url, fuente=""):
    try:
        session = requests.Session()
        r = session.get(url, headers=get_headers(), timeout=10, verify=False, allow_redirects=True)
        basura = ["google", "gstatic", "youtube", "analytics", "doubleclick", "facebook", "twitter", "googletagmanager", "scorecardresearch"]
        if "google" in r.url:
            clean = fuente.lower().replace(" ", "").replace("tv", "").replace("noticias", "").replace("diario","")
            if len(clean) < 3: clean = "xxxxx"
            candidates = re.findall(r'(https?:\/\/[^"\s<>\\]+)', r.text)
            gen_match = None
            for c in candidates:
                u = unquote(c).replace("\\u0026", "&").replace("\\", "")
                if any(b in u for b in basura) or len(u) < 25: continue
                if u.endswith(('.png','.jpg','.js','.css','.woff')): continue
                if clean in u.lower(): return session.get(u, headers=get_headers(), timeout=10, verify=False)
                if not gen_match: gen_match = u
            if gen_match: return session.get(gen_match, headers=get_headers(), timeout=10, verify=False)
        return r
    except: return None

def espiar_web(url, fuente=""):
    try:
        resp = resolver_redireccion_google(url, fuente)
        if resp and resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            for s in soup.find_all('script', type='application/ld+json'):
                if s.string:
                    try:
                        d = json.loads(s.string)
                        if isinstance(d, list): d=d[0]
                        if 'articleBody' in d: return d['articleBody']
                    except: continue
            for t in soup(["script", "style", "nav", "footer", "header", "ads", "iframe", "aside", "form"]): t.extract()
            textos = [t.get_text().strip() for t in soup.find_all(['p','li','h1','h2','h3']) if len(t.get_text().strip()) > 25]
            return " ".join(textos)
    except: pass
    return ""

def detectar_problemas(texto):
    texto = texto.lower()
    frases = re.split(r'[.;\n|]', texto)
    res = {}
    for f in frases:
        if len(f) < 10: continue
        lineas = []
        for k, v in MAPA_LINEAS.items():
            if re.search(fr'\b{k}\b' if k.isdigit() else k, f) or f"linea {k}" in f or f"l{k} " in f:
                lineas.append(v)
        if lineas:
            found = [val for key, val in CAUSAS.items() if key in f]
            cause = ", ".join(list(set(found))) if found else "Afectación"
            for l in set(lineas):
                if l not in res or "Afectación" in res[l]: res[l] = cause
    return res

def revisar_todo(ahora):
    msgs = []
    afectaciones = {}
    try:
        feed = feedparser.parse(RSS_URL)
        lim = ahora - timedelta(minutes=65)
        for e in feed.entries:
            if hasattr(e,'published_parsed'):
                dt = datetime(*e.published_parsed[:6], tzinfo=pytz.utc).astimezone(ahora.tzinfo)
                if dt > lim:
                    txt = f"{e.title}. {e.summary if hasattr(e,'summary') else ''}"
                    fuente = e.source.title if hasattr(e,'source') else ""
                    if any(w in txt.lower() for w in CAUSAS.keys()):
                        probs = detectar_problemas(txt)
                        if not probs:
                            wc = espiar_web(e.link, fuente)
                            probs = detectar_problemas(txt + " " + wc)
                        if probs:
                            afectaciones.update(probs)
                            emoji = "✅" if any(s in e.title.lower() for s in PALABRAS_SOLUCION) else "🚨"
                            detalles = "\n".join([f"• <b>{k}:</b> {v}" for k,v in probs.items()])
                            msgs.append(f"{emoji} <b>NOTICIA:</b> {e.title}\n{detalles}\n🔗 <a href='{e.link}'>Leer Nota</a>")
    except Exception as ex: print(f"RSS: {ex}")

    for inst in ["nitter.privacydev.net", "nitter.net"]:
        try:
            scraper = Nitter(log_level=1, skip_instance_check=False, instance=inst)
            t = scraper.get_tweets("MetroCDMX", mode='user', number=4)
            if t and 'tweets' in t:
                for tw in t['tweets']:
                    if "m" in tw['date'] or "1h" in tw['date']:
                        txt = tw['text'].lower()
                        if any(w in txt for w in CAUSAS.keys()) and not any(ig in txt for ig in IGNORAR):
                            probs = detectar_problemas(txt)
                            afectaciones.update(probs)
                            msgs.append(f"🚨 <b>OFICIAL:</b> {tw['text']}\n🔗 <a href='{tw['link']}'>Ver Tweet</a>")
                break
        except: continue
    return msgs, afectaciones

def main():
    tz = pytz.timezone('America/Mexico_City')
    now = datetime.now(tz)
    print(f"Start: {now}")
    enviar_texto("📡 <i>Sincronizando red...</i>")
    
    d, h = now.weekday(), now.hour
    msg_h = None
    if d<=4 and h==5: msg_h = "🚇 <b>APERTURA DE SERVICIO</b>"
    elif h==0: msg_h = "💤 <b>CIERRE DE SERVICIO</b>"
    if msg_h: enviar_texto(msg_h + FIRMA); return

    txts, fallas = revisar_todo(now)
    if txts:
        img = generar_tablero_visual(fallas)
        u = list(dict.fromkeys(txts))
        cap = f"📢 <b>REPORTE ({now.strftime('%I:%M %p')})</b>\n──────────────────\n" + "\n\n".join(u) + FIRMA
        enviar_multimedia(cap[:1024], img)
    else:
        print("Normal")
        enviar_texto("✅ <b>Sistema operando con normalidad.</b>" + FIRMA)

if __name__ == "__main__":
    main()
