"""Shared JSON/form/ZIP transport, explicit timeouts and no retries."""
import json
from time import monotonic
from uuid import uuid4
from urllib.request import Request, urlopen
from urllib.error import HTTPError


def request(method,url,*,payload=None,upload=None,session_id=None,accept='application/json',timeout=60,form_fields=None):
    deadline=monotonic()+timeout
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
        remaining=deadline-monotonic()
        if remaining<=0: raise TimeoutError('Request time limit exceeded before sending.')
        response=urlopen(Request(url,data=data,headers=headers,method=method),timeout=remaining)
    except HTTPError as exc:
        response=exc
    with response:
        chunks=[]
        while True:
            remaining=deadline-monotonic()
            if remaining<=0: raise TimeoutError('Request time limit exceeded while receiving the response.')
            # urllib's timeout normally applies separately to each socket read.
            # Reduce it as the whole-call budget is consumed (HTTPError wraps an
            # HTTPResponse, so check both possible levels).
            for candidate in (response,getattr(response,'fp',None)):
                raw=getattr(getattr(candidate,'fp',None),'raw',None)
                sock=getattr(raw,'_sock',None)
                if sock is not None:
                    sock.settimeout(remaining)
                    break
            chunk=getattr(response,'read1',response.read)(64*1024)
            if monotonic()>deadline: raise TimeoutError('Request time limit exceeded while receiving the response.')
            if not chunk: break
            chunks.append(chunk)
        return response.status,dict(response.headers),b''.join(chunks)
