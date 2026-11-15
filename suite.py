"""Pod v0.5.0 contract, detection and repair tests; no project-call retries."""
import base64
import copy
import hashlib
import json
import os
from io import BytesIO
from pathlib import Path, PurePosixPath
from urllib.error import URLError
from urllib.parse import urlencode
from uuid import uuid4
from zipfile import ZipFile, BadZipFile
from http.client import HTTPException

from jsonschema import Draft7Validator, FormatChecker
from ruamel.yaml import YAML
from transport import request

ROOT = Path(__file__).resolve().parent
SPEC = YAML(typ='safe', pure=True).load((ROOT/'shared-openapi.yaml').read_text(encoding='utf-8'))
VERSION = SPEC['info']['version']
CATALOG = {item['check_id']: item for item in SPEC['paths']['/checks']['get']['responses']['200']['content']['application/json']['example']['checks']}
LEGACY_CASES = [('T-01','BiggerThan20MB.pdf'), ('T-02','goodAccessible.pdf'),
                ('T-03','NonPDF.docx'), ('T-04','passwordprotected.pdf'),
                ('T-05','encrypted.pdf'), ('T-06','accessibilityIssues.pdf')]
ISOLATED_CASES = {
    'T-22': ('wcag-1.1.1-missing-alt.pdf', 'CHK-NONTEXT'),
    'T-23': ('wcag-1.3.1-heading-tagged-as-paragraph.pdf', 'CHK-STRUCTURE'),
    'T-24': ('wcag-1.3.3-location-only-instruction.pdf', 'CHK-SENSORY'),
    'T-25': ('wcag-1.4.1-color-only-status.pdf', 'CHK-COLOR'),
    'T-26': ('wcag-2.4.2-missing-title.pdf', 'CHK-TITLE'),
    'T-27': ('wcag-2.4.4-ambiguous-link-purpose.pdf', 'CHK-LINK'),
    'T-28': ('wcag-2.4.6-vague-heading.pdf', 'CHK-HEADINGS'),
    'T-29': ('wcag-3.1.1-missing-language.pdf', 'CHK-LANG'),
}
OCR_CASE = ('T-30', 'ocr-unreadable-scan.pdf')
PHASE5_CASES = [('T-31','Mixed text/scanned/blank pages'), ('T-32','Blank PDF without text'), ('T-33','Invisible OCR text layer'), ('T-34','Unknown processing session'), ('T-35','Missing processing session')]
LLM_CHECKS = {'CHK-NONTEXT','CHK-LINK','CHK-COLOR','CHK-SENSORY','CHK-TITLE'}
LLM_WRITE_CHECKS = {'CHK-NONTEXT','CHK-LINK','CHK-TITLE'}
ISSUE_FIXTURE_CHECKS = {'CHK-NONTEXT', 'CHK-STRUCTURE', 'CHK-TITLE', 'CHK-LINK', 'CHK-LANG'}

CASES = LEGACY_CASES + [
    ('T-07','Health and specification version'), ('T-08','Agreed check catalog'),
    ('T-09','Missing upload'), ('T-10','Corrupted PDF'), ('T-11','Exact size boundary'),
    ('T-12','All eight checks performed'), ('T-13','Known title/language findings'),
    ('T-14','Known human-review finding'), ('T-15','Shared ZIP output'),
    ('T-16','Invalid output option'), ('T-17','ZIP validation error remains JSON'),
    ('T-18','Explicit JSON output'), ('T-19','Duplicate system session'),
    ('T-20','Unknown system report session'), ('T-21','Phase 5 repairs and revalidation'),
    *((test_id, filename) for test_id, (filename, _) in ISOLATED_CASES.items()),
    OCR_CASE] + PHASE5_CASES
