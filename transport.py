"""Shared JSON/form/ZIP transport, explicit timeouts and no retries."""
import json
from uuid import uuid4
from urllib.request import Request, urlopen
from urllib.error import HTTPError


def request(method,url,*,payload=None,upload=None,session_id=None,accept='application/json',timeout=60,form_fields=None):
    headers={'Accept':accept}
    data=None
    if payload is not None:
        if upload is not None or form_fields is not None:
            raise ValueError('Use JSON or multipart, not both.')
        data=json.dumps(payload).encode()
        headers['Content-Type']='application/json'
    elif upload is not None or form_fields is not None:
        fields=dict(form_fields or {})
        if session_id is not None:
            fields['session_id']=session_id
        boundary=uuid4().hex
        parts=[]
        for key,value in fields.items():
            if any(ch in str(key) for ch in '\r\n"'):
                raise ValueError('Invalid multipart field name')
            parts.append((f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n').encode())
        if upload is not None:
            filename,content=upload
            if any(ch in filename for ch in '\r\n"'):
                raise ValueError('Invalid upload filename')
            parts.extend([(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\nContent-Type: application/octet-stream\r\n\r\n').encode(),content,b'\r\n'])
        parts.append(f'--{boundary}--\r\n'.encode())
        data=b''.join(parts)
        headers['Content-Type']=f'multipart/form-data; boundary={boundary}'
    try:
        response=urlopen(Request(url,data=data,headers=headers,method=method),timeout=timeout)
    except HTTPError as exc:
        response=exc
    with response:
        return response.status,dict(response.headers),response.read()
