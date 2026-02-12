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
from PIL import Image, ImageDraw, ImageFont # Módulo de Dibujo

# Desactivar advertencias de SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- CONFIGURACIÓN ---
TOKEN = os.environ.get('TELEGRAM_TOKEN')
ID_GRUPO = os.environ.get('TELEGRAM_CHAT_ID') 
ID_CANAL = os.environ.get('TELEGRAM_CHANNEL_ID') 
DESTINATARIOS = [id_ for id_ in [ID_GRUPO, ID_CANAL] if id_]

RSS_URL = "https://news.google.com/rss/search?q=Metro+CDMX+retraso+OR+falla+OR+caos+when:1h&hl=es-419&gl=MX&ceid=MX:es-419"

# Diccionario de causas
CAUSAS = {
    "retraso": "Retrasos", "lento": "Marcha Lenta", "lenta": "Marcha Lenta",
    "falla": "Falla Técnica", "avería": "Avería", "desalojo": "Desalojo",
    "humo": "Humo", "fuego": "Conato Incendio", "quemado": "Olor Quemado",
    "zapatas": "Zapatas", "lluvia": "Lluvia", "mojado": "Lluvia", 
    "caos": "Aglomeración", "colapso": "Colapso", "espera": "Espera Alta", 
    "detenido": "Detenido", "suicida": "Persona en Vías", "arrollado": "Accidente",
    "corte": "Corte Energía", "bloqueo": "Bloqueo", "cerrada": "Cerrada"
}

PALABRAS_CLAVE = list(CAUSAS.keys()) + ["afectaciones", "avance", "servicio"]
PALABRAS_SOLUCION = ["restablece", "normal", "agiliza", "solucionado", "continuo", "reanuda"]
IGNORAR = ["buenos días", "cubrebocas", "tarjeta", "arte", "exposición", "domingos y días festivos", "cultura"]
FIRMA = "\n\n— 🤖 <i>JJMex Bot</i>"

# COLORES OFICIALES DEL METRO (Hex)
COLORES_LINEAS = {
    "1": "#F04E98", "2": "#0057B8", "3": "#6D8D23", 
    "4": "#6FB19C", "5": "#FFCD00", "6": "#DB2228", 
    "7": "#E46F23", "8": "#009A44", "9": "#5B3A29", 
    "A": "#9F258F", "B": "#B0B3B2", "12": "#C19C2D"
}

# Mapeo para detección de texto
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

ua = UserAgent()

def get_headers():
    return {'User-Agent': ua.random, 'Referer': 'https://news.google.com/'}

# --- GENERADOR DE IMAGEN (DASHBOARD) ---
def descargar_fuente():
    """Descarga una fuente Google Font para asegurar que se vea bien."""
    try:
        url_font = "https://github.com/google/fonts/raw/main/apache/robotoslab/RobotoSlab-Bold.ttf"
        r = requests.get(url_font)
        return io.BytesIO(r.content)
    except: return None

def generar_tablero_visual(lineas_afectadas):
    """
    Crea una imagen con el estado de las 12 líneas.
    lineas_afectadas: Diccionario {'L3': 'Humo', 'L7': 'Lento'}
    """
    # 1. Configuración del Lienzo
    W, H = 800, 600
    bg_color = (20, 24, 30) # Azul oscuro casi negro
    img = Image.new('RGB', (W, H), color=bg_color)
    draw = ImageDraw.Draw(img)
    
    # 2. Cargar Fuente
    font_bytes = descargar_fuente()
    try:
        font_title = ImageFont.truetype(font_bytes, 40)
        font_line = ImageFont.truetype(font_bytes, 30)
        font_status = ImageFont.truetype(font_bytes, 18)
    except:
        font_title = ImageFont.load_default()
        font_line = ImageFont.load_default()
        font_status = ImageFont.load_default()

    # 3. Título y Fecha
    ahora = datetime.now(pytz.timezone('America/Mexico_City')).strftime("%I:%M %p | %d-%b")
    draw.text((30, 20), "ESTADO DE LA RED - JJMEX HUB", font=font_title, fill=(255, 255, 255))
    draw.text((30, 70), f"Actualización: {ahora}", font=font_status, fill=(200, 200, 200))

    # 4. Dibujar Grilla de Líneas
    # Orden de las líneas para el dibujo
    orden = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "A", "B", "12"]
    
    start_x, start_y = 30, 120
    box_w, box_h = 170, 100
    gap = 20
    cols = 4

    for i, linea_key in enumerate(orden):
        # Calcular posición
        row = i // cols
        col = i % cols
        x = start_x + (col * (box_w + gap))
        y = start_y + (row * (box_h + gap))
        
        # Determinar Estado
        nombre_linea = f"L{linea_key}" if linea_key not in ["A", "B"] else f"L{linea_key}"
        color_hex = COLORES_LINEAS[linea_key]
        
        estado_texto = "NORMAL"
        status_color = (0, 200, 100) # Verde
        
        # Verificar si esta línea está en las afectadas
        if nombre_linea in lineas_afectadas:
            estado_texto = lineas_afectadas[nombre_linea].upper()[:15] # Cortar si es muy largo
            status_color = (255, 50, 50) # Rojo Alerta
        
        # Dibujar Caja (Borde)
        draw.rounded_rectangle([x, y, x+box_w, y+box_h], radius=10, outline=color_hex, width=3)
        
        # Etiqueta de Línea (Círculo de color)
        draw.ellipse([x+10, y+10, x+50, y+50], fill=color_hex)
        # Texto del número/letra centrado en el círculo (Ajuste manual simple)
        text_w = draw.textlength(linea_key, font=font_line)
        draw.text((x+30-(text_w/2), y+12), linea_key, font=font_line, fill=(255,255,255))
        
        # Texto de Estado
        draw.text((x+60, y+15), "Estado:", font=font_status, fill=(150, 150, 150))
        draw.text((x+10, y+60), estado_texto, font=font_status, fill=status_color)

    # Guardar en memoria
    bio = io.BytesIO()
    img.save(bio, 'PNG')
    bio.seek(0)
    return bio