CASE_COMPONENTS = {
    'T-01': {'COMP-VALIDATION'}, 'T-02': {'COMP-REPORT'},
    'T-03': {'COMP-VALIDATION'}, 'T-04': {'COMP-VALIDATION'}, 'T-05': {'COMP-VALIDATION'},
    'T-06': {'COMP-REPORT','COMP-DETECTION','COMP-CLASSIFICATION'}, 'T-07': {'COMP-HEALTH'}, 'T-08': {'COMP-CATALOG'},
    'T-09': {'COMP-VALIDATION'}, 'T-10': {'COMP-VALIDATION'}, 'T-11': {'COMP-REPORT'},
    'T-12': {'COMP-DETECTION'}, 'T-13': {'COMP-DETECTION','COMP-CLASSIFICATION'},
    'T-14': {'COMP-DETECTION','COMP-CLASSIFICATION'}, 'T-15': {'COMP-REPORT'},
    'T-16': {'COMP-VALIDATION'}, 'T-17': {'COMP-VALIDATION'}, 'T-18': {'COMP-REPORT'},
    **{test_id: {'COMP-DETECTION','COMP-CLASSIFICATION'} for test_id in ISOLATED_CASES},
    OCR_CASE[0]: {'COMP-VALIDATION'},
    'T-21': {'COMP-REPAIR','COMP-REVALIDATION','COMP-REPORT'},
    'T-31': {'COMP-DETECTION','COMP-REPORT'}, 'T-32': {'COMP-VALIDATION'},
    'T-33': {'COMP-REPORT'}, 'T-34': {'COMP-REPORT'}, 'T-35': {'COMP-REPORT'}}


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def json_schema(value):
    if isinstance(value, list): return [json_schema(item) for item in value]
    if not isinstance(value, dict): return value
    result = {key: json_schema(item) for key,item in value.items() if key != 'nullable'}
    if value.get('nullable') and isinstance(result.get('type'),str):
        result['type'] = [result['type'],'null']
    return result


SCHEMAS = json_schema(SPEC['components'])


def validate(schema_name, value):
    schema = {'$ref':'#/components/schemas/'+schema_name,'components':SCHEMAS}
    problems = sorted(Draft7Validator(schema,format_checker=FormatChecker()).iter_errors(value),key=lambda e:str(e.path))
    require(not problems,'Shared schema mismatch: '+'; '.join(f'{list(e.path)}: {e.message}' for e in problems[:3]))


def validate_success(result, filename, original, *, embedded=True):
    checked = copy.deepcopy(result)
    if not embedded:
        for key in ('output_pdf','report_pdf'):
            require('content_base64' not in checked.get(key,{}),f'ZIP result.json must omit {key}.content_base64.')
            checked[key]['content_base64'] = ''
    validate('EvaluationResult',checked)
    require(result['input']['file_name']==filename,'Input filename differs.')
    require(result['input']['size_bytes']==len(original),'Input byte count differs.')
    require(result['input']['sha256']==hashlib.sha256(original).hexdigest(),'Input digest differs.')
    if embedded:
        for key in ('output_pdf','report_pdf'):
            decoded = base64.b64decode(result[key]['content_base64'],validate=True)
            validate_pdf_bytes(key,result[key],decoded,original,result['outcome'])
    performed = result['checks_performed']
    require(len(performed)==len(set(performed)),'checks_performed contains duplicates.')
    for check in CATALOG:
        if check not in performed:
            require(any(check in text for text in result['limitations']),f'{check} was not performed and is not named in limitations.')
    findings = result['findings']
    ids = [f['finding_id'] for f in findings]
    require(len(ids)==len(set(ids)),'Finding IDs are not unique.')
    by_id = {f['finding_id']:f for f in findings}
    reviews = result['human_review_items']
    require(len(reviews)==len(set(reviews)) and set(reviews)<=set(ids),'human_review_items contains duplicates or unknown IDs.')
    require(set(reviews)=={f['finding_id'] for f in findings if f['classification']=='human_review'},'human_review_items must contain exactly the unresolved human-review findings.')
    repairs = result['repairs']
    require(len({r['repair_id'] for r in repairs})==len(repairs),'Repair IDs are not unique.')
    for repair in repairs:
        require(repair['finding_id'] in by_id,'Repair refers to an unknown finding.')
        finding = by_id[repair['finding_id']]
        check = finding['check_id']
        method = repair.get('method','rule')
        require(check not in ('CHK-COLOR','CHK-SENSORY'),f'{check} is suggestions only; PDF repair is prohibited.')
        if method=='llm':
            require(check in LLM_WRITE_CHECKS,f'LLM write is prohibited for {check}.')
            require(finding.get('suggestion_source')=='llm','LLM repair must identify its finding as LLM-generated.')
            if repair['validation_result']=='passed':
                require(isinstance(repair.get('applied_text'),str) and repair['applied_text'].strip(),'Successful LLM repairs must record nonblank applied_text.')
        if finding['classification']=='human_review':
            require(check in ('CHK-NONTEXT','CHK-LINK') and method=='llm','Only LLM alt/link drafts may be written for human-review findings.')
            require(finding['status']=='needs_human_review','AI draft write must leave the finding in human review.')
        else:
            require(check in ('CHK-TITLE','CHK-LANG'),'Unexpected automatic repair check.')
            expected = 'fixed' if repair['validation_result']=='passed' else 'repair_failed'
            require(finding['status']==expected,'Finding status does not agree with repair validation.')
    for finding in findings + result['new_issues_after_repair']:
        check = finding['check_id']
        definition = CATALOG[check]
        require(check in performed,f'Finding refers to unperformed check {check}.')
        require(all(finding[key]==definition[key] for key in ('wcag_criterion','wcag_level','classification')),f'WCAG/classification mapping differs for {check}.')
        require(isinstance(finding.get('fix_description'),str) and finding['fix_description'].strip(),'Every finding must explain the problem and fix in fix_description.')
        source = finding.get('suggestion_source')
        suggestion = finding.get('suggested_text')
        if source=='llm':
            require(check in LLM_CHECKS,f'LLM suggestions are prohibited for {check}.')
        if suggestion is not None:
            require(source in ('rule','llm'),'suggested_text must identify its suggestion_source.')
        if finding['classification']=='human_review':
            require(finding['status']=='needs_human_review','Human-review finding must remain needs_human_review.')
        else:
            require(finding['status'] in ('detected','fixed','repair_failed'),'v0.5.0 auto_fixable findings use detected when unrepaired, or fixed/repair_failed after repair.')
        linked = [r for r in repairs if r['finding_id']==finding['finding_id']]
        if finding['status']=='detected':
            require(not linked,'A detected finding must not have a repair attempt.')
        if finding['status'] in ('fixed','repair_failed'):
            require(bool(linked),'Repaired finding has no corresponding repair record.')
    summary = result['summary']
    require(summary['total_issues']==len(findings),'summary.total_issues does not match findings.')
    require(summary['fixed_count']==sum(f['status']=='fixed' for f in findings),'summary.fixed_count is inconsistent.')
    require(summary['human_review_count']==len(reviews),'summary.human_review_count is inconsistent.')
    applied = any(r['validation_result']=='passed' for r in repairs)
    require(result['outcome']==('completed_with_repairs' if applied else 'completed_no_repairs'),'outcome does not agree with successful repair records.')
    if applied:
        require(result['output_pdf'].get('modified') is not False,'Successful repairs must not claim modified=false.')
    require(result['compliance_statement']=='This report does not certify ADA Title II or WCAG 2.1 conformance.','Missing fixed non-certification statement.')
    if embedded:
        validate_llm_report(result,base64.b64decode(result['report_pdf']['content_base64'],validate=True))


