import json
import os
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from google.cloud import storage, logging as cloud_logging
from google.api_core import exceptions

BUCKET_NAME="jasont63-nta"
BUCKET_DIR="html-files-gcs/"
PORT = 8080

FORBIDDEN_COUNTRIES = {
    "North Korea", "Iran", "Cuba", "Myanmar",
    "Iraq", "Libya", "Sudan", "Zimbabwe", "Syria"
    }

bucket=storage.Client().bucket(BUCKET_NAME)

logger = cloud_logging.Client().logger("vm-http-microservice")

class CustomHTTPServer(HTTPServer):
    request_queue_size = 10

class FileReqReply(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    #simply override basehttprequest handler stderr logging, prevent unneeded outputs
    def log_msg(self, format,*args):
        pass
        
    def check_forbidden_country(self)->bool:
        country = self.headers.get("X-country")
        if country and country.strip() in FORBIDDEN_COUNTRIES:
            payload={
                "event":"FORBIDDEN_COUNTRY_ACCESS",
                "client_ip":self.client_address[0],
                "country":country,
                "path":self.path,
                "method":self.command,
            }
            logger.log_struct(payload,severity="CRITICAL")
            self.send_reply(400,"Permission Denied:Forbidden Country Header")
            return True
        return False
        
    def send_reply(self, status, content, content_type="text/plain"):
        encoded_content = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Lenth", str(len(encoded_content)))
        self.send_header("Connection","close")
        self.end_headers()
        self.wfile.write(encoded_content)
        
    def fetch_and_reply(self, filename):
        filename=filename.lstrip("/")
        
        try:
            content=bucket.blob(BUCKET_DIR+filename).download_as_text()
            self.send_reply(200,content)
        except exceptions.NotFound:
            payload={
                "event":"FILE_NOT_FOUND",
                "filename":filename,
                "client_ip":self.client_address[0],
            }
            
            logger.log_struct(payload,severity="WARNING")
            self.send_reply(404,f"File Not Found:{filename}")
    #GET method
    def do_GET(self):
        if self.check_forbidden_country():
            return
        parsed_url=urllib.parse.urlparse(self.path)
        filename=parsed_url.path.strip()
        self.fetch_and_reply(filename)
    #Post method
    def do_POST(self):
        if self.check_forbidden_country():
            return
            
        try:
            content_len=int(self.headers.get("Content-Length",0))
            post_data = self.rfile.read(content_len)
            
            payload = json.loads(post_data.decode("utf-8"))
            filename=payload.get("filename")
            self.fetch_and_reply(filename)
        except Exception as e:
            self.send_reply(400, f"SOMETHING_HAPPENED: {str(e)}")
    #override Python's fallback, taking direct control over constructing 
    #the custom response format generating Cloud Logging ERROR payload.
    def do_PUT(self): self.handle_unsupported()
    def do_DELETE(self): self.handle_unsupported()
    def do_HEAD(self): self.handle_unsupported()
    def do_OPTIONS(self): self.handle_unsupported()
    def do_PATCH(self): self.handle_unsupported()
    
    def handle_unsupported(self):
        payload={
            "event": "UNSUPPORTED_METHOD",
            "method": self.command,
            "path":self.path,
            "client_ip": self.client_address[0]
        }
        logger.log_struct(payload,severity="ERROR")
        self.send_reply(501,f"NOT_IMPLEMENTED: {self.command}")
        
def run():
    server_address = ("",PORT)
    httpd = HTTPServer(server_address, FileReqReply)
    print(f"BaseHTTP Server starting on port {PORT}")
    httpd.serve_forever()
    
if __name__ == "__main__":
    run()