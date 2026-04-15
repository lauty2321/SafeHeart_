"""
SafeClick Backend Server - Version Mejorada
Servidor HTTP con soporte para emergencias, tracking y envio de emails
"""

from http.server import HTTPServer, SimpleHTTPRequestHandler
import json
from urllib.parse import urlparse, parse_qs
import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

# Archivos de datos
DATA_FILE = "data.json"
EMERGENCY_LOG_FILE = "emergency_log.json"
TRACKING_LOG_FILE = "tracking_log.json"

class SafeClickHandler(SimpleHTTPRequestHandler):
    """Handler mejorado para SafeClick con soporte de tracking y email"""
    
    def _set_headers(self, status=200, content_type='application/json'):
        self.send_response(status)
        self.send_header('Content-type', content_type)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_OPTIONS(self):
        """Maneja preflight requests CORS"""
        self._set_headers()

    def do_GET(self):
        """Maneja peticiones GET"""
        parsed = urlparse(self.path)
        
        # Endpoint: Obtener configuracion
        if parsed.path == "/api/config":
            self._handle_get_config()
            return
        
        # Endpoint: Obtener historial de emergencias
        if parsed.path == "/api/history":
            self._handle_get_history()
            return
        
        # Endpoint: Obtener historial de tracking
        if parsed.path == "/api/tracking/history":
            self._handle_get_tracking_history()
            return
        
        # Endpoint: Estadisticas
        if parsed.path == "/api/stats":
            self._handle_get_stats()
            return
        
        # Servir archivos estaticos
        super().do_GET()

    def do_POST(self):
        """Maneja peticiones POST"""
        # Endpoint: Registrar emergencia
        if self.path == "/api/emergency":
            self._handle_emergency()
            return
        
        # Endpoint: Registrar punto de tracking
        if self.path == "/api/tracking":
            self._handle_tracking()
            return
        
        # Endpoint: Enviar email
        if self.path == "/api/send-email":
            self._handle_send_email()
            return
        
        self.send_error(404)

    def _handle_get_config(self):
        """Devuelve la configuracion de la app"""
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self._set_headers()
            self.wfile.write(json.dumps(data).encode())
        except FileNotFoundError:
            default_config = {
                "app": {
                    "name": "SafeClick",
                    "version": "2.0.0",
                    "description": "Emergencia en tu bolsillo - SMS automatico con tracking"
                },
                "defaultMessage": "EMERGENCIA! Necesito ayuda urgente. Hora: {TIME} | Bateria: {BATTERY}% | Ubicacion: {LOCATION}",
                "smsConfig": {
                    "maxLength": 160,
                    "encoding": "UTF-8",
                    "locationPlaceholder": "{LOCATION}",
                    "timePlaceholder": "{TIME}",
                    "batteryPlaceholder": "{BATTERY}"
                },
                "trackingConfig": {
                    "intervalSeconds": 10,
                    "durationMinutes": 3,
                    "maxPoints": 50
                },
                "features": {
                    "sms": True,
                    "whatsapp": True,
                    "email": True,
                    "push": True,
                    "gps": True,
                    "tracking": True,
                    "vibration": True,
                    "sound": True
                }
            }
            self._set_headers()
            self.wfile.write(json.dumps(default_config).encode())

    def _handle_get_history(self):
        """Devuelve el historial de emergencias"""
        try:
            logs = self._read_json_lines(EMERGENCY_LOG_FILE)
            self._set_headers()
            self.wfile.write(json.dumps(logs).encode())
        except Exception as e:
            self._set_headers(500)
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def _handle_get_tracking_history(self):
        """Devuelve el historial de tracking"""
        try:
            logs = self._read_json_lines(TRACKING_LOG_FILE)
            # Devolver los ultimos 100 puntos
            self._set_headers()
            self.wfile.write(json.dumps(logs[-100:]).encode())
        except Exception as e:
            self._set_headers(500)
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def _handle_get_stats(self):
        """Devuelve estadisticas de uso"""
        try:
            emergencies = self._read_json_lines(EMERGENCY_LOG_FILE)
            tracking_points = self._read_json_lines(TRACKING_LOG_FILE)
            
            stats = {
                "totalEmergencies": len(emergencies),
                "totalTrackingPoints": len(tracking_points),
                "lastEmergency": emergencies[-1]["timestamp"] if emergencies else None,
                "activeSince": emergencies[0]["timestamp"] if emergencies else None
            }
            
            self._set_headers()
            self.wfile.write(json.dumps(stats).encode())
        except Exception as e:
            self._set_headers(500)
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def _handle_emergency(self):
        """Registra una emergencia"""
        try:
            length = int(self.headers['Content-Length'])
            data = json.loads(self.rfile.read(length))
            
            log_entry = {
                "id": datetime.datetime.now().strftime("%Y%m%d%H%M%S%f"),
                "timestamp": datetime.datetime.now().isoformat(),
                "contacts": data.get("contacts", []),
                "location": data.get("location"),
                "message": data.get("message"),
                "time": data.get("time"),
                "battery": data.get("battery"),
                "channels": data.get("channels", {}),
                "status": "sent"
            }
            
            # Guardar en archivo
            self._append_json_line(EMERGENCY_LOG_FILE, log_entry)
            
            print(f"[EMERGENCIA] {log_entry['timestamp']} - Enviada a {len(log_entry['contacts'])} contactos")
            print(f"  Ubicacion: {log_entry['location']}")
            print(f"  Canales: {log_entry['channels']}")
            
            self._set_headers()
            self.wfile.write(json.dumps({
                "status": "ok",
                "id": log_entry["id"],
                "message": "Emergencia registrada correctamente"
            }).encode())
            
        except Exception as e:
            print(f"[ERROR] Error procesando emergencia: {e}")
            self._set_headers(500)
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def _handle_tracking(self):
        """Registra un punto de tracking"""
        try:
            length = int(self.headers['Content-Length'])
            data = json.loads(self.rfile.read(length))
            
            tracking_point = {
                "timestamp": data.get("timestamp", datetime.datetime.now().isoformat()),
                "lat": data.get("lat"),
                "lon": data.get("lon"),
                "accuracy": data.get("accuracy"),
                "server_time": datetime.datetime.now().isoformat()
            }
            
            # Guardar en archivo
            self._append_json_line(TRACKING_LOG_FILE, tracking_point)
            
            print(f"[TRACKING] {tracking_point['timestamp']} - Lat: {tracking_point['lat']}, Lon: {tracking_point['lon']}")
            
            self._set_headers()
            self.wfile.write(json.dumps({
                "status": "ok",
                "message": "Punto de tracking registrado"
            }).encode())
            
        except Exception as e:
            print(f"[ERROR] Error procesando tracking: {e}")
            self._set_headers(500)
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def _handle_send_email(self):
        """Envia emails de emergencia"""
        try:
            length = int(self.headers['Content-Length'])
            data = json.loads(self.rfile.read(length))
            
            contacts = data.get("contacts", [])
            message = data.get("message", "")
            location = data.get("location", "")
            time = data.get("time", "")
            
            # Filtrar contactos con email
            email_contacts = [c for c in contacts if c.get("email")]
            
            if not email_contacts:
                self._set_headers()
                self.wfile.write(json.dumps({
                    "status": "ok",
                    "message": "No hay contactos con email configurado"
                }).encode())
                return
            
            # Intentar enviar emails (requiere configuracion SMTP)
            emails_sent = 0
            smtp_host = os.environ.get("SMTP_HOST", "")
            smtp_port = int(os.environ.get("SMTP_PORT", "587"))
            smtp_user = os.environ.get("SMTP_USER", "")
            smtp_pass = os.environ.get("SMTP_PASS", "")
            
            if smtp_host and smtp_user and smtp_pass:
                try:
                    server = smtplib.SMTP(smtp_host, smtp_port)
                    server.starttls()
                    server.login(smtp_user, smtp_pass)
                    
                    for contact in email_contacts:
                        try:
                            msg = MIMEMultipart()
                            msg['From'] = smtp_user
                            msg['To'] = contact['email']
                            msg['Subject'] = "ALERTA DE EMERGENCIA - SafeClick"
                            
                            body = f"""
ALERTA DE EMERGENCIA

{message}

Hora: {time}
Ubicacion: {location}

Este mensaje fue enviado automaticamente por SafeClick.
                            """
                            
                            msg.attach(MIMEText(body, 'plain'))
                            server.send_message(msg)
                            emails_sent += 1
                            print(f"[EMAIL] Enviado a {contact['email']}")
                            
                        except Exception as e:
                            print(f"[ERROR] Error enviando email a {contact['email']}: {e}")
                    
                    server.quit()
                    
                except Exception as e:
                    print(f"[ERROR] Error conectando al servidor SMTP: {e}")
            else:
                print("[INFO] SMTP no configurado - emails no enviados")
            
            self._set_headers()
            self.wfile.write(json.dumps({
                "status": "ok",
                "emailsSent": emails_sent,
                "totalContacts": len(email_contacts)
            }).encode())
            
        except Exception as e:
            print(f"[ERROR] Error procesando envio de email: {e}")
            self._set_headers(500)
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def _read_json_lines(self, filename):
        """Lee un archivo JSON lines"""
        logs = []
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        logs.append(json.loads(line))
        except FileNotFoundError:
            pass
        return logs

    def _append_json_line(self, filename, data):
        """Agrega una linea JSON a un archivo"""
        with open(filename, 'a', encoding='utf-8') as f:
            f.write(json.dumps(data) + "\n")

    def log_message(self, format, *args):
        """Formato de log personalizado"""
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {format % args}")