def validate_llm_report(result, report_bytes):
    used = any(f.get('suggestion_source')=='llm' for f in result['findings']+result['new_issues_after_repair']) or any(r.get('method')=='llm' for r in result['repairs'])
    if not used:
        return
    from pypdf import PdfReader
    text = ' '.join(' '.join(p.extract_text() or '' for p in PdfReader(BytesIO(report_bytes)).pages).split()).lower()
    require('ai-generated, please verify' in text,'Report PDF must label LLM text AI-generated, please verify.')
    disclosure = ' '.join(result['limitations']).lower()
    require('external' in disclosure and ('model' in disclosure or 'provider' in disclosure),'LLM use must disclose sending document content to an external model provider in limitations.')


def validate_pdf_bytes(key,item,decoded,original,outcome):
    require(decoded.startswith(b'%PDF-'),f'{key} is not PDF content.')
    require(hashlib.sha256(decoded).hexdigest()==item['sha256'],f'{key} digest differs.')
    from pypdf import PdfReader
    try:
        reader = PdfReader(BytesIO(decoded),strict=False)
        require(not reader.is_encrypted and len(reader.pages)>0,f'{key} is unreadable, encrypted or empty.')
    except Exception as exc:
        raise AssertionError(f'{key} is not a readable PDF: {exc}') from exc
    if key=='output_pdf' and (item.get('modified') is False or outcome=='completed_no_repairs'):
        require(decoded==original,'Unrepaired/unmodified output differs from original.')


