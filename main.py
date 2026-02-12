import os
import time
import requests
import feedparser
import pytz
import re
import urllib3
import json
from datetime import datetime, timedelta
from ntscraper import Nitter
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from urllib.parse import unquote

# 1. CONFIGURACIÓN TÉCNICA
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
ua = UserAgent()

# --- CREDENCIALES ---
TOKEN = os.environ.get('TELEGRAM_TOKEN')
ID_GRUPO = os.environ.get('TELEGRAM_CHAT_ID') 
ID_CANAL = os.environ.get('TELEGRAM_CHANNEL_ID') 
DESTINATARIOS = [id_ for id_ in [ID_GRUPO, ID_CANAL] if id_]

RSS_URL = "https://news.google.com/rss/search?q=Metro+CDMX+retraso+OR+falla+OR+caos+when:1h&hl=es-419&gl=MX&ceid=MX:es-419"

# --- DICCIONARIO DE INTELIGENCIA ---
CAUSAS = {
    "retraso": "Retrasos", "lento": "Marcha Lenta", "lenta": "Marcha Lenta",
    "falla": "Falla Técnica", "avería": "Avería", "desalojo": "Desalojo de Tren",
    "humo": "Presencia de Humo", "fuego": "Conato de Incendio", "quemado": "Olor a Quemado",
    "zapatas": "Zapatas Pegadas", "lluvia": "Lluvia / Marcha de Seguridad", 
    "mojado": "Lluvia", "caos": "Aglomeración Alta", "colapso": "Colapso",
    "espera": "Tiempos de Espera Altos", "detenido": "Tren Detenido", 
    "suicida": "Persona en Vías", "arrollado": "Accidente en Vías", 
    "corte": "Corte de Corriente", "bloqueo": "Bloqueo Exterior", 
    "cerrada": "Estación Cerrada", "sin servicio": "Sin Servicio"
}

PALABRAS_CLAVE = list(CAUSAS.keys()) + ["afectaciones", "avance", "servicio", "estaciones"]
PALABRAS_SOLUCION = ["restablece", "normal", "agiliza", "solucionado", "continuo", "reanuda", "opera con normalidad"]
IGNORAR = ["buenos días", "cubrebocas", "tarjeta", "arte", "exposición", "domingos y días festivos", "cultura", "museo", "simulacro"]
FIRMA = "\n\n— 🤖 <i>JJMex Bot</i>"

# --- MAPA DE LINEAS CON EMOJIS DE COLOR ---
MAPA_LINEAS = {
    "1": "🩷 L1 (Rosa)", "uno": "🩷 L1 (Rosa)", "rosa": "🩷 L1 (Rosa)",
    "2": "🔵 L2 (Azul)", "dos": "🔵 L2 (Azul)", "azul": "🔵 L2 (Azul)",
    "3": "💚 L3 (Verde)", "tres": "💚 L3 (Verde)", "verde": "💚 L3 (Verde)",
    "4": "🩵 L4 (Cian)", "cuatro": "🩵 L4 (Cian)", "cian": "🩵 L4 (Cian)",
    "5": "🟡 L5 (Amarilla)", "cinco": "🟡 L5 (Amarilla)", "amarilla": "🟡 L5 (Amarilla)",
    "6": "🔴 L6 (Roja)", "seis": "🔴 L6 (Roja)", "roja": "🔴 L6 (Roja)",
    "7": "🟠 L7 (Naranja)", "siete": "🟠 L7 (Naranja)", "naranja": "🟠 L7 (Naranja)",
    "8": "🟢 L8 (Verde)", "ocho": "🟢 L8 (Verde)", 
    "9": "🟤 L9 (Café)", "nueve": "🟤 L9 (Café)", "café": "🟤 L9 (Café)",
    "a": "🟣 LA (Férrea)", "férrea": "🟣 LA (Férrea)",
    "b": "🩶 LB (Gris)", "gris": "🩶 LB (Gris)",
    "12": "🌟 L12 (Dorada)", "doce": "🌟 L12 (Dorada)", "dorada": "🌟 L12 (Dorada)"
}

def get_headers():
    return {
        'User-Agent': ua.random,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Referer': 'https://news.google.com/'
    }

def enviar_telegram(mensaje):
    if not TOKEN or not DESTINATARIOS: return
    for chat_id in DESTINATARIOS:
        for _ in range(3):
            try:
                url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
                data = {'chat_id': chat_id, 'text': mensaje, 'parse_mode': 'HTML', 'disable_web_page_preview': True}
                requests.post(url, data=data, timeout=10)
                break
            except: pass

# --- CEREBRO DE ANÁLISIS ---

