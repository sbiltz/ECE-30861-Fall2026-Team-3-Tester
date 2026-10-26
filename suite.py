"""Regression comparisons against the six supplied preliminary ZIP outputs."""
import base64
import hashlib
import json
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile, BadZipFile
from urllib.error import URLError
from transport import request
import os
from jsonschema import Draft7Validator, FormatChecker

ROOT = Path(__file__).resolve().parent
CASES = [('T-01','BiggerThan20MB.pdf'), ('T-02','goodAccessible.pdf'),
         ('T-03','NonPDF.docx'), ('T-04','passwordprotected.pdf'),
         ('T-05','encrypted.pdf'), ('T-06','accessibilityIssues.pdf')]


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def compare(actual, expected, filename, original):
    with ZipFile(BytesIO(actual)) as got, ZipFile(BytesIO(expected)) as want:
        names = got.namelist()
        require(len(names) == len(set(names)), 'ZIP contains duplicate filenames.')
        require(set(names) == set(want.namelist()), f'ZIP members differ: received {names}.')
        require(got.testzip() is None, 'ZIP checksum failed.')
        require(got.read(filename) == original, 'Returned original differs from uploaded file.')
        result = json.loads(got.read('report.json'))
        baseline = json.loads(want.read('report.json'))
        require(isinstance(result, dict), 'report.json must contain an object.')
        if 'evaluation_id' in baseline:
            require(isinstance(result.get('evaluation_id'), str) and bool(result['evaluation_id'].strip()), 'Missing evaluation_id.')
            # Evaluation identifiers are generated per request; their values must vary.
            result = dict(result)
            result.pop('evaluation_id', None)
            baseline.pop('evaluation_id', None)
        require(result == baseline, 'report.json differs from the supplied expected output (evaluation_id ignored).')
        for name in names:
            if name != 'report.json':
                require(got.read(name) == want.read(name), f'{name} differs from the expected file.')
        for key in ('output_pdf','report_pdf'):
            if key in result:
                item = result[key]
                content = base64.b64decode(item['content_base64'], validate=True)
                require(content == got.read(item['file_name']), f'{key} Base64 does not match ZIP bytes.')
                require(hashlib.sha256(content).hexdigest() == item['sha256'], f'{key} SHA-256 differs.')


def run_zip_case(test_id, filename, target, session_id):
    # Local fixture failures abort the suite, rather than blaming the target.
    original = (ROOT/'fixtures'/'inputs'/filename).read_bytes()
    expected = (ROOT/'fixtures'/'expected'/(Path(filename).stem+'_review.zip')).read_bytes()
    with ZipFile(BytesIO(expected)) as reference:
        require(reference.read(filename) == original, f'Local expected ZIP does not match fixture {filename}.')
    try:
        status, headers, body = request('POST', target+'/process', upload=(filename,original), session_id=session_id)
    except (URLError, OSError, TimeoutError) as exc:
        return dict(test_id=test_id, outcome='error', source='communication', message=f'{filename}: no evaluable response: {exc}')
    if status >= 500:
        return dict(test_id=test_id, outcome='error', source='system', message=f'{filename}: target returned HTTP {status}.')
    try:
        require(status == 200, f'Expected HTTP 200 ZIP delivery; received {status}.')
        media = next((v for k,v in headers.items() if k.lower() == 'content-type'), '')
        require('application/zip' in media.lower(), f'Expected application/zip; received {media}.')
        compare(body, expected, filename, original)
    except (AssertionError, BadZipFile, ValueError, KeyError, TypeError, RuntimeError) as exc:
        return dict(test_id=test_id, outcome='fail', message=f'{filename}: {exc}')
    return dict(test_id=test_id, outcome='pass', message=f'{filename}: ZIP members, report and file contents match expected output.')