def validate_zip(body,headers,filename,original):
    disposition = header(headers,'content-disposition')
    require('attachment' in disposition.lower() and ('filename=' in disposition.lower() or 'filename*=' in disposition.lower()),'ZIP is missing attachment filename.')
    with ZipFile(BytesIO(body)) as archive:
        names = archive.namelist()
        require(len(names)==len(set(names)),'ZIP has duplicate members.')
        require(archive.testzip() is None,'ZIP checksum failed.')
        require('result.json' in names and 'original.pdf' in names,'ZIP must contain result.json and original.pdf.')
        require(archive.read('original.pdf')==original,'ZIP original differs from submitted PDF.')
        result = json.loads(archive.read('result.json'))
        validate_success(result,filename,original,embedded=False)
        expected = {'original.pdf','result.json'}
        for key in ('output_pdf','report_pdf'):
            item=result[key]
            name=item['file_name']
            require(PurePosixPath(name).name==name and '\\' not in name and name not in expected,'Invalid/colliding ZIP output filename.')
            expected.add(name)
            validate_pdf_bytes(key,item,archive.read(name),original,result['outcome'])
        validate_llm_report(result,archive.read(result['report_pdf']['file_name']))
        require(set(names)==expected,f'Unexpected ZIP members: {names}.')
        return result


def header(headers,name):
    return next((v for k,v in headers.items() if k.lower()==name),'')


def _json_response(status,headers,body,expected,schema):
    require(status==expected,f'Expected HTTP {expected}; received {status}.')
    require(header(headers,'content-type').split(';')[0].strip().lower()=='application/json',
            f"Expected application/json; received {header(headers,'content-type')}.")
    result=json.loads(body)
    validate(schema,result)
    return result


class FixtureError(Exception):
    pass


def _input(filename):
    try:
        return (ROOT/'fixtures'/'inputs'/filename).read_bytes()
    except OSError as exc:
        raise FixtureError(f'Local fixture {filename} is unavailable: {exc}') from exc


