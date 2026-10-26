"""Course tester API. One process owns all in-memory sessions."""
from copy import deepcopy
from pathlib import Path
import json
import logging
from threading import Lock
from urllib.parse import urlsplit, urlencode
from urllib.error import URLError
from uuid import uuid4
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from models import SessionRef, TestError, SuiteReport
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, StrictStr, field_validator
from starlette.exceptions import HTTPException
from transport import request
from suite import CASES, run_case, coverage

app = FastAPI(title='Team 3 preliminary PDF tester', version='1.0.0', docs_url='/docs', redoc_url=None, openapi_url='/openapi.json', description='Run the Team 3 preliminary PDF suite against a system implementing the shared pod API v0.3.0. Prepare a session, run it once, and retrieve its stored report. The browser dashboard is at /; this API explorer is at /docs and /tester.')
sessions = {}
lock = Lock()


def error(message, status=400, source='tester'):
    return JSONResponse({'message': message, 'source': source}, status_code=status)


class Setup(BaseModel):
    target_url: StrictStr

    @field_validator('target_url')
    @classmethod
    def valid_url(cls, value):
        value = value.strip().rstrip('/')
        u = urlsplit(value)
        if u.scheme not in ('http', 'https') or not u.hostname or u.username or u.password or u.query or u.fragment or any(ch.isspace() for ch in value):
            raise ValueError('Use an HTTP(S) base URL without credentials, query, or fragment')
        if u.path.endswith('/test') or u.path.endswith(('/test/setup','/test/run','/test/report')):
            raise ValueError('Supply the system base URL, without a test endpoint suffix')
        _ = u.port
        return value


class Run(BaseModel):
    session_id: StrictStr

    @field_validator('session_id')
    @classmethod
    def nonblank(cls, value):
        if not value.strip(): raise ValueError('session_id must not be blank')
        return value


@app.exception_handler(RequestValidationError)
async def invalid(request, exc):
    return error('Invalid request. Supply target_url for setup or a nonempty session_id for run/report.')


@app.exception_handler(HTTPException)
async def http_error(request, exc):
    return error(str(exc.detail), exc.status_code)


@app.exception_handler(Exception)
async def unexpected(request, exc):
    logging.exception('Tester operation failed', exc_info=exc)
    return error('Tester operation failed.', 500)


@app.post('/test/setup', status_code=201, response_model=SessionRef, summary='Prepare a target system and create a session', responses={400: {'model': TestError}, 409: {'model': TestError}, 500: {'model': TestError}})
def setup(body: Setup):
    sid = str(uuid4())
    try:
        status, _, raw = request('POST', body.target_url+'/test/setup', payload={'session_id': sid, 'setup': {}}, timeout=10)
        try: result = json.loads(raw)
        except (ValueError, TypeError): return error('Target setup returned invalid JSON.', 500, 'system')
        if status >= 400:
            if isinstance(result, dict) and result.get('message') and result.get('source') in ('tester','system','communication','unknown'):
                return JSONResponse(result, status_code=status)
            return error('Target setup returned a malformed error.', status, 'system')
        if status != 201 or not isinstance(result, dict) or result.get('session_id') != sid:
            return error('Target setup must return 201 and the supplied session_id.', 500, 'system')
    except (URLError, OSError, TimeoutError) as exc:
        return error(f'Target setup communication failed: {exc}', 500, 'communication')
    with lock:
        sessions[sid] = {'target_url': body.target_url, 'state': 'ready', 'report': None}
    return {'session_id': sid}


def read_code(target, sid):
    try:
        status, _, raw = request('GET', target+'/test/report?'+urlencode({'session_id':sid}))
        result = json.loads(raw)
        if status != 200 or result['session_id'] != sid: raise ValueError('Unexpected system report status or session')
        code = result['coverage']['code']
        a,b = code['covered'], code['total']
        if not isinstance(code['basis'], str) or not code['basis'].strip(): raise ValueError('Empty basis')
        if not (a is None and b is None) and not (type(a) is int and type(b) is int and 0 <= a <= b): raise ValueError('Invalid coverage counts')
        return {k:code[k] for k in ('covered','total','basis')}
    except Exception as exc:
        return {'covered':None, 'total':None, 'basis':f'Target code coverage unavailable: {exc}'}


@app.post('/test/run', response_model=SuiteReport, response_model_exclude_unset=True, summary='Run the six tests once and return the complete report', responses={400: {'model': TestError}, 404: {'model': TestError}, 409: {'model': TestError}, 500: {'model': TestError}})
def run(body: Run):
    with lock:
        session = sessions.get(body.session_id)
        if session is None: return error('Unknown session.', 404)
        if session['state'] != 'ready': return error('This session has already started. Create a new session to run again.', 409)
        session['state'] = 'running'
        target = session['target_url']
    results = []
    aborted = False
    current = None
    try:
        for test_id, filename in CASES:
            current = test_id
            results.append(run_case(test_id, filename, target, body.session_id))
            current = None
    except Exception as exc:
        logging.exception('Tester suite aborted')
        aborted = True
        if current is not None:
            results.append(dict(test_id=current, outcome='error', source='tester', message=f'Could not evaluate test: {exc}'))
        recorded = {r['test_id'] for r in results}
        for test_id, filename in CASES:
            if test_id not in recorded:
                results.append(dict(test_id=test_id, outcome='skip', message=f'{filename}: not executed because tester aborted.'))
    measures = coverage(results)
    measures['code'] = read_code(target, body.session_id)
    report = dict(session_id=body.session_id, target_url=target, results=results, coverage=measures)
    with lock:
        session['report'] = deepcopy(report)
        session['state'] = 'ended'
    if aborted: return error('Tester aborted. Retrieve available results using /test/report.', 500)
    return report


@app.get('/test/report', response_model=SuiteReport, response_model_exclude_unset=True, summary='Retrieve the saved report without rerunning tests', responses={400: {'model': TestError}, 404: {'model': TestError}, 409: {'model': TestError}})
def report(session_id: str):
    if not session_id.strip(): return error('session_id must not be blank.')
    with lock:
        session = sessions.get(session_id)
        if session is None: return error('Unknown session.', 404)
        if session['state'] != 'ended': return error('Suite has not ended.', 409)
        return deepcopy(session['report'])


@app.get("/", include_in_schema=False)
def homepage():
    return FileResponse(Path(__file__).resolve().parent / "index.html", headers={"Cache-Control": "no-store"})


@app.get('/tester', include_in_schema=False)
@app.get('/tester/', include_in_schema=False)
def api_explorer(request: Request):
    prefix = request.scope.get('root_path', '').rstrip('/')
    return get_swagger_ui_html(openapi_url=prefix + '/openapi.json', title='Team 3 Tester - API explorer')


def course_openapi():
    if app.openapi_schema is None:
        schema = get_openapi(title=app.title, version=app.version,
                             description=app.description, routes=app.routes)
        # FastAPI's default 422 is replaced by the course-mandated 400 handler.
        for path in schema['paths'].values():
            for operation in path.values():
                if isinstance(operation, dict):
                    operation.get('responses', {}).pop('422', None)
        schema['components']['schemas']['Setup']['properties']['target_url']['example'] = 'http://127.0.0.1:8001'
        schema['components']['schemas']['Run']['properties']['session_id']['description'] = 'Use the session_id returned by setup. One run per session.'
        app.openapi_schema = schema
    return app.openapi_schema


app.openapi = course_openapi
