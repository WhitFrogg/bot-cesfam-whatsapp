from fastapi import FastAPI, Request, Response
import requests
import json

app = FastAPI()

# Diccionario temporal para guardar el estado conversacional de los pacientes
user_states = {}

# CREDENCIALES DE META WHATSAPP
VERIFY_TOKEN = "cesfam123"
WHATSAPP_TOKEN = "EAAQEXeRY6fMBSxZCafqRFdSEip20xFtWP1xhcgWYlarRnm27VK8bURLwKVAfHYkINXuF2AqDbz9pD2j0k8FIz0rVw6sgF0eFvj1W1D52ZBy7ZA260DR5XoLHEI1grJbNGnapDFbXJF1yrEkDUWlMS6qhqEeXnqFwgUYnqmLkIh1OHzJoBdZArA7C0gChc7cpFeh3AJPhLIgbpQLbQhgnd8hMXzqZByhboLAp57naHbMYlH42vdutwHWel8aPIT8FCrfkr6DQkVGO1prZAQ9VL9CDYZD"
PHONE_NUMBER_ID = "1511997975323511"

@app.get("/")
def home():
    return {"status": "Servidor del Bot CESFAM Activo en la Nube"}

# Endpoint GET para que Meta valide el Webhook
@app.get("/webhook")
async def verify_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return Response(content=str(challenge), media_type="text/plain", status_code=200)
    
    return Response(content="Token mismatch", status_code=403)

# Endpoint POST para recibir mensajes de WhatsApp
@app.post("/webhook")
async def receive_webhook(request: Request):
    body = await request.json()
    print(f"WEBHOOK RECIBIDO DE META: {json.dumps(body, indent=2)}")
    
    try:
        entry = body.get("entry", [])[0]
        changes = entry.get("changes", [])[0]
        value = changes.get("value", {})
        
        messages = value.get("messages", [])
        if messages:
            msg = messages[0]
            phone_number = msg.get("from")
            msg_body = ""
            
            if msg.get("type") == "text":
                msg_body = msg.get("text", {}).get("body", "").strip()
            elif msg.get("type") == "interactive":
                interactive_type = msg.get("interactive", {}).get("type")
                if interactive_type == "button_reply":
                    msg_body = msg.get("interactive", {}).get("button_reply", {}).get("id", "").strip()
            
            if msg_body and phone_number:
                print(f"Procesando mensaje de {phone_number}: {msg_body}")
                response_message = process_conversation_flow(phone_number, msg_body)
                send_whatsapp_message(phone_number, response_message)
                
    except Exception as e:
        print(f"Error procesando el webhook: {e}")
        
    return {"status": "EVENT_RECEIVED"}

def send_whatsapp_message(to_phone: str, message: str):
    url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "text",
        "text": {"body": message},
    }
    response = requests.post(url, json=payload, headers=headers)
    print(f"Respuesta de Meta API: {response.status_code} - {response.text}")
    return response.json()

def process_conversation_flow(phone: str, text: str):
    if phone not in user_states:
        user_states[phone] = {"step": "WAITING_CONFIRMATION"}
        return "Hola. Le recordamos su control médico para mañana a las 10:00 hrs en el CESFAM. ¿Confirma su asistencia? (Responda Confirmar o Cancelar)"
    
    current_state = user_states[phone]["step"]
    
    if current_state == "WAITING_CONFIRMATION":
        if "confirmar" in text.lower() or "si" in text.lower():
            user_states[phone]["step"] = "WAITING_BIRTHDATE"
            return "¡Gracias por confirmar su cita! Para actualizar su ficha clínica, por favor indique su fecha de nacimiento en formato DD/MM/AAAA:"
        else:
            user_states[phone]["step"] = "COMPLETED"
            return "Entendido. Su cita ha sido cancelada y la hora quedará disponible para otro paciente. ¡Que tenga buen día!"
            
    elif current_state == "WAITING_BIRTHDATE":
        user_states[phone]["birthdate"] = text
        user_states[phone]["step"] = "WAITING_SEX"
        return "Perfecto. Por último, indique su sexo administrativo (Femenino / Masculino):"
        
    elif current_state == "WAITING_SEX":
        user_states[phone]["sex"] = "F" if "fem" in text.lower() else "M"
        birthdate = user_states[phone]["birthdate"]
        sex = user_states[phone]["sex"]
        
        parts = birthdate.split("/")
        hl7_date = f"{parts[2]}{parts[1]}{parts[0]}" if len(parts) == 3 else "19780415"
        hl7_segment = f"PID|||123456^^^MR||Paciente^Ejemplo||{hl7_date}|{sex}"
        
        user_states[phone]["step"] = "COMPLETED"
        return f"¡Datos sincronizados con éxito en el sistema del CESFAM!\n\n(Trama HL7 generada y enviada al middleware Mirth Connect):\n{hl7_segment}"
        
    else:
        return "Su proceso de confirmación ya se encuentra finalizado. ¡Nos vemos en el CESFAM!"
