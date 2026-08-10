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
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Error al enviar mensaje a Telegram: {e}")

def obtener_alertas():
    url = f"https://apitransporte.buenosaires.gob.ar/subtes/serviceAlerts?client_id={CLIENT_ID}&client_secret={CLIENT_SECRET}"
    
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers, timeout=15)
    
    if response.status_code != 200:
        print(f"Error HTTP {response.status_code} al consultar API Transporte.")
        print(f"Respuesta del servidor: {response.text}")
        return None

    feed = gtfs_realtime_pb2.FeedMessage()
    try:
        feed.ParseFromString(response.content)
    except Exception as e:
        print(f"No se pudo parsear el feed protobuf: {e}")
        print(f"Contenido recibido (primeros 500 caracteres): {response.text[:500]}")
        return None

    alertas_linea_b = []

    for entity in feed.entity:
        if entity.HasField('alert'):
            aplica_linea_b = False
            for informed_entity in entity.alert.informed_entity:
                if informed_entity.HasField('route_id') and informed_entity.route_id in ["LineaB", "B", "LINEA_B", "LineB", "3"]:
                    aplica_linea_b = True
                    break
            
            if aplica_linea_b:
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

    if estado_actual != estado_anterior:
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
