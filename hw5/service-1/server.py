#!/usr/bin/env python3
"""HW4 app 1: serve Cloud Storage files and report forbidden countries."""
import json
import mimetypes
import os
import datetime
import mimetypes
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit

import pymysql
from google.api_core.exceptions import NotFound

FORBIDDEN_COUNTRIES = {
    'north korea', 'iran', 'cuba', 'myanmar', 'iraq',
    'libya', 'sudan', 'zimbabwe', 'syria',
}

LOG_NAME='vm-file-server'
DIR="html-files-gcs/"
DB_HOST = os.environ.get('DB_HOST', '')
DB_USER = os.environ.get('DB_USER', '')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '')
DB_INSTANCE = os.environ.get('DB_INSTANCE', '')

def get_db_connection():
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_INSTANCE,
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor
    )
    
class FileServer(ThreadingHTTPServer):
    """Cloud clients are explicit so the HTTP app can also be tested offline."""
    def __init__(self, address, *, bucket_name, prefix, storage_client,
                 publisher, topic_path, logger):
        self.bucket_name = bucket_name
        self.prefix = prefix.strip('/')
        self.storage_client = storage_client
        self.publisher = publisher
        self.topic_path = topic_path
        self.logger = logger
        super().__init__(address, RequestHandler)

#extract metadata from gcs and timer
def extract_request_headers(handler):
    t0 = time.perf_counter()
    country = handler.headers.get('X-country', 'unknown').strip()
    gender = handler.headers.get('X-gender', handler.headers.get('X-Gender', 'unknown'))
    age_range = handler.headers.get('X-age', "unknown")
    income = handler.headers.get('X-income', handler.headers.get('X-Income', 'unknown'))
    is_banned_hdr = handler.headers.get('X-is-banned', handler.headers.get('X-Is-Banned', 'false'))
    
    is_banned = (country.casefold() in FORBIDDEN_COUNTRIES) or (str(is_banned_hdr).lower() == 'true')
    client_ip = handler.headers.get('X-Client-IP', handler.client_address[0])

    metadata = {
        'country': country or 'Unknown',
        'client_ip': client_ip,
        'gender': gender,
        'age_range': age_range,
        'income': income,
        'is_banned': is_banned,
        'time_of_day': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    }
    t1 = time.perf_counter()
    return metadata, (t1 - t0)

#read serving files from gcs and timer
def fetch_from_gcs(server, filename):
    t0 = time.perf_counter()
    object_name = DIR + '/'.join(p for p in (server.prefix, filename) if p)
    try:
        contents = server.storage_client.bucket(server.bucket_name).blob(object_name).download_as_bytes()
        t1 = time.perf_counter()
        return contents, 200, (t1 - t0)
    except NotFound:
        t1 = time.perf_counter()
        return 'File not found\n', 404, (t1 - t0)
    except Exception:
        t1 = time.perf_counter()
        return 'Cloud Storage temporarily unavailable\n', 503, (t1 - t0)
