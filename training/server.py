import os
import socket
import argparse
from http.server import HTTPServer, SimpleHTTPRequestHandler

class Handler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        # Get the absolute path of the training directory
        base_dir = os.path.dirname(os.path.abspath(__file__))
        # Convert URL path to filesystem path
        path = SimpleHTTPRequestHandler.translate_path(self, path)
        # Make the path relative to the training directory
        rel_path = os.path.relpath(path, os.getcwd())
        # Join with base directory
        return os.path.join(base_dir, rel_path)

    def end_headers(self):
        # Disable caching
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        SimpleHTTPRequestHandler.end_headers(self)

def run_server(port):
    # Change to the training directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    # Create IPv6 socket that also supports IPv4
    sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
    
    # Create server
    server = HTTPServer(('::', port), Handler, bind_and_activate=False)
    server.socket = sock
    server.server_bind()
    server.server_activate()
    
    print(f"Server running on:")
    print(f"http://localhost:{port}")
    print(f"http://127.0.0.1:{port}")
    print(f"http://[::1]:{port}")
    print("\nPress Ctrl+C to stop the server")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.server_close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run the Quantum Trader training server')
    parser.add_argument('--port', type=int, default=7555,
                      help='Port to run the server on (default: 7555)')
    args = parser.parse_args()
    run_server(args.port)
