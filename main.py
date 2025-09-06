import http.server
import socketserver
import json
from urllib.parse import urlparse
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)

METADATA = {}
LAUNCH_DATA_CACHE = {}

try:
    with open('metadata.json', 'r') as f:
        METADATA = json.load(f)
    logging.info("Successfully loaded metadata.json")

    logging.info("Loading and caching launch data files...")
    launch_files_to_cache = {
        "win32": "launchdata-win32.json",
        "macx64": "launchdata-macx64.json",
        "macarm64": "launchdata-macarm64.json",
        "linuxx64": "launchdata-linuxx64.json",
        "linuxarm64": "launchdata-linuxarm64.json",
        "linux-replaymod": "launchdata-linux-replaymod.json",
        "win32-replaymod": "launchdata-win32-replaymod.json",
        "macx64-replaymod": "launchdata-macx64-replaymod.json",
        "macarm64-replaymod": "launchdata-macarm64-replaymod.json"
    }

    for key, filename in launch_files_to_cache.items():
        with open(filename, 'r') as f:
            LAUNCH_DATA_CACHE[key] = json.load(f)
            logging.info(f"-> Cached '{filename}' for key '{key}'")

except FileNotFoundError as e:
    logging.error(f"FATAL ERROR: Required data file not found: '{e.filename}'. The server cannot start.")
    sys.exit(1)
except json.JSONDecodeError as e:
    logging.error(f"FATAL ERROR: Failed to decode JSON. Please check the format of your .json files. Details: {e}")
    sys.exit(1)


class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def do_GET(self):
        parsed_path = urlparse(self.path)

        if parsed_path.path == '/':
            self.serve_file('index.html', 'text/html')
        elif parsed_path.path == '/robots.txt':
            self.serve_file('robots.txt', 'text/plain')
        elif parsed_path.path == '/launcher/metadata':
            self.send_json_response(METADATA)
        else:
            self.send_error_response(404, f"File Not Found: {self.path}")

    def do_POST(self):
        parsed_path = urlparse(self.path)

        if parsed_path.path == '/launcher/launch':
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                if content_length == 0:
                    self.send_error_response(400, "Bad Request: Content-Length header is missing or zero.")
                    return

                post_body = self.rfile.read(content_length)
                request_data = json.loads(post_body)

                arch = request_data.get("arch")
                os = request_data.get("os")
                module = request_data.get("module")

                if not arch or not os or not module:
                    self.send_error_response(400, "Bad Request: 'os', 'arch' and 'module' properties are required.")
                    return
                
                logging.info(f"Launch request received for os={os}, arch={arch}")

                lookup_key = None
                if module == 'replay':
                    if os == 'win32':
                        lookup_key = 'win32-replaymod'
                    elif os == 'darwin' and arch == 'x64':
                        lookup_key = 'macx64-replaymod'
                    elif os == 'darwin' and arch == 'arm64':
                        lookup_key = 'macarm64-replaymod'
                    elif os == 'linux':
                        lookup_key = 'linux-replaymod'
                else:
                    if os == 'win32':
                        lookup_key = 'win32'
                    elif os == 'darwin' and arch == 'x64':
                        lookup_key = 'macx64'
                    elif os == 'darwin' and arch == 'arm64':
                        lookup_key = 'macarm64'
                    elif os == 'linux' and arch == 'x64':
                        lookup_key = 'linuxx64'
                    elif os == 'linux' and arch == 'arm64':
                        lookup_key = 'linuxarm64'

                if lookup_key and lookup_key in LAUNCH_DATA_CACHE:
                    launch_data = LAUNCH_DATA_CACHE[lookup_key]
                    self.send_json_response(launch_data)
                    logging.info(f"POST {self.path} 200 OK (served from cache for key '{lookup_key}')")
                else:
                    self.send_error_response(400, f"Unsupported or unavailable OS/architecture: os={os}, arch={arch}")

            except json.JSONDecodeError:
                self.send_error_response(400, "Bad Request: Invalid JSON.")
            except Exception as e:
                self.send_error_response(500, f"An unexpected error occurred: {e}")
        else:
            self.send_error_response(404, f"File Not Found: {self.path}")

    def serve_file(self, filepath, content_type):
        try:
            with open(filepath, 'rb') as f:
                self.send_response(200)
                self.send_header('Content-type', content_type)
                self.end_headers()
                self.wfile.write(f.read())
                logging.info(f"GET {self.path} 200 OK (served {filepath})")
        except FileNotFoundError:
            self.send_error_response(404, f"File Not Found: {filepath}")

    def send_json_response(self, data):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def send_error_response(self, code, message):
        logging.warning(f"Request to {self.path} failed with {code}: {message}")
        self.send_error(code, message)


PORT = 6969
HOST = "0.0.0.0"

if __name__ == "__main__":
    with socketserver.TCPServer((HOST, PORT), Handler) as httpd:
        logging.info("All data files loaded and cached successfully.")
        logging.info(f"Server starting on http://{HOST}:{PORT}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            logging.info("Server is shutting down.")
            httpd.shutdown()
