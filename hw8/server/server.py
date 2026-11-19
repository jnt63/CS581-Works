#!/usr/bin/env python3
"""HW4 app 1: serve Cloud Storage files and report forbidden countries."""
import json
import mimetypes
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit
from datetime import datetime

from google.api_core.exceptions import NotFound


FORBIDDEN_COUNTRIES = {
    'north korea', 'iran', 'cuba', 'myanmar', 'iraq',
    'libya', 'sudan', 'zimbabwe', 'syria',
}


print(datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3], flush=True)
class FileServer(ThreadingHTTPServer):
    """Cloud clients are explicit so the HTTP app can also be tested offline."""
    def __init__(self, address, *, bucket_name, prefix, storage_client,
                 publisher, topic_path, logger, zone):
        self.bucket_name = bucket_name
        self.prefix = prefix.strip('/')
        self.storage_client = storage_client
        self.publisher = publisher
        self.topic_path = topic_path
        self.logger = logger
        self.zone = zone
        self.first = 0
        super().__init__(address, RequestHandler)


class RequestHandler(BaseHTTPRequestHandler):
    def _send(self, status, body, content_type='text/plain; charset=utf-8'):
        data = body.encode('utf-8') if isinstance(body, str) else body
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Zone', self.server.zone)
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(data)

    def _event(self, status, filename):
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
        print(full_prefix)
        print(filename)
        return filename

    def do_GET(self):
        parsed_path = unquote(urlsplit(self.path).path)
        print(parsed_path)
        if parsed_path == '/':
            #time of first health check
            if self.server.first<2:
                print(datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3], flush=True)
                self.server.first+=1
            self._send(200, 'ok\n')
            return
        try:
            filename = self._filename(unquote(urlsplit(self.path).path))
        except ValueError as exc:
            self._send(400, str(exc) + '\n')
            return
        self._serve_file(filename)

    def do_POST(self):
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 1048576:
                raise ValueError('Expected a JSON payload no larger than 1 MiB')
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError('Expected a JSON object with a filename field')
            filename = self._filename(data.get('filename'))
        except (ValueError, UnicodeDecodeError) as exc:
            self._send(400, str(exc) + '\n')
            return
        self._serve_file(filename)

    def _serve_file(self, filename):
        country = self.headers.get('X-country', '').strip().casefold()
        if country in FORBIDDEN_COUNTRIES:
            event = self._event(400, filename)
            self._log('CRITICAL', event, 'Request from a forbidden country')
            try:
                # Wait for acceptance instead of silently dropping failed publications.
                self.server.publisher.publish(
                    self.server.topic_path, json.dumps(event).encode('utf-8')
                ).result(timeout=30)
            except Exception:
                self._log('ERROR', self._event(503, filename), 'Forbidden-event publication failed')
                self._send(503, 'Reporting service temporarily unavailable\n')
                return
            self._send(400, 'Access denied: forbidden country\n')
            return

        object_name = '/'.join(p for p in (self.server.prefix, filename) if p)
        try:
            contents = self.server.storage_client.bucket(self.server.bucket_name).blob(object_name).download_as_bytes()
        except NotFound:
            self._log('WARNING', self._event(404, filename), 'File not found')
            self._send(404, 'File not found\n')
            return
        except Exception:
            self._log('ERROR', self._event(503, filename), 'Cloud Storage read failed')
            self._send(503, 'Cloud Storage temporarily unavailable\n')
            return
        content_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
        self._send(200, contents, content_type)

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
    required = ('PROJECT_ID', 'BUCKET_NAME', 'TOPIC_NAME', 'ZONE')
    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        raise SystemExit('Missing configuration: ' + ', '.join(missing))
    project = os.environ['PROJECT_ID']
    publisher = pubsub_v1.PublisherClient()
    server = FileServer(
        (os.environ.get('HOST', '0.0.0.0'), int(os.environ.get('PORT', '80'))),
        bucket_name=os.environ['BUCKET_NAME'], prefix=os.environ.get('OBJECT_PREFIX', ''),
        storage_client=storage.Client(project=project), publisher=publisher,
        topic_path=publisher.topic_path(project, os.environ['TOPIC_NAME']),
        logger=cloud_logging.Client(project=project).logger('hw8-file-server'),
        zone=os.environ['ZONE'],
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