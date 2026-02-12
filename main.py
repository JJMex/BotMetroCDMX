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

# Desactivar advertencias de SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- CONFIGURACIÓN ---
TOKEN = os.environ.get('TELEGRAM_TOKEN')
ID_GRUPO = os.environ.get('TELEGRAM_CHAT_ID') 
ID_CANAL = os.environ.get('TELEGRAM_CHANNEL_ID') 
DESTINATARIOS = [id_ for id_ in [ID_GRUPO, ID_CANAL] if id_]

RSS_URL = "https://news.google.com/rss/search?q=Metro+CDMX+retraso+OR+falla+OR+caos+when:1h&hl=es-419&gl=MX&ceid=MX:es-419"

# Diccionario de causas para dar contexto
CAUSAS = {
    "retraso": "Retrasos", "lento": "Marcha Lenta", "lenta": "Marcha Lenta",
    "falla": "Falla Técnica", "avería": "Avería", "desalojo": "Desalojo de Tren",
    "humo": "Presencia de Humo", "fuego": "Conato de Incendio", "quemado": "Olor a Quemado",
    "zapatas": "Zapatas Pegadas", "lluvia": "Lluvia / Marcha de Seguridad", 
    "mojado": "Lluvia", "caos": "Aglomeración Alta", "colapso": "Colapso",
    "espera": "Tiempos de Espera Altos", "detenido": "Tren Detenido", 
    "suicida": "Persona en Vías", "arrollado": "Accidente en Vías", "corte": "Corte de Corriente"
}

PALABRAS_CLAVE = list(CAUSAS.keys()) + ["afectaciones", "avance", "bloqueo", "cerradas", "servicio"]
PALABRAS_SOLUCION = ["restablece", "normal", "agiliza", "solucionado", "continuo", "reanuda", "opera con normalidad"]
IGNORAR = ["buenos días", "cubrebocas", "tarjeta", "arte", "exposición", "domingos y días festivos", "cultura", "museo"]

FIRMA = "\n\n— 🤖 <i>JJMex Bot</i>"

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

ua = UserAgent()