def enviar_telegram_con_foto(texto, imagen_bio):
    """Envía mensaje con foto usando multipart/form-data"""
    if not TOKEN or not DESTINATARIOS: return
    
    for chat_id in DESTINATARIOS:
        try:
            imagen_bio.seek(0) # Reiniciar puntero
            url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
            payload = {'chat_id': chat_id, 'caption': texto, 'parse_mode': 'HTML'}
            files = {'photo': ('estado.png', imagen_bio, 'image/png')}
            
            requests.post(url, data=payload, files=files, timeout=20)
        except Exception as e:
            print(f"Error enviando foto a {chat_id}: {e}")

def enviar_telegram_texto(mensaje):
    if not TOKEN or not DESTINATARIOS: return
    for chat_id in DESTINATARIOS:
        try:
            url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
            data = {'chat_id': chat_id, 'text': mensaje, 'parse_mode': 'HTML', 'disable_web_page_preview': True}
            requests.post(url, data=data, timeout=10)
        except: pass

# --- FUNCIONES DE ANÁLISIS (CORE) ---
def analizar_sentimiento(texto):
    if any(p in texto.lower() for p in PALABRAS_SOLUCION): return "✅" 
    return "🚨"

def detectar_problemas_por_linea(texto):
    """Devuelve un dict: {'L3': 'Humo', 'L1': 'Retrasos'}"""
    texto = texto.lower()
    frases = re.split(r'[.;\n]', texto) 
    detectados = {}

    for frase in frases:
        if len(frase) < 10: continue
        
        lineas_presentes = []
        for k, v in MAPA_LINEAS.items():
            patrones = [f"línea {k}", f"linea {k}", f"l{k} ", f"l-{k}"]
            if len(k) < 2: patrones = [f"línea {k}", f"linea {k}", f"l-{k}"]
            if any(p in frase for p in patrones):
                lineas_presentes.append(v)
        
        if lineas_presentes:
            causas = [val for key, val in CAUSAS.items() if key in frase]
            causa_str = ", ".join(list(set(causas))) if causas else "Afectación"
            
            for linea in lineas_presentes:
                if linea not in detectados or "Afectación" in detectados[linea]:
                    detectados[linea] = causa_str
    return detectados

def resolver_redireccion_google(url_inicial, fuente=""):
    try:
        session = requests.Session()
        resp = session.get(url_inicial, headers=get_headers(), timeout=15, verify=False, allow_redirects=True)
        
        basura = ["google", "gstatic", "youtube", "analytics", "doubleclick", "facebook", "twitter"]
        if "google" in resp.url:
            fuente_clean = fuente.lower().replace(" ", "").replace("tv", "") if fuente else "xyz"
            raw_urls = re.findall(r'(https?:\/\/[^"\s<>\\]+)', resp.text)
            
            candidato = None
            for r in raw_urls:
                u = unquote(r).replace("\\u0026", "&").replace("\\", "")
                if any(b in u for b in basura) or len(u) < 25: continue
                if fuente_clean in u.lower(): return session.get(u, headers=get_headers(), timeout=15, verify=False)
                if not candidato: candidato = u
            if candidato: return session.get(candidato, headers=get_headers(), timeout=15, verify=False)
        return resp
    except: return None

def espiar_noticia(url, fuente=""):
    try:
        resp = resolver_redireccion_google(url, fuente)
        if resp and resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            # JSON-LD
            scripts = soup.find_all('script', type='application/ld+json')
            for s in scripts:
                if s.string:
                    try:
                        d = json.loads(s.string)
                        if isinstance(d, list): d=d[0]
                        if 'articleBody' in d: return d['articleBody']
                    except: continue
            # HTML
            for t in soup(["script", "style", "nav", "footer", "header", "ads", "iframe"]): t.extract()
            textos = [t.get_text().strip() for t in soup.find_all(['p','li','h1','h2']) if len(t.get_text().strip())>20]
            return " ".join(textos)
    except: pass
    return ""

