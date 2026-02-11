# 🚇 Monitor Metro CDMX: Vigilancia de Red

![Python](https://img.shields.io/badge/Python-3.9-blue?style=flat&logo=python)
![Status](https://img.shields.io/badge/Status-Active-success)
![Metro](https://img.shields.io/badge/Sistema-STC%20Metro-orange)

Este bot supervisa en tiempo real el estado de operación del Sistema de Transporte Colectivo (Metro) de la Ciudad de México. Combina reportes oficiales de Twitter con noticias de última hora para detectar retrasos, fallas o cierres de estaciones de forma inmediata.

---

## 🧠 Inteligencia de Vigilancia

El bot utiliza un sistema de **Escaneo Híbrido** cada hora para garantizar la veracidad de la información:

1.  **Avisos Oficiales (Twitter):** Consulta la cuenta oficial `@MetroCDMX` mediante Nitter para capturar alertas de "Metro al momento".
2.  **Reportes Ciudadanos (Google News):** Rastrea noticias de última hora buscando incidentes reportados por usuarios o medios de comunicación que aún no figuran en los canales oficiales.
3.  **Filtro Selectivo:** Ignora publicaciones culturales, promocionales o de rutina para enfocarse exclusivamente en problemas de movilidad.

---

## ⚡ Funcionalidades Clave

* **⏰ Conciencia de Horario:** Reconoce los horarios de apertura diferenciados (Lunes-Viernes 5:00, Sábados 6:00 y Domingos 7:00) y el cierre de servicio a las 00:00.
* **📡 Reporte de Actividad:** Cada que el bot se activa, envía una notificación de conexión para confirmar que está analizando la red.
* **✅ Confirmación de Normalidad:** Si tras el análisis no se detectan fallas, el bot informa que el sistema trabaja con normalidad, brindando tranquilidad al usuario.
* **🚨 Alertas Detalladas:** Ante cualquier incidencia, envía el texto del reporte junto con un enlace directo a la fuente oficial o noticia para su verificación.

---

## 🚀 Instalación y Despliegue

El bot está diseñado para ejecutarse de forma gratuita en **GitHub Actions**.

### 1. Requisitos Previos
* Realizar un **Fork** de este repositorio.
* Configurar los secretos en `Settings > Secrets and variables > Actions`:
    * `TELEGRAM_TOKEN`: Obtenido mediante @BotFather.
    * `TELEGRAM_CHAT_ID`: Tu ID de chat personal o de grupo.

### 2. Automatización (Workflow)
El archivo `metro.yml` está configurado para despertar al bot **una vez cada hora** dentro del horario operativo del Metro (UTC 0-6, 11-23).

---

## 📸 Formato de Reportes

### Inicio de Servicio:
> 🚇 **INICIO DE SERVICIO**
> ──────────────────
> La red del Metro inicia operaciones. ¡Buen viaje!

### Estado Normal:
> 📡 _Conectando con la red de movilidad y analizando reportes ciudadanos..._
>
> ✅ **Estado del Metro:** Sin reportes de fallas o retrasos detectados en la última hora.
> _Sistema trabajando con normalidad._

### Alerta de Incidencia:
> 🚨 **INCIDENCIAS DETECTADAS (08:35 AM)**
> ──────────────────
> 🚨 **AVISO OFICIAL:** #AvisoMetro: Se retira un tren de la Línea 9 para revisión...
> 🔗 [Ver Tweet](https://twitter.com/MetroCDMX)

---

<p align="center">
  <i>Monitoreo constante para una movilidad inteligente. 🚈</i>
</p>
