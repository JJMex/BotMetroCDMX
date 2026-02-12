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
    "BG": "#1A1E24", "CARD": "#252A33", "TEXT": "#FFFFFF", "SUBTEXT": "#A0AAB5",
    "ALERT": "#FF4444", "OK": "#00C851"
}

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

# --- MOTOR GRÁFICO (MODO DISEÑADOR) ---
def descargar_fuente():
    try:
        # Usamos Roboto Medium para un look app moderna
        url = "https://github.com/google/fonts/raw/main/apache/robotoslab/RobotoSlab-Bold.ttf" 
        return io.BytesIO(requests.get(url).content)
    except: return None

def dibujar_tarjeta(draw, x, y, w, h, linea, estado, color_linea, font_l, font_s):
    # Fondo tarjeta
    color_borde = COLORES["ALERT"] if estado != "Normal" else COLORES["CARD"]
    bg_card = "#2C333D" if estado == "Normal" else "#381E1E"
    
    draw.rounded_rectangle([x, y, x+w, y+h], radius=12, fill=bg_card, outline=color_borde, width=2 if estado != "Normal" else 0)
    
    # --- MEJORA DE NITIDEZ AQUÍ ---
    # Coordenadas del círculo
    cx1, cy1 = x+10, y+10
    cx2, cy2 = x+45, y+45
    draw.ellipse([cx1, cy1, cx2, cy2], fill=color_linea)
    
    # Texto a dibujar (quitamos la L para que sea solo el número/letra)
    txt_num = linea.replace("L","")
    
    # Cálculo de Centro Exacto
    center_x = (cx1 + cx2) / 2
    center_y = (cy1 + cy2) / 2
    
    # Obtener dimensiones exactas del texto para centrarlo
    bbox = font_l.getbbox(txt_num)
    txt_w = bbox[2] - bbox[0]
    txt_h = bbox[3] - bbox[1]
    
    txt_x = center_x - (txt_w / 2)
    txt_y = center_y - (txt_h / 2) - 2 # Pequeño ajuste visual hacia arriba

    # Dibujar texto con CONTORNO NEGRO (Stroke) para máxima nitidez
    draw.text((txt_x, txt_y), txt_num, font=font_l, fill="white", stroke_width=2, stroke_fill="black")
    # ---------------------------------
    
    # Texto Estado
    color_status = COLORES["OK"] if estado == "Normal" else COLORES["ALERT"]
    draw.text((x+55, y+15), estado[:18], font=font_s, fill=color_status)

def generar_tablero_visual(afectaciones):
    """Genera un dashboard tipo App Móvil"""
    W, H = 800, 500
    img = Image.new('RGB', (W, H), color=COLORES["BG"])
    draw = ImageDraw.Draw(img)
    
    fb = descargar_fuente()
    try:
        f_title = ImageFont.truetype(fb, 36)
        # AUMENTAMOS TAMAÑO DE FUENTE DE LÍNEA (De 22 a 24)
        f_line = ImageFont.truetype(fb, 24) 
        f_status = ImageFont.truetype(fb, 18)
        f_sub = ImageFont.truetype(fb, 14)
    except:
        f_title = f_line = f_status = f_sub = ImageFont.load_default()

    # Header
    now = datetime.now(pytz.timezone('America/Mexico_City'))
    draw.text((30, 25), "ESTADO DEL SERVICIO", font=f_title, fill="white")
    draw.text((30, 70), f"Última actualización: {now.strftime('%I:%M %p • %d %b')}", font=f_sub, fill=COLORES["SUBTEXT"])
    
    draw.line([(30, 95), (770, 95)], fill=COLORES["CARD"], width=2)

    # Grid (2 Columnas x 6 Filas)
    lineas = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "A", "B", "12"]
    start_x, start_y = 30, 115
    col_w, row_h = 360, 55
    gap_x, gap_y = 20, 10

    for i, l_key in enumerate(lineas):
        col = i % 2
        row = i // 2
        x = start_x + (col * (col_w + gap_x))
        y = start_y + (row * (row_h + gap_y))
        
        l_name = f"L{l_key}"
        estado = afectaciones.get(l_name, "Normal")
        
        dibujar_tarjeta(draw, x, y, col_w, row_h, l_key, estado, COLORES[l_key], f_line, f_status)

    # Footer
    draw.text((W-150, H-30), "JJMex Intelligence", font=f_sub, fill=COLORES["SUBTEXT"])
    
    bio = io.BytesIO()
    img.save(bio, 'PNG', quality=95) # Calidad máxima
    bio.seek(0)
    return bio

# --- FUNCIONES DE TELEGRAM ---
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

