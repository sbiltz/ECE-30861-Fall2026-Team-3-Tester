import base64
import copy
import hashlib
from io import BytesIO
from pathlib import Path
import json
import unittest
from unittest.mock import patch
from urllib.error import URLError
from zipfile import ZipFile

import app
from tester import suite


def success(filename,original,human=False):
    with ZipFile(suite.ROOT/'fixtures'/'expected'/'goodAccessible_review.zip') as archive:
        result=json.loads(archive.read('report.json'))
    result['evaluation_id']='12345678-1234-4234-8234-123456789abc'
    result['input']={'file_name':filename,'size_bytes':len(original),'sha256':hashlib.sha256(original).hexdigest()}
    result['output_pdf'].update(file_name='output.pdf',sha256=hashlib.sha256(original).hexdigest(),
                                content_base64=base64.b64encode(original).decode(),modified=False)
    result['report_pdf']['file_name']='report.pdf'
    result['checks_performed']=list(suite.CATALOG)
    result['findings']=[]
    checks = []
    if filename=='accessibilityIssues.pdf':
        checks = ['CHK-TITLE','CHK-LANG','CHK-NONTEXT','CHK-STRUCTURE','CHK-LINK']
    else:
        checks = [check for fixture,check in suite.ISOLATED_CASES.values() if fixture==filename]
    for index,check in enumerate(checks,1):
        definition=suite.CATALOG[check]
        human_review=definition['classification']=='human_review'
        result['findings'].append({'finding_id':f'F-{index}','check_id':check,'issue_type':'implementation_specific_wording',
            'wcag_criterion':definition['wcag_criterion'],'wcag_level':definition['wcag_level'],
            'classification':definition['classification'],
            'status':'needs_human_review' if human_review else 'detected',
            'evaluation_result':'needs_review' if human_review else 'fail',
            'location':{'page':None,'description':'Fixture defect'},'fix_description':'Address the fixture defect.'})
    if human or filename=='phase4_human_review.pdf':
        result['findings'].append({'finding_id':'F-H','check_id':'CHK-NONTEXT','issue_type':'generic_alt',
            'wcag_criterion':'1.1.1','wcag_level':'A','classification':'human_review','status':'needs_human_review',
            'evaluation_result':'needs_review','location':{'page':1,'description':'Chart, Figure MCID 0'},
            'fix_description':'Describe the chart information.'})
    result['human_review_items']=[f['finding_id'] for f in result['findings'] if f['classification']=='human_review']
    result['summary']={'total_issues':len(result['findings']),'fixed_count':0,'human_review_count':len(result['human_review_items'])}
    result['repairs']=[]
    result['new_issues_after_repair']=[]
    metadata_findings=[f for f in result['findings'] if f['classification']=='auto_fixable']
    if metadata_findings:
        from pypdf import PdfWriter
        from pypdf.generic import NameObject,TextStringObject
        writer=PdfWriter(clone_from=BytesIO(original))
        for index,finding in enumerate(metadata_findings,1):
            finding['status']='fixed'
            value='Fixture document' if finding['check_id']=='CHK-TITLE' else 'en-US'
            if finding['check_id']=='CHK-TITLE': writer.add_metadata({'/Title':value})
            else: writer._root_object[NameObject('/Lang')]=TextStringObject(value)
            result['repairs'].append({'repair_id':f'R-{index}','finding_id':finding['finding_id'],'action':'Set missing metadata','validation_result':'passed','method':'rule','applied_text':value})
        out=BytesIO();writer.write(out);edited=out.getvalue()
        result['output_pdf'].update(sha256=hashlib.sha256(edited).hexdigest(),content_base64=base64.b64encode(edited).decode(),modified=True)
        result['outcome']='completed_with_repairs'
        result['summary']['fixed_count']=len(metadata_findings)
    if filename=='phase5-mixed.pdf': result['limitations'].append('Page 2 is scanned (no text layer); text-based checks did not run there.')
    return result


def response(body,status=200,media='application/json',headers=None):
    return status,{'Content-Type':media,**(headers or {})},json.dumps(body).encode() if isinstance(body,(dict,list)) else body