def resolver_redireccion_google(url, fuente=""):
    try:
        session = requests.Session()
        r = session.get(url, headers=get_headers(), timeout=10, verify=False, allow_redirects=True)
        
        basura = ["google", "gstatic", "youtube", "analytics", "doubleclick", "facebook", "twitter", "googletagmanager", "scorecardresearch"]
        
        if "google" in r.url:
            print(f"   ⚠️ URL Ofuscada. Fuente esperada: '{fuente}'")
            clean = fuente.lower().replace(" ", "").replace("tv", "").replace("noticias", "").replace("diario","")
            if len(clean) < 3: clean = "xxxxx"

            candidates = re.findall(r'(https?:\/\/[^"\s<>\\]+)', r.text)
            
            best_match = None
            generic_match = None
            
            for c in candidates:
                u = unquote(c).replace("\\u0026", "&").replace("\\", "")
                if any(b in u for b in basura): continue
                if len(u) < 25: continue
                if u.endswith(('.png','.jpg','.js','.css','.woff')): continue

                if clean in u.lower():
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

def detectar_problemas_detallados(texto):
    texto = texto.lower()
    frases = re.split(r'[.;\n|]', texto)
    reportes = {}
    
    for f in frases:
        if len(f) < 10: continue
        
        lineas_en_frase = []
        for k, v in MAPA_LINEAS.items():
            if re.search(fr'\b{k}\b' if k.isdigit() else k, f) or f"linea {k}" in f or f"l{k} " in f:
                lineas_en_frase.append(v)
        
        if lineas_en_frase:
            found_causes = [val for key, val in CAUSAS.items() if key in f]
            cause_txt = ", ".join(list(set(found_causes))) if found_causes else "Posible Afectación"
            
            for l in set(lineas_en_frase):
                if l not in reportes or "Posible" in reportes[l]:
                    reportes[l] = cause_txt
    
    if reportes:
        items = sorted(reportes.items())
        # Ahora el reporte incluirá el emoji automáticamente
        return "\n".join([f"⚠️ <b>{k}:</b> {v}" for k, v in items])
    return ""

def revisar_todo(ahora):
    msgs = []
    
    # --- 1. RSS ---
    try:
        print("🔎 Escaneando Google News...")
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
                        
                        detalles = detectar_problemas_detallados(txt_base)
                        if not detalles:
                            print("   🕵️ Escaneo profundo...")
                            web_content = espiar_web(e.link, fuente)
                            detalles = detectar_problemas_detallados(txt_base + " " + web_content)
                        
                        emoji = "✅" if any(s in e.title.lower() for s in PALABRAS_SOLUCION) else "🚨"
                        
                        cuerpo = f"{emoji} <b>NOTICIA:</b> {e.title}\n"
                        if detalles: cuerpo += f"\n{detalles}\n"
                        cuerpo += f"🔗 <a href='{e.link}'>Leer Nota Completa</a>"
                        msgs.append(cuerpo)
    except Exception as ex: print(f"RSS Error: {ex}")

    # --- 2. TWITTER ---
    for inst in ["nitter.privacydev.net", "nitter.net"]:
        try:
            print(f"🦅 Escaneando Twitter ({inst})...")
            scraper = Nitter(log_level=1, skip_instance_check=False, instance=inst)
            tweets = scraper.get_tweets("MetroCDMX", mode='user', number=4)
            if tweets and 'tweets' in tweets:
                for t in tweets['tweets']:
                    if "m" in t['date'] or "1h" in t['date']:
                        txt = t['text'].lower()
                        if any(w in txt for w in CAUSAS.keys()) and not any(ig in txt for ig in IGNORAR):
                            detalles = detectar_problemas_detallados(txt)
                            emoji = "✅" if any(s in txt for s in PALABRAS_SOLUCION) else "🚨"
                            
                            cuerpo = f"{emoji} <b>OFICIAL:</b> {t['text']}\n"
                            if detalles: cuerpo += f"\n{detalles}\n"
                            cuerpo += f"🔗 <a href='{t['link']}'>Ver Tweet</a>"
                            msgs.append(cuerpo)
                break
        except: continue

    return msgs

def main():
    tz = pytz.timezone('America/Mexico_City')
    now = datetime.now(tz)
    print(f"🏁 Inicio: {now}")
    
    enviar_telegram("📡 <i>Conectando con la red de movilidad y analizando reportes ciudadanos...</i>")
    
    d, h = now.weekday(), now.hour
    msg_h = None
    if d<=4 and h==5: msg_h = "🚇 <b>APERTURA DE SERVICIO</b>\n──────────────────\nInicia operaciones día hábil."
    elif h==0: msg_h = "💤 <b>CIERRE DE SERVICIO</b>\n──────────────────\nBuenas noches."
    
    if msg_h: enviar_telegram(msg_h + FIRMA); return

    alertas = revisar_todo(now)
    
    if alertas:
        unicos = list(dict.fromkeys(alertas))
        header = f"📢 <b>REPORTE METRO ({now.strftime('%I:%M %p')})</b>\n──────────────────\n\n"
        full_msg = header + "\n\n".join(unicos) + FIRMA
        enviar_telegram(full_msg)
    else:
        print("✅ Sin novedades")
        enviar_telegram("✅ <b>Sistema operando con normalidad.</b>" + FIRMA)

if __name__ == "__main__":
    main()