# --- CEREBRO DE ANÁLISIS ---
def resolver_redireccion_google(url, fuente=""):
    try:
        session = requests.Session()
        r = session.get(url, headers=get_headers(), timeout=10, verify=False, allow_redirects=True)
        
        basura = ["google", "gstatic", "youtube", "analytics", "doubleclick", "facebook", "twitter", "googletagmanager", "scorecardresearch"]
        
        if "google" in r.url:
            print(f"   ⚠️ URL Ofuscada. Fuente esperada: '{fuente}'")
            fuente_clean = fuente.lower().replace(" ", "").replace("tv", "").replace("noticias", "").replace("diario","")
            if len(fuente_clean) < 3: fuente_clean = "xxxxx"

            candidates = re.findall(r'(https?:\/\/[^"\s<>\\]+)', r.text)
            
            best_match = None
            generic_match = None
            
            for c in candidates:
                u = unquote(c).replace("\\u0026", "&").replace("\\", "")
                if any(b in u for b in basura) or len(u) < 25: continue
                if u.endswith(('.png','.jpg','.js','.css','.woff')): continue

                if fuente_clean in u.lower():
                    print(f"   🎯 MATCH DE FUENTE: {u[:50]}...")
                    return session.get(u, headers=get_headers(), timeout=10, verify=False)
                
                if not generic_match: generic_match = u
            
            target = best_match or generic_match
            if target: return session.get(target, headers=get_headers(), timeout=10, verify=False)
            
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
            if re.search(fr'\b{k}\b' if k.isdigit() else k, f):
                lineas.append(v)
            elif f"linea {k}" in f or f"l{k} " in f:
                lineas.append(v)
        
        if lineas:
            found_causes = [val for key, val in CAUSAS.items() if key in f]
            cause_txt = ", ".join(list(set(found_causes))) if found_causes else "Afectación"
            
            for l in set(lineas):
                if l not in res or "Afectación" in res[l]:
                    res[l] = cause_txt
    return res

def revisar_todo(ahora):
    msgs = []
    afectaciones_totales = {}
    
    # 1. RSS
    try:
        print("🔎 RSS Scan...")
        feed = feedparser.parse(RSS_URL)
        limite = ahora - timedelta(minutes=65)
        
        for e in feed.entries:
            if hasattr(e,'published_parsed'):
                dt = datetime(*e.published_parsed[:6], tzinfo=pytz.utc).astimezone(ahora.tzinfo)
                if dt > limite:
                    txt_base = f"{e.title}. {e.summary if hasattr(e,'summary') else ''}"
                    fuente = e.source.title if hasattr(e,'source') else ""
                    
                    if any(w in txt_base.lower() for w in CAUSAS.keys()):
                        print(f"👉 Detectado: {e.title[:30]}")
                        probs = detectar_problemas(txt_base)
                        
                        if not probs:
                            print("   🕵️ Deep Scan activado...")
                            web_content = espiar_web(e.link, fuente)
                            probs = detectar_problemas(txt_base + " " + web_content)
                        
                        if probs:
                            afectaciones_totales.update(probs)
                            emoji = "✅" if any(s in e.title.lower() for s in PALABRAS_SOLUCION) else "🚨"
                            detalles = "\n".join([f"• <b>{k}:</b> {v}" for k,v in probs.items()])
                            msgs.append(f"{emoji} <b>NOTICIA:</b> {e.title}\n{detalles}\n🔗 <a href='{e.link}'>Leer Nota</a>")
    except Exception as ex: print(f"RSS Error: {ex}")

    # 2. NITTER
    for inst in ["nitter.privacydev.net", "nitter.net"]:
        try:
            print(f"🦅 Twitter Scan ({inst})...")
            scraper = Nitter(log_level=1, skip_instance_check=False, instance=inst)
            tweets = scraper.get_tweets("MetroCDMX", mode='user', number=4)
            if tweets and 'tweets' in tweets:
                for t in tweets['tweets']:
                    if "m" in t['date'] or "1h" in t['date']:
                        txt = t['text'].lower()
                        if any(w in txt for w in CAUSAS.keys()) and not any(ig in txt for ig in IGNORAR):
                            probs = detectar_problemas(txt)
                            afectaciones_totales.update(probs)
                            msgs.append(f"🚨 <b>OFICIAL:</b> {t['text']}\n🔗 <a href='{t['link']}'>Ver Tweet</a>")
                break
        except: continue

    return msgs, afectaciones_totales

def main():
    tz = pytz.timezone('America/Mexico_City')
    now = datetime.now(tz)
    print(f"🏁 Start: {now}")
    
    enviar_texto("📡 <i>Conectando con la red de movilidad y analizando reportes ciudadanos...</i>")
    
    # Horarios
    d, h = now.weekday(), now.hour
    msg_h = None
    if d<=4 and h==5: msg_h = "🚇 <b>APERTURA DE SERVICIO</b>"
    elif h==0: msg_h = "💤 <b>CIERRE DE SERVICIO</b>"
    if msg_h: enviar_texto(msg_h + FIRMA); return

    # Incidentes
    textos, fallas = revisar_todo(now)
    
    if textos:
        print(f"🎨 Pintando dashboard: {fallas}")
        img = generar_tablero_visual(fallas)
        
        uniques = list(dict.fromkeys(textos))
        caption = f"📢 <b>REPORTE ({now.strftime('%I:%M %p')})</b>\n──────────────────\n" + "\n\n".join(uniques) + FIRMA
        
        enviar_multimedia(caption[:1024], img)
    else:
        print("✅ Todo normal")
        enviar_texto("✅ <b>Sistema operando con normalidad.</b>\nSin incidentes críticos reportados." + FIRMA)

if __name__ == "__main__":
    main()