#enter metadata into database
def enter_into_db(metadata, filename, status_code):
    t0 = time.perf_counter()
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            if status_code == 200:
                sql = """
                    INSERT INTO requests 
                    (country, client_ip, gender, age_range, income, is_banned, time_of_day, requested_file)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(sql, (
                    metadata['country'], metadata['client_ip'], metadata['gender'],
                    metadata['age_range'], metadata['income'], metadata['is_banned'],
                    metadata['time_of_day'], filename
                ))
            else:
                #send to failed requests if not status 200
                sql = """
                    INSERT INTO failed_requests (time_of_request, requested_file, error_code)
                    VALUES (%s, %s, %s)
                """
                cursor.execute(sql, (metadata['time_of_day'], filename, status_code))
        conn.close()
    except Exception as e:
        print(f"[DB ERROR] Insertion failed: {e}; file attempted was: {filename}", flush=True)
    t1 = time.perf_counter()
    return (t1 - t0)      
#send a rply to client
def send_reply(handler, status, body, content_type='text/plain; charset=utf-8'):
    t0 = time.perf_counter()
    data = body.encode('utf-8') if isinstance(body, str) else body
    try:
        handler.send_response(status)
        handler.send_header('Content-Type', content_type)
        handler.send_header('Content-Length', str(len(data)))
        handler.end_headers()
        if handler.command != 'HEAD':
            handler.wfile.write(data)
    except (BrokenPipeError, ConnectionResetError):
        pass
    t1 = time.perf_counter()
    return (t1 - t0)
class RequestHandler(BaseHTTPRequestHandler):
    def _event(self, status, filename):
        print(status, self.command, self.headers.get('X-country'))
        return {'status': status, 'method': self.command, 'filename': filename,
                'country': self.headers.get('X-country', ''),
                'client_ip': self.headers.get('X-Client-IP', self.client_address[0])}

    def _log(self, severity, event, message):
        self.server.logger.log_struct(dict(event, message=message), severity=severity)

    def _filename(self, value):
        if not isinstance(value, str) or not value.strip():
            raise ValueError('A nonempty filename is required')
        filename = value.lstrip('/')
        full_prefix = '/'.join(p for p in (self.server.bucket_name, self.server.prefix) if p) + '/'
        if filename.startswith(full_prefix):
            filename = filename[len(full_prefix):]
        elif self.server.prefix and filename.startswith(self.server.prefix + '/'):
            filename = filename[len(self.server.prefix) + 1:]
        if not filename or any(p in ('', '.', '..') for p in filename.split('/')):
            raise ValueError('Invalid filename')
        return (filename)

    def do_GET(self):
        metadata, t_extract = extract_request_headers(self)
        try:
            filename = self._filename(unquote(urlsplit(self.path).path))
        except ValueError as exc:
            t_send = send_reply(self, 400, str(exc) + '\n')
            t_db = enter_into_db(metadata, self.path, 400)
            self._report_timings(400, t_extract, 0.0, t_send, t_db)
            return

        self._serve_file(filename, metadata, t_extract)
        
    def do_POST(self):
        metadata, t_extract = extract_request_headers(self)
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 1048576:
                raise ValueError('Expected a JSON payload no larger than 1 MiB')
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError('Expected a JSON object with a filename field')
            filename = self._filename(data.get('filename'))
        except (ValueError, UnicodeDecodeError) as exc:
            t_send = send_reply(self, 400, str(exc) + '\n')
            t_db = enter_into_db(metadata, self.path, 400)
            self._report_timings(400, t_extract, 0.0, t_send, t_db)
            return

        self._serve_file(filename, metadata, t_extract)

    def _serve_file(self, filename, metadata,t_extract):
        if metadata['is_banned']:
            event = self._event(400, filename)
            self._log('CRITICAL', event, 'Request from a forbidden country')
            try:
                self.server.publisher.publish(
                    self.server.topic_path, json.dumps(event).encode('utf-8')
                ).result(timeout=30)
            except Exception:
                self._log('ERROR', self._event(503, filename), 'Forbidden-event publication failed')
                t_send = send_reply(self, 503, 'Reporting service temporarily unavailable\n')
                t_db = enter_into_db(metadata, filename, 503)
                self._report_timings(503, t_extract, 0.0, t_send, t_db)
                return

            t_send = send_reply(self, 400, 'Access denied: forbidden country\n')
            t_db = enter_into_db(metadata, filename, 400)
            self._report_timings(400, t_extract, 0.0, t_send, t_db)
            return

        contents, status_code, t_gcs = fetch_from_gcs(self.server, filename)
        content_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream' 
        
        t_send = send_reply(self, status_code, contents, content_type)
        t_db = enter_into_db(metadata, filename, status_code)
        self._report_timings(status_code, t_extract, t_gcs, t_send, t_db)
        
    
    def _report_timings(self, status, t_headers, t_gcs, t_send, t_db):
        return 
        """print(f"[TIMING] Status: {status} | "
              f"Header Extract: {t_headers * 1000:.3f}ms | "
              f"GCS Read: {t_gcs * 1000:.3f}ms | "
              f"Send Response: {t_send * 1000:.3f}ms | "
              f"Database Entry: {t_db * 1000:.3f}ms", flush=True)
        """
    def __getattr__(self, name):
        if name.startswith('do_'):
            return self._method_not_implemented
        raise AttributeError(name)

    def _method_not_implemented(self):
        self._log('ERROR', self._event(501, self.path), 'Unsupported HTTP method')
        self._send(501, 'Method not implemented\n')

    def log_message(self, format, *args):
        # Required structured error records go directly to Cloud Logging above.
        print(f'{self.client_address[0]} {format % args}', flush=True)


def main():
    from google.cloud import logging as cloud_logging, pubsub_v1, storage
    required = ('PROJECT_ID', 'BUCKET_NAME', 'TOPIC_NAME')
    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        raise SystemExit('Missing configuration: ' + ', '.join(missing))
    project = os.environ['PROJECT_ID']
    publisher = pubsub_v1.PublisherClient()
    server = FileServer(
        (os.environ.get('HOST', '0.0.0.0'), int(os.environ.get('PORT', '8080'))),
        bucket_name=os.environ['BUCKET_NAME'], prefix=os.environ.get('OBJECT_PREFIX', ''),
        storage_client=storage.Client(project=project), publisher=publisher,
        topic_path=publisher.topic_path(project, os.environ['TOPIC_NAME']),
        logger=cloud_logging.Client(project=project).logger(LOG_NAME),
    )
    print(f'Serving on {server.server_address}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        publisher.stop()


if __name__ == '__main__':
    main()