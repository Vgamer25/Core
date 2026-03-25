import socket
import threading
import requests
from flask import Flask, jsonify, render_template_string
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import datetime

# --- CONFIGURATION ---
LISTEN_PORT = 8888
DASHBOARD_PORT = 5000
BUFFER_SIZE = 4096
intercepted_logs = []

# --- FLASK DASHBOARD ---
app = Flask(__name__)

@app.route('/')
def index():
    # Simple HTML dashboard to view intercepted traffic
    html = """
    <html>
        <head>
            <title>Proxy Dashboard</title>
            <style>
                body { font-family: sans-serif; padding: 20px; background: #f4f4f9; }
                .log-entry { background: white; border: 1px solid #ddd; padding: 10px; margin-bottom: 5px; border-radius: 4px; }
                .method { font-weight: bold; color: #007bff; }
                .url { color: #28a745; }
            </style>
        </head>
        <body>
            <h1>Live Proxy Traffic</h1>
            <div id="logs">
                {% for log in logs %}
                <div class="log-entry">
                    <span class="method">[{{ log.method }}]</span> 
                    <span class="url">{{ log.url }}</span>
                    <small style="display:block; color:#999">{{ log.time }}</small>
                </div>
                {% endfor %}
            </div>
            <script>setTimeout(function(){ location.reload(); }, 3000);</script>
        </body>
    </html>
    """
    return render_template_string(html, logs=intercepted_logs[-20:]) # Show last 20 logs

def run_dashboard():
    app.run(port=DASHBOARD_PORT, debug=False, use_reloader=False)

# --- CRYPTOGRAPHY: SSL GEN HELPER ---
def generate_self_signed_cert(hostname):
    """Generates a dummy self-signed cert (for educational purposes)."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, hostname),
    ])
    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.datetime.utcnow()
    ).not_valid_after(
        datetime.datetime.utcnow() + datetime.timedelta(days=10)
    ).add_extension(
        x509.SubjectAlternativeName([x509.DNSName(hostname)]),
        critical=False,
    ).sign(key, hashes.SHA256())
    
    return cert, key

# --- PROXY LOGIC ---
def log_traffic(method, url):
    log = {
        "method": method,
        "url": url,
        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    intercepted_logs.append(log)
    print(f"[*] Intercepted: {method} {url}")

def handle_client(client_socket):
    try:
        request = client_socket.recv(BUFFER_SIZE)
        if not request:
            client_socket.close()
            return

        raw_request = request.decode('utf-8', errors='ignore')
        first_line = raw_request.split('\n')[0]
        parts = first_line.split(' ')
        
        if len(parts) < 3:
            client_socket.close()
            return

        method, url = parts[0], parts[1]
        log_traffic(method, url)

        if method == "CONNECT":
            host, port = url.split(':')
            proxy_https(client_socket, host, int(port))
        else:
            proxy_http(client_socket, request, url)

    except Exception as e:
        client_socket.close()

def proxy_http(client_socket, request, url):
    try:
        hostname = url.replace("http://", "").split('/')[0]
        port = 80
        if ":" in hostname:
            hostname, port = hostname.split(":")
            port = int(port)

        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.connect((hostname, port))
        server_socket.sendall(request)

        while True:
            data = server_socket.recv(BUFFER_SIZE)
            if len(data) > 0:
                client_socket.send(data)
            else:
                break
        server_socket.close()
        client_socket.close()
    except:
        client_socket.close()

def proxy_https(client_socket, host, port):
    try:
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.connect((host, port))
        client_socket.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")

        client_socket.setblocking(0)
        server_socket.setblocking(0)

        while True:
            try:
                data = client_socket.recv(BUFFER_SIZE)
                if not data: break
                server_socket.sendall(data)
            except BlockingIOError: pass
            
            try:
                data = server_socket.recv(BUFFER_SIZE)
                if not data: break
                client_socket.sendall(data)
            except BlockingIOError: pass
                
    except:
        pass
    finally:
        client_socket.close()
        server_socket.close()

def start_proxy():
    # Start Dashboard Thread
    threading.Thread(target=run_dashboard, daemon=True).start()
    print(f"[*] Dashboard available at http://127.0.0.1:{DASHBOARD_PORT}")

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('0.0.0.0', LISTEN_PORT))
    server.listen(50)
    print(f"[*] Proxy listening on port {LISTEN_PORT}")

    while True:
        client_sock, addr = server.accept()
        threading.Thread(target=handle_client, args=(client_sock,)).start()

if __name__ == "__main__":
    start_proxy()