def coverage(results):
    received = {r['test_id'] for r in results if r['outcome'] in ('pass','fail') or r.get('source') == 'system'}
    components = []
    if received & {'T-01','T-03','T-04','T-05'}: components.append('COMP-VALIDATION')
    if received & {'T-02','T-06'}: components.append('COMP-REPORT')
    return {
        'component': {'covered':len(components), 'total':8,
            'basis':'Pod v0.3.0 request-based component exercise rules. Exercised: '+(', '.join(components) or 'none')+'. Preliminary validation/output tests only; accessibility detection and repair are not tested.'},
        'system': {'covered':None, 'total':None,
            'basis':'AC-01 through AC-10 are listed in the pod API but their definitions are unavailable; no acceptance-criterion mapping is claimed.'}}


SPEC = json.loads((ROOT/'shared-openapi.json').read_text())


def validate(schema_name, value):
    schema = {'$ref': '#/components/schemas/'+schema_name, 'components': SPEC['components']}
    problems = sorted(Draft7Validator(schema, format_checker=FormatChecker()).iter_errors(value), key=lambda e:str(e.path))
    require(not problems, 'Shared schema mismatch: '+('; '.join(f"{list(e.path)}: {e.message}" for e in problems[:3])))


def validate_success(result, filename, original):
    validate('EvaluationResult',result)
    require(result['input']['file_name']==filename, 'Input filename differs.')
    require(result['input']['size_bytes']==len(original), 'Input byte count differs.')
    require(result['input']['sha256']==hashlib.sha256(original).hexdigest(), 'Input digest differs.')
    for key in ('output_pdf','report_pdf'):
        item=result[key]
        decoded=base64.b64decode(item['content_base64'],validate=True)
        require(decoded.startswith(b'%PDF-'), f'{key} is not PDF content.')
        require(hashlib.sha256(decoded).hexdigest()==item['sha256'], f'{key} digest differs.')
        if key=='output_pdf' and item.get('modified') is False:
            require(decoded==original, 'Output marked unmodified differs from original.')
    performed=set(result['checks_performed'])
    for check in SPEC['components']['schemas']['CheckId']['enum']:
        if check not in performed:
            require(any(check in text for text in result['limitations']), f'{check} was not performed and is not named in limitations.')


def run_case(test_id, filename, target, session_id):
    mode=os.environ.get('TESTER_MODE','contract')
    if mode=='zip-baseline':return run_zip_case(test_id,filename,target,session_id)
    if mode!='contract':raise ValueError('TESTER_MODE must be contract or zip-baseline')
    original=(ROOT/'fixtures'/'inputs'/filename).read_bytes()
    expected=(ROOT/'fixtures'/'expected'/(Path(filename).stem+'_review.zip')).read_bytes()
    with ZipFile(BytesIO(expected)) as archive:
        require(archive.read(filename)==original, 'Local reference does not match input fixture.')
        baseline=json.loads(archive.read('report.json'))
    code=baseline.get('error_code')
    expected_status={'FILE_TOO_LARGE':413,'INVALID_FILE_TYPE':415,'PASSWORD_PROTECTED_PDF':422,'ENCRYPTED_PDF':422}.get(code,200)
    try:
        status,headers,body=request('POST',target+'/process',upload=(filename,original),session_id=session_id,accept='application/json')
    except (URLError,OSError,TimeoutError) as exc:
        return dict(test_id=test_id,outcome='error',source='communication',message=f'{filename}: no evaluable response: {exc}')
    if status>=500:
        return dict(test_id=test_id,outcome='error',source='system',message=f'{filename}: target returned HTTP {status}.')
    try:
        require(status==expected_status,f'Expected HTTP {expected_status}; received {status}.')
        media=next((v for k,v in headers.items() if k.lower()=='content-type'),'')
        require('application/json' in media.lower(),f'Expected application/json; received {media}.')
        result=json.loads(body)
        if code:
            validate('Error',result)
            require(result['error_code']==code,f"Expected {code}; received {result['error_code']}.")
            require(bool(result['message'].strip()),'Error message is empty.')
        else:validate_success(result,filename,original)
    except (AssertionError,ValueError,KeyError,TypeError) as exc:
        return dict(test_id=test_id,outcome='fail',message=f'{filename}: {exc}')
    return dict(test_id=test_id,outcome='pass',message=f'{filename}: shared v0.3.0 HTTP status, JSON schema and input/output integrity verified.')
