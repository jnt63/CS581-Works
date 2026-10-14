import json
import os
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from google.cloud import storage, pubsub_v1, logging as cloud_logging
from google.api_core import exceptions

BUCKET_NAME="jasont63-nta"
BUCKET_DIR="html-files-gcs/"
PROJECT_ID="firstproject-508221"
TOPIC_NAME="hw4-audit-topic"
PORT = 8080

FORBIDDEN_COUNTRIES = {
    "North Korea", "Iran", "Cuba", "Myanmar",
    "Iraq", "Libya", "Sudan", "Zimbabwe", "Syria"
    }

bucket=storage.Client().bucket(BUCKET_NAME)
logger = cloud_logging.Client().logger("vm-http-microservice")

publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(PROJECT_ID, TOPIC_NAME)

class FileReqReply(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    #simply override basehttprequest handler stderr logging, prevent unneeded outputs
    def log_message(self, format,*args):
        pass
        
    def check_forbidden_country(self)->bool:
        country = self.headers.get("X-country")
        if country and country.strip() in FORBIDDEN_COUNTRIES:
            parsed_url = urllib.parse.urlparse(self.path)
            filename = parsed_url.path.strip("/") or "unknown"
            payload={
                "event":"FORBIDDEN_COUNTRY_ACCESS",
                "client_ip":self.client_address[0],
                "country":country,
                "path":self.path,
                "method":self.command,
                "status":400,
            }
            logger.log_struct(payload,severity="CRITICAL")
            try:
                message_bytes = json.dumps(payload).encode("utf-8")
                publisher.publish(topic_path, data=message_bytes)
            except Exception as e:
                print(f"Failed to publish to Pub/Sub: {e}")
            self.send_reply(400,"Permission Denied:Forbidden Country Header")
            return True
        return False
        
    def send_reply(self, status, content, content_type="text/html"):
        try:
            encoded_content = content.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", f"{content_type}; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded_content)))
            self.send_header("Connection","close")
            self.end_headers()
            self.wfile.write(encoded_content)
        except (BrokenPipeError, ConnectionResetError):
            pass
        
    def fetch_and_reply(self, filename):
        filename=filename.lstrip("/")
        
        try:
            content=bucket.blob(BUCKET_DIR+filename).download_as_text()
            payload={
                "event":"OK",
                "filename":filename,
                 "client_ip":self.client_address[0],
            }
            logger.log_struct(payload,severity="DEFAULT")
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
        #simple check to make sure server is up before making requests
        if self.path == "/health":
            self.send_reply(200, "OK")
            return
        if self.check_forbidden_country():
            return
        parsed_url=urllib.parse.urlparse(self.path)
        filename=parsed_url.path.strip()
        if not filename:
            filename = "0.html"
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
        #get file name, simply for logging and checking to specify logs for specific files
        content_len=int(self.headers.get("Content-Length",0))
        post_data = self.rfile.read(content_len)
        if content_len >0:
            try:
                payload = json.loads(post_data.decode("utf-8"))
                filename=payload.get("filename")
                if not filename:
                    filename="nofile.html"
            except Exception:
                pass
                
        else:
            parsed_url = urllib.parse.urlparse(self.path)
            extracted = parsed_url.path.strip("/")
            if extracted:
                filename = extracted
        payload={
            "event": "UNSUPPORTED_METHOD",
            "method": self.command,
            "filename":filename,
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