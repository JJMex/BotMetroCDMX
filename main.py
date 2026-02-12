import os
import time
import requests
import feedparser
import pytz
import re
import base64
from datetime import datetime, timedelta
from ntscraper import Nitter
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

# --- CONFIGURACIÓN ---
TOKEN = os.environ.get('TELEGRAM_TOKEN')
ID_GRUPO = os.environ.get('TELEGRAM_CHAT_ID') 
ID_CANAL = os.environ.get('TELEGRAM_CHANNEL_ID') 
DESTINATARIOS = [id_ for id_ in [ID_GRUPO, ID_CANAL] if id_]

# URL RSS (Ventana de 1 hora para frescura)
RSS_URL = "https://news.google.com/rss/search?q=Metro+CDMX+retraso+OR+falla+OR+caos+when:1h&hl=es-419&gl=MX&ceid=MX:es-419"

# Palabras Clave de Problemas
PALABRAS_CLAVE = ["retraso", "marcha lenta", "falla", "desalojo", "humo", "detenido", "caos", "lento", "espera", "sin servicio", "colapso", "afectaciones", "avance", "bloqueo"]
# Palabras de Solución (Para cambiar el semáforo)
PALABRAS_SOLUCION = ["restablece", "normal", "agiliza", "solucionado", "continuo", "reanuda"]
IGNORAR = ["buenos días", "cubrebocas", "tarjeta", "arte", "exposición", "domingos y días festivos", "cultura", "museo"]

MAPA_LINEAS = {
    "1": "🩷 L1 (Rosa)", "uno": "🩷 L1 (Rosa)", "rosa": "🩷 L1 (Rosa)",
    "2": "💙 L2 (Azul)", "dos": "💙 L2 (Azul)", "azul": "💙 L2 (Azul)",
    "3": "💚 L3 (Verde)", "tres": "💚 L3 (Verde)", "verde": "💚 L3 (Verde)",
    "4": "🩵 L4 (Cian)", "cuatro": "🩵 L4 (Cian)", "cian": "🩵 L4 (Cian)",
    "5": "💛 L5 (Amarilla)", "cinco": "💛 L5 (Amarilla)", "amarilla": "💛 L5 (Amarilla)",
    "6": "❤️ L6 (Roja)", "seis": "❤️ L6 (Roja)", "roja": "❤️ L6 (Roja)",
    "7": "🧡 L7 (Naranja)", "siete": "🧡 L7 (Naranja)", "naranja": "🧡 L7 (Naranja)",
    "8": "💚 L8 (Verde)", "ocho": "💚 L8 (Verde)", 
    "9": "🤎 L9 (Café)", "nueve": "🤎 L9 (Café)", "café": "🤎 L9 (Café)",
    "a": "💜 LA (Férrea)", "férrea": "💜 LA (Férrea)",
    "b": "🩶 LB (Gris)", "gris": "🩶 LB (Gris)",
    "12": "💛 L12 (Dorada)", "doce": "💛 L12 (Dorada)", "dorada": "💛 L12 (Dorada)"
}

# Inicializador de Camuflaje
ua = UserAgent()

