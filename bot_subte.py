import os
import re
import requests
from google.transit import gtfs_realtime_pb2

CLIENT_ID = os.environ.get("BA_CLIENT_ID")
CLIENT_SECRET = os.environ.get("BA_CLIENT_SECRET")
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

STATE_FILE = "ultimo_estado.txt"

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}
    try:
        r = requests.post(url, json=payload, timeout=10)
        print(f"Respuesta Telegram: {r.status_code} - {r.text}")
    except Exception as e:
        print(f"Error enviando a Telegram: {e}")

def obtener_alertas():
    url = f"https://apitransporte.buenosaires.gob.ar/subtes/serviceAlerts?client_id={CLIENT_ID}&client_secret={CLIENT_SECRET}"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    response = requests.get(url, headers=headers, timeout=15)
    if response.status_code != 200:
        print(f"Error HTTP {response.status_code} al consultar la API.")
        return None

    content = response.content

    # Intento 1: Parseo Protobuf directo
    feed = gtfs_realtime_pb2.FeedMessage()
    parsed_ok = False
    
    # Probamos parsear directo o buscando dónde empieza el mensaje de Protobuf
    for offset in range(0, min(50, len(content))):
        try:
            feed.ParseFromString(content[offset:])
            parsed_ok = True
            break
        except Exception:
            continue

    alertas_linea_b = []

    if parsed_ok:
        print("Protobuf parseado con éxito.")
        for entity in feed.entity:
            if entity.HasField('alert'):
                texto_alerta = ""
                if entity.alert.header_text.translation:
                    texto_alerta = entity.alert.header_text.translation[0].text
                elif entity.alert.description_text.translation:
                    texto_alerta = entity.alert.description_text.translation[0].text

                # Verificar si aplica a la Línea B
                es_b = False
                if 'LineaB' in entity.id or 'linea_b' in entity.id.lower():
                    es_b = True
                for informed in entity.alert.informed_entity:
                    if informed.HasField('route_id') and 'LineaB' in informed.route_id:
                        es_b = True
                        break

                if es_b and texto_alerta:
                    alertas_linea_b.append(texto_alerta)
    else:
        print("Fallback a extracción directa por texto/expresión regular.")
        # Intento 2: Búsqueda de patrones en el contenido binario si falla Protobuf
        texto_raw = content.decode('utf-8', errors='ignore')
        
        # Buscar bloques de texto asociados a LineaB
        coincidencias = re.findall(r'Alert_LineaB.*?(?=Alert_Linea|\Z)', texto_raw, re.DOTALL)
        for coincidencia in coincidencias:
            # Extraer textos legibles dentro del bloque
            textos_legibles = re.findall(r'[A-ZÁÉÍÓÚÑa-záéíóúñ0-9\s\,\.\:\-\/]{10,}', coincidencia)
            limpios = [t.strip() for t in textos_legibles if "Alert_Linea" not in t and len(t.strip()) > 10]
            if limpios:
                alertas_linea_b.append(" - ".join(limpios))

    if alertas_linea_b:
        return " | ".join(set(alertas_linea_b))
    else:
        return "NORMAL"

def main():
    estado_actual = obtener_alertas()
    if estado_actual is None:
        print("No se pudo obtener el estado del subte.")
        return

    estado_anterior = ""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            estado_anterior = f.read().strip()

    print(f"Estado anterior: '{estado_anterior}'")
    print(f"Estado actual: '{estado_actual}'")

    # Enviar si cambió el estado o si es la primera ejecución
    if estado_actual != estado_anterior or not os.path.exists(STATE_FILE):
        if estado_actual == "NORMAL":
            mensaje = "🟢 **Línea B - Servicio Normalizado / Sin Alertas**"
        else:
            mensaje = f"🚨 **ALERTA LÍNEA B** 🚨\n\n{estado_actual}"
        
        enviar_telegram(mensaje)

        with open(STATE_FILE, "w", encoding="utf-8") as f:
            f.write(estado_actual)
    else:
        print("Sin cambios en el servicio. No se envía alerta.")

if __name__ == "__main__":
    main()
