"""HTTP calls have explicit timeouts and are never retried."""
import json
from uuid import uuid4
from urllib.request import Request, urlopen
from urllib.error import HTTPError


def request(method, url, *, payload=None, upload=None, session_id=None, accept='application/zip', timeout=60):
    headers = {'Accept': 'application/json'}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode()
        headers['Content-Type'] = 'application/json'
    if upload is not None:
        filename, content = upload
        boundary = uuid4().hex
        data = (f'--{boundary}\r\nContent-Disposition: form-data; name="session_id"\r\n\r\n{session_id}\r\n'
                f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\n'
                'Content-Type: application/octet-stream\r\n\r\n').encode() + content + f'\r\n--{boundary}--\r\n'.encode()
        headers = {'Accept': accept, 'Content-Type': f'multipart/form-data; boundary={boundary}'}
    try:
        response = urlopen(Request(url, data=data, headers=headers, method=method), timeout=timeout)
    except HTTPError as exc:
        response = exc
    with response:
        return response.status, dict(response.headers), response.read()