def target(method,url,**kwargs):
    if url.endswith('/health'):
        return response({'status':'ok','spec_version':suite.VERSION})
    if url.endswith('/checks'):
        return response({'checks':list(suite.CATALOG.values())})
    if url.endswith('/test/setup'):
        return response({'message':'Session already exists','source':'system'},409)
    if '/test/report?' in url:
        return response({'message':'Unknown session','source':'system'},404)
    fields=kwargs.get('form_fields',{})
    upload=kwargs.get('upload')
    code=None
    if not upload: code='MISSING_FILE'
    elif fields.get('output')=='invalid': code='INVALID_REQUEST'
    else:
        filename,original=upload
        code={'BiggerThan20MB.pdf':'FILE_TOO_LARGE','NonPDF.docx':'INVALID_FILE_TYPE',
              'encrypted.pdf':'ENCRYPTED_PDF','passwordprotected.pdf':'PASSWORD_PROTECTED_PDF',
              'corrupted.pdf':'CORRUPTED_PDF','ocr-unreadable-scan.pdf':'NO_TEXT_LAYER','phase5-blank.pdf':'NO_TEXT_LAYER'}.get(filename)
    if code:
        status={'FILE_TOO_LARGE':413,'INVALID_FILE_TYPE':415,'ENCRYPTED_PDF':422,
                'PASSWORD_PROTECTED_PDF':422,'CORRUPTED_PDF':422,'NO_TEXT_LAYER':422,'MISSING_FILE':400,'INVALID_REQUEST':400}[code]
        return response({'status':'error','error_code':code,'message':'Known fixture rejection'},status)
    result=success(filename,original)
    if fields.get('output')=='zip':
        result=copy.deepcopy(result)
        output=BytesIO()
        with ZipFile(output,'w') as archive:
            archive.writestr('original.pdf',original)
            for key in ('output_pdf','report_pdf'):
                archive.writestr(result[key]['file_name'],base64.b64decode(result[key].pop('content_base64')))
            archive.writestr('result.json',json.dumps(result))
        return response(output.getvalue(),media='application/zip',headers={'Content-Disposition':'attachment; filename="results.zip"'})
    return response(result)