def _execute(test_id,target,sid):
    if test_id=='T-07':
        response=request('GET',target+'/health')
        result=_json_response(*response,200,'Health')
        require(result['spec_version']==VERSION,f"Expected shared spec_version {VERSION}; received {result['spec_version']}.")
        return 'Health and shared specification version verified.'
    if test_id=='T-08':
        result=_json_response(*request('GET',target+'/checks'),200,'CheckList')
        ids=[item['check_id'] for item in result['checks']]
        require(len(ids)==len(set(ids)) and set(ids)==set(CATALOG),'Check catalog must list all eight agreed checks exactly once.')
        for item in result['checks']:
            require(all(item[key]==CATALOG[item['check_id']][key] for key in ('wcag_criterion','wcag_level','classification')),
                    f"Catalog mapping differs for {item['check_id']}.")
        return 'All eight catalog definitions and classifications verified.'
    if test_id=='T-19':
        result=_json_response(*request('POST',target+'/test/setup',payload={'session_id':sid,'setup':{}},timeout=10),409,'TestError')
        require(result['source']=='system','Duplicate-session error source must identify the system.')
        return 'Duplicate system session correctly rejected.'
    if test_id=='T-20':
        _json_response(*request('GET',target+'/test/report?'+urlencode({'session_id':str(uuid4())})),404,'TestError')
        return 'Unknown system report session correctly rejected.'
    kwargs={'session_id':sid,'accept':'application/json'}
    error_code=None
    if test_id in dict(LEGACY_CASES):
        filename=dict(LEGACY_CASES)[test_id]
        original=_input(filename)
        error_code={'T-01':'FILE_TOO_LARGE','T-03':'INVALID_FILE_TYPE','T-04':'PASSWORD_PROTECTED_PDF','T-05':'ENCRYPTED_PDF'}.get(test_id)
        kwargs['upload']=(filename,original)
    elif test_id in ISOLATED_CASES or test_id==OCR_CASE[0]:
        filename=dict(CASES)[test_id]
        original=_input(filename)
        kwargs['upload']=(filename,original)
        if test_id==OCR_CASE[0]: error_code='NO_TEXT_LAYER'
    elif test_id in ('T-31','T-32','T-33'):
        from phase5_fixtures import make_fixture
        kind={'T-31':'mixed','T-32':'blank','T-33':'ocr-text'}[test_id]
        filename='phase5-'+kind+'.pdf'
        original=make_fixture(kind,ROOT)
        kwargs['upload']=(filename,original)
        if test_id=='T-32': error_code='NO_TEXT_LAYER'
    elif test_id=='T-09':
        kwargs['form_fields']={}
        error_code='MISSING_FILE'
    elif test_id=='T-10':
        filename,original='corrupted.pdf',b'%PDF-1.7\nintentionally truncated\n'
        kwargs['upload']=(filename,original)
        error_code=('CORRUPTED_PDF','UNREADABLE_PDF')
    elif test_id=='T-11':
        original=_input('goodAccessible.pdf')
        limit=SPEC['x-limits']['max_file_size_bytes']
        position=original.rfind(b'%%EOF')
        require(position>=0 and len(original)<=limit,'Invalid local size-boundary fixture.')
        original=original[:position]+b' '*(limit-len(original))+original[position:]
        filename='exactly20MB.pdf'
        kwargs['upload']=(filename,original)
    else:
        filename='phase4_human_review.pdf' if test_id=='T-14' else 'accessibilityIssues.pdf' if test_id in ('T-12','T-13','T-21') else 'NonPDF.docx' if test_id=='T-17' else 'goodAccessible.pdf'
        original=_input(filename)
        kwargs['upload']=(filename,original)
        if test_id in ('T-15','T-17'):
            kwargs.update(form_fields={'output':'zip'},accept='application/zip')
        if test_id=='T-16':
            kwargs['form_fields']={'output':'invalid'}
            error_code='INVALID_REQUEST'
        if test_id=='T-17': error_code='INVALID_FILE_TYPE'
        if test_id=='T-18': kwargs['form_fields']={'output':'json'}
        if test_id=='T-34': kwargs['session_id']=str(uuid4())
        if test_id=='T-35': kwargs.pop('session_id',None)
    response=request('POST',target+'/process',**kwargs)
    status,headers,body=response
    if status>=500:
        result=_json_response(*response,status,'Error')
        raise TargetUnavailable(f"HTTP {status}: {result['error_code']}: {result['message']}")
    if error_code:
        errors=error_code if isinstance(error_code,tuple) else (error_code,)
        expected={'FILE_TOO_LARGE':413,'INVALID_FILE_TYPE':415,'PASSWORD_PROTECTED_PDF':422,'ENCRYPTED_PDF':422,'CORRUPTED_PDF':422,'UNREADABLE_PDF':422,'NO_TEXT_LAYER':422,'MISSING_FILE':400,'INVALID_REQUEST':400}[errors[0]]
        result=_json_response(*response,expected,'Error')
        require(result['error_code'] in errors,f"Expected error {errors}; received {result['error_code']}.")
        require(result['message'].strip(),'Error explanation is blank.')
        return f'HTTP {expected}, {result["error_code"]}, shared error schema verified.'
    if test_id=='T-15':
        require(status==200,f'Expected ZIP HTTP 200; received {status}.')
        require(header(headers,'content-type').split(';')[0].strip().lower()=='application/zip','output=zip must return application/zip.')
        validate_zip(body,headers,filename,original)
        return 'Shared output=zip archive, JSON manifest, original and PDF hashes verified.'
    result=_json_response(*response,200,'EvaluationResult')
    if test_id in ('T-02','T-12') or test_id in ISOLATED_CASES:
        missing=set(CATALOG)-set(result['checks_performed'])
        require(not missing,f'Expected all eight Phase 5 checks performed; missing {sorted(missing)}.')
    validate_success(result,filename,original)
    finding_checks = {finding['check_id'] for finding in result['findings']}
    if test_id=='T-02':
        require(not finding_checks,f'Expected no findings; received {sorted(finding_checks)}.')
        return 'All eight checks completed with no findings.'
    if test_id=='T-06':
        missing=ISSUE_FIXTURE_CHECKS-finding_checks
        require(not missing,f'Missing expected findings for {sorted(missing)}.')
        return 'Expected findings from all five applicable shared checks verified.'
    if test_id in ISOLATED_CASES:
        _, expected_check=ISOLATED_CASES[test_id]
        require(finding_checks=={expected_check},
                f'Expected findings only for {expected_check}; received {sorted(finding_checks)}.')
        if CATALOG[expected_check]['classification']=='auto_fixable':
            require(any(finding['evaluation_result']=='fail' for finding in result['findings']),
                    f'Expected a failure for {expected_check}.')
        return f'All eight checks completed; findings isolated to {expected_check}.'
    if test_id=='T-21':
        from pypdf import PdfReader
        output=PdfReader(BytesIO(base64.b64decode(result['output_pdf']['content_base64'],validate=True)))
        for check in ('CHK-TITLE','CHK-LANG'):
            matches=[f for f in result['findings'] if f['check_id']==check]
            require(bool(matches) and all(f['status']=='fixed' for f in matches),f'Phase 5 must repair and revalidate the known {check} defect.')
            require(all(any(r['finding_id']==f['finding_id'] and r['validation_result']=='passed' for r in result['repairs']) for f in matches),f'{check} lacks a passed repair record.')
        require(bool(output.metadata and output.metadata.title and output.metadata.title.strip()),'Repaired output PDF still lacks a document title.')
        from re import fullmatch
        language=output.trailer['/Root'].get('/Lang')
        require(isinstance(language,str) and bool(fullmatch(r'[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*',language)) and language.split('-')[0].lower()=='en','Repaired output PDF must declare English for this English-language fixture.')
        require(result['outcome']=='completed_with_repairs','Known repaired defects must produce completed_with_repairs.')
        return 'Title/language repair records, post-write metadata and validation results verified.'
    if test_id=='T-31':
        import re
        require(any('scanned' in note.lower() and re.search(r'\b2\b',note) for note in result['limitations']),'Mixed PDF must name scanned page 2 in limitations.')
        for finding in result['findings']+result['new_issues_after_repair']:
            if finding['location'].get('page')==2:
                require(finding['check_id'] not in ('CHK-SENSORY','CHK-COLOR','CHK-LINK'),'Scanned page 2 must not have text-based findings.')
                require(not (finding['check_id']=='CHK-HEADINGS' and not finding['location'].get('object_ref')),'Scanned page 2 must not have untagged text-heading findings.')
        return 'Mixed PDF accepted, scanned page disclosed and text-based findings suppressed there.'
    if test_id=='T-33':
        return 'Invisible OCR text counts as a text layer; PDF accepted.'
    if test_id=='T-13':
        for check in ('CHK-TITLE','CHK-LANG'):
            # issue_type is intentionally free text in the shared contract.
            require(any(f['check_id']==check and f['evaluation_result']=='fail' for f in result['findings']),f'Missing predetermined missing-metadata finding for {check}.')
    if test_id=='T-14':
        matches=[f for f in result['findings'] if f['check_id']=='CHK-NONTEXT' and f['classification']=='human_review']
        require(bool(matches),'Predetermined generic Figure alternative was not flagged for human review.')
        require(all(f['status']=='needs_human_review' and f['finding_id'] in result['human_review_items'] for f in matches),'Human-review findings were resolved or omitted.')
    return f'Shared v{VERSION} status/schema/integrity verified'+('; full Phase 4 check execution verified.' if test_id=='T-12' else '; predetermined findings and classifications verified.' if test_id in ('T-13','T-14') else '.')


