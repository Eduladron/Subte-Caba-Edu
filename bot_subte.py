import os
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
        print(f"Respuesta de Telegram: {r.status_code} - {r.text}")
    except Exception as e:
        print(f"Error al enviar mensaje a Telegram: {e}")

def obtener_alertas():
    url = f"https://apitransporte.buenosaires.gob.ar/subtes/serviceAlerts?client_id={CLIENT_ID}&client_secret={CLIENT_SECRET}"
    
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers, timeout=15)
    
    if response.status_code != 200:
        print(f"Error HTTP {response.status_code} al consultar API Transporte.")
        return None

    content = response.content

    # Si la respuesta incluye encabezados adicionales de versión, recortamos hasta la primera entidad
    idx = content.find(b'\x0a')
    if idx != -1 and idx < 20:
        content = content[idx:]

    feed = gtfs_realtime_pb2.FeedMessage()
    try:
        feed.ParseFromString(content)
    except Exception as e:
        print(f"Error al parsear protobuf ajustado: {e}")
        return None

    alertas_linea_b = []

    for entity in feed.entity:
        if entity.HasField('alert'):
            es_linea_b = False
            
            # 1. Revisar IDs en informed_entity
            for informed in entity.alert.informed_entity:
                if informed.HasField('route_id') and 'LineaB' in informed.route_id:
                    es_linea_b = True
                    break
            
            # 2. Revisar si el ID de la alerta hace referencia a la Línea B
            if not es_linea_b and 'LineaB' in entity.id:
                es_linea_b = True

            if es_linea_b:
                header_text = ""
                if entity.alert.header_text.translation:
                    header_text = entity.alert.header_text.translation[0].text
                
                description_text = ""
                if entity.alert.description_text.translation:
                    description_text = entity.alert.description_text.translation[0].text

                texto = f"{header_text}\n{description_text}".strip()
                if texto:
                    alertas_linea_b.append(texto)

    if alertas_linea_b:
        return " | ".join(alertas_linea_b)
    else:
        return "NORMAL"

def main():
    estado_actual = obtener_alertas()
    if estado_actual is None:
        print("No se pudo obtener el estado.")
        return

    estado_anterior = ""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            estado_anterior = f.read().strip()

    print(f"Estado anterior: {estado_anterior}")
    print(f"Estado actual: {estado_actual}")

    # Enviar mensaje siempre en la primera ejecución o cuando cambie el estado
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