class SuiteExecutionTests(unittest.TestCase):
    def run_case(self,test_id,transport=target):
        with patch.object(suite,'request',side_effect=transport),patch.dict('os.environ',{'TESTER_MODE':'contract'}):
            return suite.run_case(test_id,dict(suite.CASES)[test_id],'http://example.test/system','session')

    def test_full_compliant_phase5_target_passes(self):
        outcomes=[self.run_case(test_id) for test_id,_ in suite.CASES]
        self.assertEqual([r['test_id'] for r in outcomes if r['outcome']!='pass'],[],outcomes)
        self.assertEqual(len(outcomes),35)
        self.assertEqual(suite.coverage(outcomes)['component']['covered'],8)
        self.assertIsNone(suite.coverage(outcomes)['system']['covered'])

    def test_isolated_fixture_rejects_missing_and_extra_findings(self):
        filename, _ = suite.ISOLATED_CASES['T-26']
        original = suite._input(filename)
        missing = success(filename,original)
        missing['findings'].clear()
        missing['summary'].update(total_issues=0,fixed_count=0)
        missing['repairs']=[]
        missing['outcome']='completed_no_repairs'
        missing['output_pdf'].update(content_base64=base64.b64encode(original).decode(),sha256=hashlib.sha256(original).hexdigest(),modified=False)
        extra = success(filename,original,human=True)
        for payload in (missing,extra):
            with self.subTest(findings=payload['findings']):
                outcome = self.run_case('T-26',lambda *a,**kw:response(payload))
                self.assertEqual(outcome['outcome'],'fail')
                self.assertIn('Expected findings only for CHK-TITLE',outcome['message'])

    def test_old_service_version_is_explicit_failure(self):
        outcome=self.run_case('T-07',lambda *a,**kw:response({'status':'ok','spec_version':'0.3.0'}))
        self.assertEqual(outcome['outcome'],'fail')
        self.assertIn('0.5.0',outcome['message'])

    def test_declared_but_unperformed_checks_fail(self):
        def missing(*args,**kwargs):
            result=success(*kwargs['upload'])
            result['checks_performed'].remove('CHK-LINK')
            result['limitations'].append('CHK-LINK: not implemented')
            return response(result)
        result=self.run_case('T-12',missing)
        self.assertEqual(result['outcome'],'fail')
        self.assertIn('CHK-LINK',result['message'])

    def test_catalog_cannot_substitute_wrong_classification(self):
        checks=copy.deepcopy(list(suite.CATALOG.values()))
        checks[0]['classification']='auto_fixable'
        self.assertEqual(self.run_case('T-08',lambda *a,**kw:response({'checks':checks}))['outcome'],'fail')

    def test_missing_predetermined_metadata_findings_fail(self):
        def missing(*args,**kwargs):
            result=success(*kwargs['upload'])
            result['findings']=[]
            result['repairs']=[]
            result['outcome']='completed_no_repairs'
            result['output_pdf'].update(content_base64=base64.b64encode(kwargs['upload'][1]).decode(),sha256=hashlib.sha256(kwargs['upload'][1]).hexdigest(),modified=False)
            result['summary'].update(total_issues=0,fixed_count=0,human_review_count=0)
            result['human_review_items']=[]
            return response(result)
        self.assertEqual(self.run_case('T-13',missing)['outcome'],'fail')

    def test_human_review_cannot_be_marked_detected(self):
        original=suite._input('goodAccessible.pdf')
        result=success('goodAccessible.pdf',original,human=True)
        result['findings'][0]['status']='detected'
        with self.assertRaisesRegex(AssertionError,'Human-review finding'):
            suite.validate_success(result,'goodAccessible.pdf',original)

    def test_old_auto_fixable_needs_review_status_is_not_v04_semantics(self):
        original=suite._input('accessibilityIssues.pdf')
        result=success('accessibilityIssues.pdf',original)
        result['findings'][0]['status']='needs_human_review'
        with self.assertRaisesRegex(AssertionError,'status'):
            suite.validate_success(result,'accessibilityIssues.pdf',original)

    def test_wrong_output_digest_and_missing_review_ids_fail(self):
        original=suite._input('goodAccessible.pdf')
        result=success('goodAccessible.pdf',original,human=True)
        result['human_review_items']=[]
        with self.assertRaises(AssertionError):suite.validate_success(result,'goodAccessible.pdf',original)
        result=success('goodAccessible.pdf',original)
        result['output_pdf']['sha256']='0'*64
        with self.assertRaises(AssertionError):suite.validate_success(result,'goodAccessible.pdf',original)

    def test_zip_uses_shared_form_field_and_no_baseline_comparison(self):
        with patch.object(suite,'request',side_effect=target) as call:
            result=suite.run_case('T-15','ZIP','http://example.test','sid')
        self.assertEqual(result['outcome'],'pass',result)
        self.assertEqual(call.call_args.kwargs['form_fields'],{'output':'zip'})

    def test_legacy_zip_layout_is_rejected_by_shared_zip_case(self):
        raw=(suite.ROOT/'fixtures'/'expected'/'goodAccessible_review.zip').read_bytes()
        result=self.run_case('T-15',lambda *a,**kw:response(raw,media='application/zip',headers={'Content-Disposition':'attachment; filename="legacy.zip"'}))
        self.assertEqual(result['outcome'],'fail')

    def test_zip_input_errors_must_not_be_wrapped_in_http200_archive(self):
        result=self.run_case('T-17',lambda *a,**kw:response(b'zip',media='application/zip'))
        self.assertEqual(result['outcome'],'fail')

    def test_communication_and_system_failures_are_distinct(self):
        def offline(*args,**kwargs):raise URLError('offline')
        self.assertEqual(self.run_case('T-02',offline)['source'],'communication')
        result=self.run_case('T-02',lambda *a,**kw:response({'status':'error','error_code':'EXTERNAL_SERVICE_UNAVAILABLE','message':'offline'},503))
        self.assertEqual(result['source'],'system')

    def test_unreachable_and_skipped_checks_do_not_inflate_coverage(self):
        results=[{'test_id':'T-07','outcome':'error','source':'communication'}, {'test_id':'T-21','outcome':'skip'}]
        self.assertEqual(suite.coverage(results)['component']['covered'],0)
        self.assertNotIn('COMP-REPAIR',suite.coverage([{'test_id':'T-14','outcome':'pass'}])['component']['basis'])

    def test_nullable_json_cache_matches_canonical_yaml(self):
        expected=json.loads((suite.CONTRACT_DIR/'shared-openapi.json').read_text())
        self.assertEqual(expected,suite.json_schema(suite.SPEC))

    def test_app_run_preserves_full_report_and_coverage(self):
        sid='complete-v04-test'
        app.sessions[sid]={'target_url':'http://example.test','state':'ready','report':None}
        with patch.object(suite,'request',side_effect=target),patch.object(app,'read_code',return_value={'covered':None,'total':None,'basis':'Unavailable'}):
            report=app.run(app.Run(session_id=sid))
        self.assertEqual(len(report['results']),len(suite.CASES))
        self.assertEqual(sum(r['outcome']=='pass' for r in report['results']),35)
        self.assertEqual(app.report(sid),report)
        self.assertEqual(app.run(app.Run(session_id=sid)).status_code,409)