def get_headers():
    """Genera una identidad falsa aleatoria para cada petición."""
    return {
        'User-Agent': ua.random,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
        'Referer': 'https://www.google.com/'
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

def analizar_sentimiento(texto):
    """Determina si la noticia es mala (retraso) o buena (solución)."""
    texto = texto.lower()
    if any(p in texto for p in PALABRAS_SOLUCION):
        return "✅" # Verde: Problema resuelto
    return "🚨" # Rojo: Alerta activa

def detectar_lineas(texto):
    texto = texto.lower()
    detectadas = set()
    for clave, nombre in MAPA_LINEAS.items():
        patrones = [f"línea {clave}", f"linea {clave}", f"l{clave} ", f"l-{clave}", f"la {clave} "]
        if len(clave) < 3: patrones = [f"línea {clave}", f"linea {clave}", f"l-{clave}"]
        if any(p in texto for p in patrones):
            detectadas.add(nombre)
    
    if detectadas:
        lista = sorted(list(detectadas))
        return "\n⚠️ <b>AFECTACIÓN:</b> " + ", ".join(lista)
    return ""

def resolver_redireccion_google(url_inicial):
    """
    Motor de resolución de enlaces con Filtro Anti-Basura.
    """
    try:
        session = requests.Session()
        # Usamos identidad falsa
        response = session.get(url_inicial, headers=get_headers(), timeout=10, allow_redirects=True)
        
        # LISTA NEGRA: Dominios que NO son noticias
        basura_domains = [
            "google", "gstatic", "youtube", "blogger", "analytics", "doubleclick", 
            "facebook", "twitter", "instagram", "cloudflare", "w3.org", "schema.org",
            "googletagmanager", "g.co", "goo.gl", "pinterest", "tiktok", "microsoft"
        ]
        
        # Si seguimos atrapados en Google, buscamos la salida
        if "google" in response.url:
            print("   ⚠️ URL Ofuscada. Iniciando extracción quirúrgica...")
            
            # 1. BÚSQUEDA REGEX (Busca cualquier http que no sea google)
            urls_candidatas = re.findall(r'(https?:\/\/[^"\s<>\\]+)', response.text)
            
            mejor_candidato = None
            
            for url in urls_candidatas:
                # Filtros de limpieza
                if any(b in url for b in basura_domains): continue # Es basura
                if len(url) < 25: continue # Es muy corta
                if url.endswith(('.png', '.jpg', '.svg', '.gif', '.js', '.css')): continue # Es un archivo
                
                # Si pasa los filtros, es probable que sea la noticia
                print(f"   🎯 Candidato Válido: {url[:60]}...")
                return session.get(url, headers=get_headers(), timeout=10)

        return response 
        
    except Exception as e:
        print(f"   ❌ Error resolviendo: {e}")
        return None

def espiar_noticia_completa(url):
    try:
        response = resolver_redireccion_google(url)
        
        if response and response.status_code == 200:
            print(f"   ↳ Leyendo sitio real: {response.url[:40]}...")
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Limpieza profunda del HTML
            for tag in soup(["script", "style", "nav", "footer", "header", "aside", "iframe", "form"]):
                tag.extract()
                
            textos = soup.find_all(['p', 'h1', 'h2', 'article'])
            texto_completo = " ".join([t.get_text() for t in textos])
            return texto_completo
    except: pass
    return ""

def revisar_incidentes(ahora):
    incidentes = []
    
    # --- GOOGLE NEWS ---
    try:
        print("🔎 Analizando Noticias...")
        feed = feedparser.parse(RSS_URL)
        limite = ahora - timedelta(minutes=65)
        
        for e in feed.entries:
            if hasattr(e, 'published_parsed'):
                f = datetime(*e.published_parsed[:6], tzinfo=pytz.utc).astimezone(ahora.tzinfo)
                if f > limite:
                    titulo = e.title
                    
                    if any(p in titulo.lower() for p in PALABRAS_CLAVE):
                        print(f"👉 Analizando: {titulo[:40]}...")
                        
                        # 1. Detectar Líneas
                        tag_linea = detectar_lineas(titulo)
                        if not tag_linea:
                            print("   🕵️ Activando escaneo profundo...")
                            texto_web = espiar_noticia_completa(e.link)
                            tag_linea = detectar_lineas(texto_web)
                            if tag_linea: print(f"   ✅ Líneas detectadas: {tag_linea}")
                            else: print("   ❌ No se encontraron líneas.")
                        
                        # 2. Analizar Sentimiento (Rojo o Verde)
                        emoji_estado = analizar_sentimiento(titulo)
                        
                        incidentes.append(f"{emoji_estado} <b>REPORTE:</b> {titulo}{tag_linea}\n🔗 <a href='{e.link}'>Ver Nota</a>")
    except Exception as e: print(f"Error RSS: {e}")

    # --- TWITTER (Nitter) ---
    instancias = ["nitter.privacydev.net", "nitter.net", "nitter.cz"]
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
                             emoji_estado = analizar_sentimiento(txt)
                             incidentes.append(f"{emoji_estado} <b>AVISO OFICIAL:</b> {t['text']}{tag_linea}\n🔗 <a href='{t['link']}'>Ver Tweet</a>")
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
    
    # Ping de conexión
    enviar_telegram("📡 <i>Conectando con la red de movilidad y analizando reportes ciudadanos...</i>")
    time.sleep(1) # Pequeña pausa
    
    msg = verificar_horario_servicio(ahora)
    if msg: enviar_telegram(msg); return

    reportes = revisar_incidentes(ahora)
    if reportes:
        un = list(dict.fromkeys(reportes))
        h = ahora.strftime('%I:%M %p')
        enviar_telegram(f"📢 <b>ACTUALIZACIÓN ({h})</b>\n──────────────────\n" + "\n\n".join(un))
    else:
        # Mensaje de normalidad
        enviar_telegram("✅ <b>Estado del Metro:</b> Sin reportes críticos en la última hora.\n<i>Sistema operando con normalidad.</i>")
        print("✅ Todo normal.")

if __name__ == "__main__":
    main()
