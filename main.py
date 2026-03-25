import socket
import threading

# Configuration
LISTEN_PORT = 8888
BUFFER_SIZE = 4096

def handle_client(client_socket):
    try:
        # Receive the initial request from the browser
        request = client_socket.recv(BUFFER_SIZE)
        if not request:
            client_socket.close()
            return

        # Parse the first line to get the destination
        first_line = request.decode('utf-8', errors='ignore').split('\n')[0]
        parts = first_line.split(' ')
        
        if len(parts) < 3:
            client_socket.close()
            return

        method = parts[0]
        url = parts[1]

        # Handle HTTPS (CONNECT method)
        if method == "CONNECT":
            host, port = url.split(':')
            proxy_https(client_socket, host, int(port))
        else:
            # Handle standard HTTP
            proxy_http(client_socket, request, url)

    except Exception as e:
        print(f"[!] Error: {e}")
        client_socket.close()

def proxy_http(client_socket, request, url):
    """Handles standard unencrypted HTTP requests."""
    try:
        # Strip the protocol to get the hostname
        hostname = url.replace("http://", "").split('/')[0]
        port = 80
        
        if ":" in hostname:
            hostname, port = hostname.split(":")
            port = int(port)

        # Connect to the actual destination server
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.connect((hostname, port))
        server_socket.sendall(request)

        # Relay the response back to the browser
        while True:
            data = server_socket.recv(BUFFER_SIZE)
            if len(data) > 0:
                client_socket.send(data)
            else:
                break
        
        server_socket.close()
        client_socket.close()
    except Exception as e:
        print(f"[!] HTTP Proxy Error: {e}")
        client_socket.close()

def proxy_https(client_socket, host, port):
    """Handles HTTPS tunneling via the CONNECT method."""
    try:
        # Connect to the destination server
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.connect((host, port))
        
        # Tell the browser the tunnel is established
        client_socket.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")

        # Start two-way communication between client and server
        # We use non-blocking mode to keep the threads alive during the tunnel
        client_socket.setblocking(0)
        server_socket.setblocking(0)

        while True:
            # Browser to Server
            try:
                data = client_socket.recv(BUFFER_SIZE)
                if not data: break
                server_socket.sendall(data)
            except BlockingIOError:
                pass
            
            # Server to Browser
            try:
                data = server_socket.recv(BUFFER_SIZE)
                if not data: break
                client_socket.sendall(data)
            except BlockingIOError:
                pass
                
    except Exception as e:
        print(f"[!] HTTPS Tunnel Error: {e}")
    finally:
        client_socket.close()
        server_socket.close()

def start_proxy():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('127.0.0.1', LISTEN_PORT))
    server.listen(10)
    
    print(f"[*] Proxy listening on 127.0.0.1:{LISTEN_PORT}")

    while True:
        client_sock, addr = server.accept()
        print(f"[*] Accepted connection from {addr[0]}:{addr[1]}")
        
        # Start a new thread for every request
        handler = threading.Thread(target=handle_client, args=(client_sock,))
        handler.start()

if __name__ == "__main__":
    start_proxy()