class TransportTests(unittest.TestCase):
    def test_multipart_output_and_session_are_encoded(self):
        from tester import transport
        class Reply(BytesIO):
            status=200
            headers={'Content-Type':'application/json'}
        with patch.object(transport,'urlopen',return_value=Reply(b'{}')) as call:
            transport.request('POST','http://example.test/process',upload=('x.pdf',b'%PDF-test'),
                              session_id='sid',form_fields={'output':'zip'},accept='application/zip')
        request=call.call_args.args[0]
        self.assertEqual(request.get_header('Accept'),'application/zip')
        self.assertIn(b'name="output"\r\n\r\nzip',request.data)
        self.assertIn(b'name="session_id"\r\n\r\nsid',request.data)
        self.assertGreater(call.call_args.kwargs['timeout'],0)
        self.assertLessEqual(call.call_args.kwargs['timeout'],60)

    def test_missing_upload_can_still_send_session_field(self):
        from tester import transport
        class Reply(BytesIO):
            status=400
            headers={}
        with patch.object(transport,'urlopen',return_value=Reply(b'{}')) as call:
            transport.request('POST','http://example.test/process',session_id='sid',form_fields={})
        data=call.call_args.args[0].data
        self.assertIn(b'name="session_id"',data)
        self.assertNotIn(b'name="file"',data)


class FailureAttributionAndFixtureTests(unittest.TestCase):
    def test_bad_returned_pdf_is_target_failure_not_tester_abort(self):
        original=suite._input('goodAccessible.pdf')
        result=success('goodAccessible.pdf',original)
        invalid=b'%PDF-1.7\ninvalid payload\n'
        result['report_pdf'].update(content_base64=base64.b64encode(invalid).decode(),sha256=hashlib.sha256(invalid).hexdigest())
        with patch.object(suite,'request',return_value=response(result)):
            outcome=suite.run_case('T-02','goodAccessible.pdf','http://example.test','sid')
        self.assertEqual(outcome['outcome'],'fail')
        self.assertIn('readable PDF',outcome['message'])

    def test_missing_local_fixture_is_not_a_communication_failure(self):
        with patch.object(Path,'read_bytes',side_effect=FileNotFoundError('missing')):
            with self.assertRaises(suite.FixtureError):
                suite.run_case('T-02','goodAccessible.pdf','http://example.test','sid')

    def test_human_fixture_has_real_image_and_structural_parent_associations(self):
        from pypdf import PdfReader
        reader=PdfReader(suite.ROOT/'fixtures'/'inputs'/'phase4_human_review.pdf')
        tree=reader.trailer['/Root']['/StructTreeRoot']
        figure=tree['/K'][0].get_object()
        self.assertEqual(figure['/Alt'],'image1')
        self.assertEqual(figure['/P'],tree)
        self.assertEqual(reader.pages[0]['/StructParents'],0)
        self.assertEqual(tree['/ParentTree']['/Nums'][1][0].get_object(),figure)
        self.assertTrue(reader.pages[0]['/Resources']['/XObject'])
        self.assertNotIn('2024',reader.pages[0].extract_text())

    def test_rfc_encoded_zip_attachment_filename_is_accepted(self):
        original=suite._input('goodAccessible.pdf')
        status,headers,body=target('POST','http://example.test/process',upload=('goodAccessible.pdf',original),form_fields={'output':'zip'})
        headers['Content-Disposition']="attachment; filename*=UTF-8''results.zip"
        suite.validate_zip(body,headers,'goodAccessible.pdf',original)