def get_headers():
    return {
        'User-Agent': ua.random,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
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
            except: time.sleep(1)

def analizar_sentimiento(texto):
    texto = texto.lower()
    if any(p in texto for p in PALABRAS_SOLUCION): return "✅" 
    return "🚨"

def analizar_detalle_lineas(texto):
    """
    Analiza el texto buscando líneas y asocia la CAUSA más cercana.
    Retorna una lista de strings formateados: "⚠️ L3 (Verde): Marcha Lenta"
    """
    texto = texto.lower()
    # Dividimos por frases para no mezclar problemas de una línea con otra
    frases = re.split(r'[.;\n]', texto) 
    
    reportes_detectados = {} # Usamos dict para evitar duplicados de líneas

    for frase in frases:
        if len(frase) < 10: continue # Ignorar frases muy cortas
        
        lineas_en_frase = []
        # 1. Detectar qué líneas se mencionan en esta frase específica
        for clave, nombre in MAPA_LINEAS.items():
            patrones = [f"línea {clave}", f"linea {clave}", f"l{clave} ", f"l-{clave}", f"la {clave} "]
            if len(clave) < 3: patrones = [f"línea {clave}", f"linea {clave}", f"l-{clave}"]
            
            if any(p in frase for p in patrones):
                lineas_en_frase.append(nombre)
        
        # 2. Si hay líneas, buscar la causa en la MISMA frase
        if lineas_en_frase:
            causas_encontradas = []
            for k, v in CAUSAS.items():
                if k in frase:
                    causas_encontradas.append(v)
            
            # Formatear el reporte
            causa_str = ", ".join(list(set(causas_encontradas))) if causas_encontradas else "Posible Afectación"
            
            for linea in lineas_en_frase:
                # Prioridad: Si ya detectamos algo grave, lo mantenemos. Si es "Posible", lo sobreescribimos.
                if linea not in reportes_detectados or "Posible" in reportes_detectados[linea]:
                    reportes_detectados[linea] = causa_str

    # Convertir a lista formateada
    resultado = []
    if reportes_detectados:
        items_ordenados = sorted(reportes_detectados.items())
        for nombre, problema in items_ordenados:
            resultado.append(f"⚠️ <b>{nombre}:</b> {problema}")
            
    return "\n".join(resultado) if resultado else ""

def resolver_redireccion_google(url_inicial, fuente_nombre=""):
    try:
        session = requests.Session()
        response = session.get(url_inicial, headers=get_headers(), timeout=15, allow_redirects=True, verify=False)
        
        basura = ["google", "gstatic", "youtube", "blogger", "analytics", "doubleclick", 
                  "facebook", "twitter", "instagram", "cloudflare", "w3.org", "schema.org", "googletagmanager"]
        
        if "google" in response.url:
            print(f"   ⚠️ URL Ofuscada. Buscando fuente: '{fuente_nombre}'...")
            fuente_clean = fuente_nombre.lower().replace(" ", "").replace("tv", "").replace("noticias", "")
            if len(fuente_clean) < 3: fuente_clean = "xyz_no_match"
            
            raw_urls = re.findall(r'(https?:\/\/[^"\s<>\\]+)', response.text)
            candidato_fuente = None
            candidato_generico = None
            
            for raw_url in raw_urls:
                url = unquote(raw_url).replace("\\u0026", "&").replace("\\", "")
                if any(b in url for b in basura): continue
                if len(url) < 25: continue
                if url.endswith(('.png', '.jpg', '.css', '.js', '.ico', '.woff')): continue
                
                if fuente_clean in url.lower():
                    candidato_fuente = url
                    break
                if not candidato_generico: candidato_generico = url
            
            url_final = candidato_fuente if candidato_fuente else candidato_generico
            if url_final:
                return session.get(url_final, headers=get_headers(), timeout=15, verify=False)
        return response 
    except Exception as e: return None

def espiar_noticia_completa(url, fuente_nombre=""):
    try:
        response = resolver_redireccion_google(url, fuente_nombre)
        if response and response.status_code == 200:
            print(f"   ↳ Leyendo sitio real: {response.url[:50]}...")
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # JSON-LD (Prioridad Alta)
            scripts = soup.find_all('script', type='application/ld+json')
            for script in scripts:
                if script.string:
                    try:
                        data = json.loads(script.string)
                        if isinstance(data, list): data = data[0]
                        if 'articleBody' in data: return data['articleBody']
                    except: continue

            # Scraping HTML
            for tag in soup(["script", "style", "nav", "footer", "header", "aside", "iframe", "form", "noscript", "ads"]):
                tag.extract()
            textos = soup.find_all(['p', 'h1', 'h2', 'h3', 'li', 'article'])
            textos_limpios = [t.get_text().strip() for t in textos if len(t.get_text().strip()) > 20]
            return " ".join(textos_limpios)
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
                    # IMPORTANTE: Usamos el resumen del RSS también, no solo el título
                    resumen = e.summary if hasattr(e, 'summary') else ""
                    fuente = e.source.title if hasattr(e, 'source') else ""
                    
                    texto_analisis = f"{titulo} {resumen}"
                    
                    if any(p in texto_analisis.lower() for p in PALABRAS_CLAVE):
                        print(f"👉 Analizando ({fuente}): {titulo[:30]}...")
                        
                        # 1. Intentar detectar con Título + Resumen (Rápido)
                        info_lineas = analizar_detalle_lineas(texto_analisis)
                        
                        # 2. Si no es suficiente, Espiar Web (Profundo)
                        if not info_lineas:
                            print("   🕵️ Activando escaneo profundo...")
                            texto_web = espiar_noticia_completa(e.link, fuente)
                            # Analizamos TODO junto: Título + Resumen + Web
                            info_lineas = analizar_detalle_lineas(texto_analisis + " " + texto_web)
                            
                        if info_lineas:
                            print(f"   ✅ Detectado: {info_lineas}")
                        else:
                            print("   ❌ No se detectaron líneas específicas.")

                        emoji_estado = analizar_sentimiento(titulo)
                        
                        # Construcción del Mensaje Rico en Datos
                        cuerpo = f"{emoji_estado} <b>REPORTE:</b> {titulo}\n"
                        if info_lineas:
                            cuerpo += f"\n{info_lineas}\n" # Aquí insertamos el detalle: "L3: Humo"
                        
                        cuerpo += f"🔗 <a href='{e.link}'>Ver Nota Completa</a>"
                        incidentes.append(cuerpo)

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
                             info_lineas = analizar_detalle_lineas(txt)
                             emoji_estado = analizar_sentimiento(txt)
                             
                             cuerpo = f"{emoji_estado} <b>AVISO OFICIAL:</b> {t['text']}\n"
                             if info_lineas: cuerpo += f"\n{info_lineas}\n"
                             cuerpo += f"🔗 <a href='{t['link']}'>Ver Tweet</a>"
                             incidentes.append(cuerpo)
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
    time.sleep(1)
    
    msg = verificar_horario_servicio(ahora)
    if msg: enviar_telegram(msg + FIRMA); return

    reportes = revisar_incidentes(ahora)
    if reportes:
        un = list(dict.fromkeys(reportes))
        h = ahora.strftime('%I:%M %p')
        enviar_telegram(f"📢 <b>ACTUALIZACIÓN ({h})</b>\n──────────────────\n" + "\n\n".join(un) + FIRMA)
    else:
        enviar_telegram("✅ <b>Estado del Metro:</b> Sin reportes críticos en la última hora.\n<i>Sistema operando con normalidad.</i>" + FIRMA)
        print("✅ Todo normal.")

if __name__ == "__main__":
    main()
