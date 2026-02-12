import os
import time
import requests
import feedparser
import pytz
from datetime import datetime, timedelta
from ntscraper import Nitter
from bs4 import BeautifulSoup  # Nueva herramienta de espionaje

# --- CONFIGURACIÓN ---
TOKEN = os.environ.get('TELEGRAM_TOKEN')
ID_GRUPO = os.environ.get('TELEGRAM_CHAT_ID') 
ID_CANAL = os.environ.get('TELEGRAM_CHANNEL_ID') 
DESTINATARIOS = [id_ for id_ in [ID_GRUPO, ID_CANAL] if id_]

RSS_URL = "https://news.google.com/rss/search?q=Metro+CDMX+retraso+OR+falla+OR+caos+when:1h&hl=es-419&gl=MX&ceid=MX:es-419"
PALABRAS_CLAVE = ["retraso", "marcha lenta", "falla", "desalojo", "humo", "detenido", "caos", "lento", "espera", "sin servicio", "colapso", "afectaciones", "avance"]
IGNORAR = ["buenos días", "cubrebocas", "tarjeta", "arte", "exposición", "domingos y días festivos", "cultura"]

# --- DICCIONARIO MEJORADO (Detecta Colores y Alias) ---
MAPA_LINEAS = {
    # Números
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
                r = requests.post(url, data=data, timeout=10)
                if r.status_code == 200: break
                time.sleep(1)
            except: time.sleep(1)

def detectar_lineas(texto):
    """Analiza texto buscando nombres, números o COLORES de líneas."""
    texto = texto.lower()
    detectadas = set()
    
    for clave, nombre in MAPA_LINEAS.items():
        # Buscamos: "Línea 1", "L1", "La Rosa", "Linea Azul"
        patrones = [f"línea {clave}", f"linea {clave}", f"l{clave} ", f"l-{clave}", f"la {clave}"]
        
        # Filtro estricto para letras y colores cortos para no confundir
        if len(clave) < 3: 
             patrones = [f"línea {clave}", f"linea {clave}", f"l-{clave}"]
             
        if any(p in texto for p in patrones):
            detectadas.add(nombre)
            
    if detectadas:
        # Convertimos el set a lista y ordenamos para que se vea bien
        lista = sorted(list(detectadas))
        return "\n⚠️ <b>AFECTACIÓN CONFIRMADA:</b> " + ", ".join(lista)
    return ""

def espiar_noticia_completa(url):
    """
    MODO ESPÍA: Entra a la web, descarga el texto y busca las líneas ahí.
    """
    try:
        # Nos hacemos pasar por un navegador real
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=4)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            # Extraemos todos los párrafos de la noticia
            parrafos = soup.find_all('p')
            texto_completo = " ".join([p.get_text() for p in parrafos])
            return texto_completo
    except:
        return ""
    return ""

def revisar_incidentes(ahora):
    incidentes = []
    
    # 1. GOOGLE NEWS (Con Modo Espía)
    try:
        feed = feedparser.parse(RSS_URL)
        limite = ahora - timedelta(minutes=65)
        for e in feed.entries:
            if hasattr(e, 'published_parsed'):
                f = datetime(*e.published_parsed[:6], tzinfo=pytz.utc).astimezone(ahora.tzinfo)
                if f > limite:
                    titulo = e.title.lower()
                    
                    if any(p in titulo for p in PALABRAS_CLAVE):
                        # Paso 1: Intentamos detectar en el título
                        tag_linea = detectar_lineas(titulo)
                        
                        # Paso 2: Si NO encontramos líneas en el título, activamos el ESPÍA
                        if not tag_linea:
                            print(f"🕵️ Activando espía para: {e.title[:20]}...")
                            texto_profundo = espiar_noticia_completa(e.link)
                            tag_linea = detectar_lineas(texto_profundo)
                        
                        incidentes.append(f"📰 <b>NOTICIA:</b> {e.title}{tag_linea}\n🔗 <a href='{e.link}'>Ver Nota</a>")
    except Exception as e: print(f"Error RSS: {e}")

    # 2. TWITTER
    # (Código simplificado de Nitter para ahorrar espacio, usando la mejor instancia)
    instancias = ["nitter.net", "nitter.privacydev.net", "nitter.cz"]
    for instancia in instancias:
        try:
            scraper = Nitter(log_level=1, skip_instance_check=False, instance=instancia)
            data = scraper.get_tweets("MetroCDMX", mode='user', number=5)
            if data and 'tweets' in data:
                for t in data['tweets']:
                    txt = t['text'].lower()
                    # Filtro de fecha aproximada (hoy)
                    if any(p in txt for p in PALABRAS_CLAVE) and not any(i in txt for i in IGNORAR):
                        if "m" in t['date'] or "1h" in t['date']:
                             tag_linea = detectar_lineas(txt)
                             incidentes.append(f"🚨 <b>AVISO OFICIAL:</b> {t['text']}{tag_linea}\n🔗 <a href='{t['link']}'>Ver Tweet</a>")
                break # Si funcionó, dejamos de probar instancias
        except: continue

    return incidentes

def main():
    tz_mx = pytz.timezone('America/Mexico_City')
    ahora = datetime.now(tz_mx)
    
    # Mensaje de conexión
    enviar_telegram("📡 <i>Conectando con la red de movilidad y analizando reportes ciudadanos...</i>")
    
    # Revisión de incidentes
    reportes = revisar_incidentes(ahora)
    
    if reportes:
        reportes_unicos = list(dict.fromkeys(reportes))
        hora_str = ahora.strftime('%I:%M %p')
        header = f"🚨 <b>INCIDENCIAS DETECTADAS ({hora_str})</b>\n──────────────────\n"
        enviar_telegram(header + "\n\n".join(reportes_unicos))
    else:
        # Opcional: Descomentar para aviso de normalidad
        # enviar_telegram("✅ Sin reportes graves por el momento.")
        print("✅ Todo normal.")

if __name__ == "__main__":
    main()