class TargetUnavailable(Exception): pass


def run_case(test_id,filename,target,session_id):
    mode=os.getenv('TESTER_MODE','contract')
    if mode=='zip-baseline':
        if test_id not in dict(LEGACY_CASES):
            return dict(test_id=test_id,outcome='skip',message='Legacy ZIP-baseline mode only runs the six preliminary cases.')
        return run_zip_case(test_id,filename,target,session_id)
    if mode!='contract': raise ValueError('TESTER_MODE must be contract or zip-baseline')
    try:
        message=_execute(test_id,target,session_id)
    except (URLError,OSError,TimeoutError,HTTPException) as exc:
        return dict(test_id=test_id,outcome='error',source='communication',message=f'{filename}: no evaluable response: {exc}')
    except TargetUnavailable as exc:
        return dict(test_id=test_id,outcome='error',source='system',message=f'{filename}: {exc}')
    except (AssertionError,ValueError,KeyError,TypeError,BadZipFile) as exc:
        return dict(test_id=test_id,outcome='fail',message=f'{filename}: {exc}')
    return dict(test_id=test_id,outcome='pass',message=f'{filename}: {message}')


def coverage(results):
    exercised=set()
    for result in results:
        if result['outcome'] in ('pass','fail') or result.get('source')=='system':
            exercised.update(CASE_COMPONENTS.get(result['test_id'],set()))
    components=SPEC['x-pod-testing']['components']['list']
    return {'component':{'covered':len(exercised),'total':len(components),
        'basis':f'Pod v{VERSION} request-based component exercise rules. Exercised: '+(', '.join(sorted(exercised)) or 'none')+'. Exercise is not correctness. Repair/revalidation are exercised by T-21 when it has an evaluable response.'},
        'system':{'covered':None,'total':None,
        'basis':'Shared contract lists AC-01 through AC-10 without definitions; the supplied standalone AC list uses AC-02 through AC-13. No agreed mapping is available, so no system-model coverage is claimed.'}}


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
        status, headers, body = request('POST', target+'/process', upload=(filename,original), session_id=session_id, accept='application/zip')
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