def revisar_incidentes(ahora):
    incidentes_texto = []
    todas_afectaciones = {} # Acumulador de todas las líneas fallando
    
    # 1. GOOGLE NEWS
    try:
        print("🔎 Analizando Noticias...")
        feed = feedparser.parse(RSS_URL)
        limite = ahora - timedelta(minutes=65)
        for e in feed.entries:
            if hasattr(e, 'published_parsed'):
                f = datetime(*e.published_parsed[:6], tzinfo=pytz.utc).astimezone(ahora.tzinfo)
                if f > limite:
                    txt = f"{e.title}. {e.summary if hasattr(e,'summary') else ''}"
                    fuente = e.source.title if hasattr(e,'source') else ""
                    
                    if any(p in txt.lower() for p in list(CAUSAS.keys())+["afectaciones"]):
                        print(f"👉 Noticia: {e.title[:30]}...")
                        probs = detectar_problemas_por_linea(txt)
                        if not probs:
                            web_txt = espiar_noticia(e.link, fuente)
                            probs = detectar_problemas_por_linea(txt + " " + web_txt)
                        
                        todas_afectaciones.update(probs) # Guardar para la imagen
                        
                        emoji = analizar_sentimiento(e.title)
                        detalle = "\n".join([f"⚠️ {k}: {v}" for k,v in probs.items()])
                        incidentes_texto.append(f"{emoji} <b>NOTICIA:</b> {e.title}\n{detalle}\n🔗 <a href='{e.link}'>Leer más</a>")
    except Exception as e: print(f"Error RSS: {e}")

    # 2. NITTER
    for inst in ["nitter.privacydev.net", "nitter.net"]:
        try:
            print(f"🦅 Nitter ({inst})...")
            scraper = Nitter(log_level=1, skip_instance_check=False, instance=inst)
            data = scraper.get_tweets("MetroCDMX", mode='user', number=5)
            if data and 'tweets' in data:
                for t in data['tweets']:
                    txt = t['text'].lower()
                    if any(p in txt for p in list(CAUSAS.keys())+["servicio"]) and not any(i in txt for i in IGNORAR):
                        if "m" in t['date'] or "1h" in t['date']:
                            probs = detectar_problemas_por_linea(txt)
                            todas_afectaciones.update(probs)
                            
                            emoji = analizar_sentimiento(txt)
                            detalle = "\n".join([f"⚠️ {k}: {v}" for k,v in probs.items()])
                            incidentes_texto.append(f"{emoji} <b>OFICIAL:</b> {t['text']}\n{detalle}\n🔗 <a href='{t['link']}'>Ver Tweet</a>")
                break
        except: continue

    return incidentes_texto, todas_afectaciones

def verificar_horario(ahora):
    d, h = ahora.weekday(), ahora.hour
    if d<=4 and h==5: return "🚇 <b>INICIO DE SERVICIO</b>"
    if d==5 and h==6: return "🚇 <b>INICIO SÁBADO</b>"
    if d==6 and h==7: return "🚇 <b>INICIO DOMINGO</b>"
    if h==0: return "💤 <b>CIERRE DE SERVICIO</b>"
    return None

def main():
    tz = pytz.timezone('America/Mexico_City')
    ahora = datetime.now(tz)
    print(f"🏁 JJMex Scan: {ahora}")

    # Ping técnico (solo texto)
    enviar_telegram_texto("📡 <i>Conectando con la red de movilidad y analizando reportes ciudadanos...</i>")
    
    # 1. Horario
    msg_h = verificar_horario(ahora)
    if msg_h: enviar_telegram_texto(msg_h + FIRMA); return

    # 2. Incidentes
    textos, mapa_fallas = revisar_incidentes(ahora)
    
    if textos:
        # Generar IMAGEN DEL TABLERO
        print(f"🎨 Generando tablero con fallas en: {list(mapa_fallas.keys())}")
        imagen_bio = generar_tablero_visual(mapa_fallas)
        
        # Eliminar duplicados de texto
        msgs_unicos = list(dict.fromkeys(textos))
        caption = f"📢 <b>REPORTE VISUAL JJMEX ({ahora.strftime('%I:%M %p')})</b>\n──────────────────\n" + "\n\n".join(msgs_unicos) + FIRMA
        
        # Enviar FOTO + TEXTO
        enviar_telegram_con_foto(caption[:1024], imagen_bio)
    else:
        # Todo bien (Enviar solo texto o imagen verde opcional)
        print("✅ Todo normal.")
        enviar_telegram_texto("✅ <b>Sin incidentes críticos.</b>\nLa red opera con normalidad." + FIRMA)

if __name__ == "__main__":
    main()
