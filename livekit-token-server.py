#!/usr/bin/env python3
"""
Einfacher LiveKit Token Generator Server
Nutzen: http://localhost:8765?room=test-room&user=TestUser
"""
import jwt
import json
import os
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

API_KEY = os.environ.get("LIVEKIT_API_KEY", "")
API_SECRET = os.environ.get("LIVEKIT_API_SECRET", "")

class TokenHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            # Parse query parameters
            parsed_url = urlparse(self.path)
            params = parse_qs(parsed_url.query)

            room_name = params.get('room', ['test-room'])[0]
            user_name = params.get('user', ['TestUser'])[0]

            # Generate token (LiveKit JWT format)
            now = int(time.time())
            payload = {
                'iss': API_KEY,
                'sub': user_name,
                'iat': now,
                'exp': now + 3600,  # 1 hour
                'nbf': now,
                'video': {
                    'roomJoin': True,
                    'room': room_name,
                    'canPublish': True,
                    'canPublishData': True,
                    'canSubscribe': True,
                }
            }

            token = jwt.encode(payload, API_SECRET, algorithm='HS256')

            # Return JSON response
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()

            response = {
                'token': token,
                'room': room_name,
                'user': user_name,
                'livekit_url': os.environ.get('LIVEKIT_PUBLIC_URL', 'wss://appdb.eppcom.de:7443'),
                'status': 'ok'
            }
            self.wfile.write(json.dumps(response).encode())

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {format % args}")

if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', 8765), TokenHandler)
    print("🔑 LiveKit Token Server läuft auf http://localhost:8765")
    print("Usage: http://localhost:8765?room=test-room&user=TestUser")
    print("")
    server.serve_forever()
