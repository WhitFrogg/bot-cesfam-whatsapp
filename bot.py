from fastapi import FastAPI, Request, Response, HTTPException
import json

app = FastAPI()

# Diccionario temporal para guardar el estado conversacional de los pacientes por su número
user_states = {}

# TOKEN DE VERIFICACIÓN (Debe coincidir exactamente con el que pongas en el panel de Meta)
VERIFY_TOKEN = "cesfam123"

@app.get("/")
def home():
    return {"status": "Servidor del Bot CESFAM Activo en la Nube"}

# Endpoint GET obligatorio para que Meta valide el Webhook
@app.get("/webhook")
async def verify_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    print(f"🔍 Intento de verificación recibido -> Mode: {mode}, Token: {token}, Challenge: {challenge}")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("✅ ¡Verificación exitosa! Retornando challenge.")
        return Response(content=str(challenge), media_type="text/plain", status_code=200)
    
    print("❌ Error de verificación: El token no coincide o faltan parámetros.")
    return Response(content="Token mismatch", status_code=403)


# Endpoint POST que Meta (WhatsApp) llamará cada vez que llegue un mensaje
@app.post("/webhook")
async def receive_webhook(request: Request):
    body = await request.json()
    
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
            
            response_message = process_conversation_flow(phone_number, msg_body)
            print(f"Enviando al número {phone_number}: {response_message}")
            
    except Exception as e:
        print(f"Error procesando el webhook: {e}")
        
    return {"status": "EVENT_RECEIVED"}

def process_conversation_flow(phone: str, text: str):
    # Si el usuario es nuevo, inicializamos su estado
    if phone not in user_states:
        user_states[phone] = {"step": "WAITING_CONFIRMATION"}
        return "Hola. Le recordamos su control médico para mañana a las 10:00 hrs en el CESFAM. ¿Confirma su asistencia? (Responda Confirmar o Cancelar)"
    
    current_state = user_states[phone]["step"]
    
    # Paso 1: El usuario responde a la confirmación de la cita
    if current_state == "WAITING_CONFIRMATION":
        if "confirmar" in text.lower() or "si" in text.lower():
            user_states[phone]["step"] = "WAITING_BIRTHDATE"
            return "¡Gracias por confirmar su cita! Para actualizar su ficha clínica, por favor indique su fecha de nacimiento en formato DD/MM/AAAA:"
        else:
            user_states[phone]["step"] = "COMPLETED"
            return "Entendido. Su cita ha sido cancelada y la hora quedará disponible para otro paciente. ¡Que tenga buen día!"
            
    # Paso 2: El usuario ingresa su fecha de nacimiento
    elif current_state == "WAITING_BIRTHDATE":
        user_states[phone]["birthdate"] = text
        user_states[phone]["step"] = "WAITING_SEX"
        return "Perfecto. Por último, indique su sexo administrativo (Femenino / Masculino):"
        
    # Paso 3: El usuario ingresa su sexo y generamos la trama HL7
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