def create_default_data():
    """Crea el archivo de datos por defecto si no existe"""
    if not os.path.exists(DATA_FILE):
        default_data = {
            "app": {
                "name": "SafeClick",
                "version": "2.0.0",
                "description": "Emergencia en tu bolsillo - SMS automatico con tracking en tiempo real"
            },
            "defaultMessage": "EMERGENCIA! Necesito ayuda urgente. Hora: {TIME} | Bateria: {BATTERY}% | Ubicacion: {LOCATION}",
            "smsConfig": {
                "maxLength": 160,
                "encoding": "UTF-8",
                "locationPlaceholder": "{LOCATION}",
                "timePlaceholder": "{TIME}",
                "batteryPlaceholder": "{BATTERY}"
            },
            "trackingConfig": {
                "intervalSeconds": 10,
                "durationMinutes": 3,
                "maxPoints": 50
            },
            "features": {
                "sms": True,
                "whatsapp": True,
                "email": True,
                "push": True,
                "gps": True,
                "tracking": True,
                "vibration": True,
                "sound": True
            },
            "exampleContacts": [
                {"id": "1", "name": "Mama", "phone": "+5491112345678", "email": "mama@email.com", "relationship": "Familiar"},
                {"id": "2", "name": "Papa", "phone": "+5491187654321", "email": "papa@email.com", "relationship": "Familiar"},
                {"id": "3", "name": "Hermano", "phone": "+5491155551234", "relationship": "Familiar"}
            ]
        }
        
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_data, f, indent=2, ensure_ascii=False)
        
        print(f"[INFO] Archivo {DATA_FILE} creado")


def run(port=8000):
    """Inicia el servidor"""
    create_default_data()
    
    server = HTTPServer(("", port), SafeClickHandler)
    print("=" * 50)
    print("  SAFECLICK SERVER v2.0")
    print("=" * 50)
    print(f"  Servidor corriendo en http://localhost:{port}")
    print(f"  API Endpoints:")
    print(f"    GET  /api/config          - Configuracion")
    print(f"    GET  /api/history         - Historial de emergencias")
    print(f"    GET  /api/tracking/history - Historial de tracking")
    print(f"    GET  /api/stats           - Estadisticas")
    print(f"    POST /api/emergency       - Registrar emergencia")
    print(f"    POST /api/tracking        - Registrar punto GPS")
    print(f"    POST /api/send-email      - Enviar email")
    print("=" * 50)
    print("  Presiona Ctrl+C para detener el servidor")
    print("=" * 50)
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[INFO] Servidor detenido")
        server.shutdown()


if __name__ == "__main__":
    run()