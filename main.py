import os
import time
import requests
import feedparser
import pytz
import re
from datetime import datetime, timedelta
from ntscraper import Nitter
from bs4 import BeautifulSoup

# --- CONFIGURACIÓN ---
TOKEN = os.environ.get('TELEGRAM_TOKEN')
ID_GRUPO = os.environ.get('TELEGRAM_CHAT_ID') 
ID_CANAL = os.environ.get('TELEGRAM_CHANNEL_ID') 
DESTINATARIOS = [id_ for id_ in [ID_GRUPO, ID_CANAL] if id_]

RSS_URL = "https://news.google.com/rss/search?q=Metro+CDMX+retraso+OR+falla+OR+caos+when:1h&hl=es-419&gl=MX&ceid=MX:es-419"
PALABRAS_CLAVE = ["retraso", "marcha lenta", "falla", "desalojo", "humo", "detenido", "caos", "lento", "espera", "sin servicio", "colapso", "afectaciones", "avance"]
IGNORAR = ["buenos días", "cubrebocas", "tarjeta", "arte", "exposición", "domingos y días festivos", "cultura"]

MAPA_LINEAS = {
    "1": "🩷 Línea 1 (Rosa)", "uno": "🩷 Línea 1 (Rosa)", "rosa": "🩷 Línea 1 (Rosa)",
    "2": "💙 Línea 2 (Azul)", "dos": "💙 Línea 2 (Azul)", "azul": "💙 Línea 2 (Azul)",
    "3": "💚 Línea 3 (Verde)", "tres": "💚 Línea 3 (Verde)", "verde": "💚 Línea 3 (Verde)",
    "4": "🩵 Línea 4 (Cian)", "cuatro": "🩵 Línea 4 (Cian)", "cian": "🩵 Línea 4 (Cian)",
    "5": "💛 Línea 5 (Amarilla)", "cinco": "💛 Línea 5 (Amarilla)", "amarilla": "💛 Línea 5 (Amarilla)",
    "6": "❤️ Línea 6 (Roja)", "seis": "❤️ Línea 6 (Roja)", "roja": "❤️ Línea 6 (Roja)",
    "7": "🧡 Línea 7 (Naranja)", "siete": "🧡 Línea 7 (Naranja)", "naranja": "🧡 Línea 7 (Naranja)",
    "8": "💚 Línea 8 (Verde)", "ocho": "💚 Línea 8 (Verde)", 
    "9": "🤎 Línea 9 (Café)", "nueve": "🤎 Línea 9 (Café)", "café": "🤎 Línea 9 (Café)",
    "a": "💜 Línea A (Férrea)", "férrea": "💜 Línea A (Férrea)",
    "b": "🩶 Línea B (Gris)", "gris": "🩶 Línea B (Gris)",
    "12": "💛 Línea 12 (Dorada)", "doce": "💛 Línea 12 (Dorada)", "dorada": "💛 Línea 12 (Dorada)"
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
            except: time.sleep(1)

def detectar_lineas(texto):
    texto = texto.lower()
    detectadas = set()
    for clave, nombre in MAPA_LINEAS.items():
        patrones = [f"línea {clave}", f"linea {clave}", f"l{clave} ", f"l-{clave}", f"la {clave} "]
        if len(clave) < 3: patrones = [f"línea {clave}", f"linea {clave}", f"l-{clave}"]
        if any(p in texto for p in patrones):
            detectadas.add(nombre)
    if detectadas:
        return "\n⚠️ <b>AFECTACIÓN CONFIRMADA:</b> " + ", ".join(sorted(list(detectadas)))
    return ""

def resolver_redireccion_google(url_inicial):
    """
    Intenta desenredar la URL de Google News para llegar a la fuente real (TV Azteca, El Universal, etc).
    """
    try:
        session = requests.Session()
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
        # 1. Primera petición: Dejamos que requests siga redirecciones estándar
        response = session.get(url_inicial, headers=headers, timeout=10, allow_redirects=True)
        
        # 2. Verificación: ¿Seguimos atrapados en Google?
        if "news.google.com" in response.url:
            print("   ⚠️ Atrapado en redirección de Google. Buscando enlace real...")
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Google suele poner el link real en un tag <a> que dice "Abrir" o similar
            # Buscamos cualquier link que NO sea de google
            links = soup.find_all('a', href=True)
            for link in links:
                href = link['href']
                if "google.com" not in href and href.startswith("http"):
                    print(f"   🎯 Enlace real encontrado: {href}")
                    # Hacemos una SEGUNDA petición, ahora sí a la web real
                    response_real = session.get(href, headers=headers, timeout=10)
                    return response_real
        
        return response # Si ya no estamos en Google, devolvemos la respuesta directa
        
    except Exception as e:
        print(f"   ❌ Error resolviendo URL: {e}")
        return None

def espiar_noticia_completa(url):
    try:
        # Usamos la nueva función inteligente
        response = resolver_redireccion_google(url)
        
        if response and response.status_code == 200:
            print(f"   ↳ Leyendo contenido de: {response.url[:40]}...")
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extraemos texto de párrafos y encabezados
            textos = soup.find_all(['p', 'h1', 'h2', 'article'])
            texto_completo = " ".join([t.get_text() for t in textos])
            return texto_completo
    except Exception as e:
        print(f"   ↳ Error espiando: {e}")
    return ""

def revisar_incidentes(ahora):
    incidentes = []
    
    # --- GOOGLE NEWS ---
    try:
        print("🔎 Analizando Noticias...")
        feed = feedparser.parse(RSS_URL)
        limite = ahora - timedelta(minutes=65) # Ventana de tiempo
        
        for e in feed.entries:
            if hasattr(e, 'published_parsed'):
                f = datetime(*e.published_parsed[:6], tzinfo=pytz.utc).astimezone(ahora.tzinfo)
                if f > limite:
                    titulo = e.title
                    
                    if any(p in titulo.lower() for p in PALABRAS_CLAVE):
                        print(f"👉 Posible incidente: {titulo[:30]}...")
                        
                        # 1. Detección rápida (Título)
                        tag_linea = detectar_lineas(titulo)
                        
                        # 2. Si falla, activamos MODO ESPÍA MEJORADO
                        if not tag_linea:
                            print("   🕵️ Activando escaneo profundo...")
                            texto_web = espiar_noticia_completa(e.link)
                            tag_linea = detectar_lineas(texto_web)
                            if tag_linea: print(f"   ✅ ¡Líneas detectadas!: {tag_linea}")
                            else: print("   ❌ No se encontraron líneas en el texto.")
                        
                        incidentes.append(f"📰 <b>NOTICIA:</b> {titulo}{tag_linea}\n🔗 <a href='{e.link}'>Ver Nota</a>")
    except Exception as e: print(f"Error RSS: {e}")

    # --- TWITTER (Nitter) ---
    instancias = ["nitter.privacydev.net", "nitter.net"]
    for instancia in instancias:
        try:
            print(f"🦅 Nitter ({instancia})...")
            scraper = Nitter(log_level=1, skip_instance_check=False, instance=instancia)
            data = scraper.get_tweets("MetroCDMX", mode='user', number=5)
            if data and 'tweets' in data:
                for t in data['tweets']:
                    txt = t['text'].lower()
                    if any(p in txt for p in PALABRAS_CLAVE) and not any(i in txt for i in IGNORAR):
                        if "m" in t['date'] or "1h" in t['date']:
                             tag_linea = detectar_lineas(txt)
                             incidentes.append(f"🚨 <b>AVISO OFICIAL:</b> {t['text']}{tag_linea}\n🔗 <a href='{t['link']}'>Ver Tweet</a>")
                break 
        except: continue

    return incidentes

def verificar_horario_servicio(ahora):
    dia = ahora.weekday(); hora = ahora.hour
    if dia <= 4 and hora == 5: return "🚇 <b>INICIO DE SERVICIO</b>\n──────────────────\nLa red del Metro inicia operaciones."
    elif dia == 5 and hora == 6: return "🚇 <b>INICIO DE SERVICIO (SÁBADO)</b>\n──────────────────\nInicia operación de fin de semana."
    elif dia == 6 and hora == 7: return "🚇 <b>INICIO DE SERVICIO (DOMINGO)</b>\n──────────────────\nServicio dominical iniciado."
    elif hora == 0: return "💤 <b>CIERRE DE SERVICIO</b>\n──────────────────\nOperaciones concluidas por hoy."
    return None

def main():
    tz_mx = pytz.timezone('America/Mexico_City')
    ahora = datetime.now(tz_mx)
    print(f"🏁 Escaneo iniciado: {ahora}")
    
    enviar_telegram("📡 <i>Conectando con la red de movilidad y analizando reportes ciudadanos...</i>")
    
    msg = verificar_horario_servicio(ahora)
    if msg: enviar_telegram(msg); return

    reportes = revisar_incidentes(ahora)
    if reportes:
        un = list(dict.fromkeys(reportes))
        h = ahora.strftime('%I:%M %p')
        enviar_telegram(f"🚨 <b>INCIDENCIAS DETECTADAS ({h})</b>\n──────────────────\n" + "\n\n".join(un))
    else:
        print("✅ Todo normal.")

if __name__ == "__main__":
    main()
