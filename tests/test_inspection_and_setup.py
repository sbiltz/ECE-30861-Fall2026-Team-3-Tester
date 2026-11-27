"""Phase 5 contract regressions; controlled responses only, no live model calls."""
import base64,json,unittest
from io import BytesIO
from unittest.mock import patch
from pypdf import PdfWriter
from tester import suite
from tests.test_suite_execution import success,response,target

class InspectionTests(unittest.TestCase):
    def test_supplied_phase5_contract_is_loaded(self):
        self.assertEqual(suite.VERSION,'0.5.0')
        self.assertIn('NO_TEXT_LAYER',suite.SPEC['components']['schemas']['Error']['properties']['error_code']['enum'])

    def test_ai_alt_write_is_allowed_without_resolving_finding(self):
        data=suite._input('phase4_human_review.pdf')
        result=success('phase4_human_review.pdf',data,human=True)
        finding=result['findings'][0]
        finding.update(suggested_text='A chart with three bars.',suggestion_source='llm')
        result['repairs']=[{'repair_id':'R-1','finding_id':finding['finding_id'],'action':'Write draft Alt','validation_result':'passed','method':'llm','applied_text':finding['suggested_text']}]
        # A real changed PDF; output still needs semantic human review.
        writer=PdfWriter(clone_from=BytesIO(data))
        from pypdf.generic import NameObject,TextStringObject
        writer._root_object['/StructTreeRoot']['/K'][0].get_object()[NameObject('/Alt')]=TextStringObject(finding['suggested_text'])
        out=BytesIO();writer.write(out);edited=out.getvalue()
        import hashlib
        result['output_pdf'].update(content_base64=base64.b64encode(edited).decode(),sha256=hashlib.sha256(edited).hexdigest(),modified=True)
        result['outcome']='completed_with_repairs'
        result['limitations'].append('Document content was sent to an external language model provider.')
        # Use an actual report PDF with the required AI label.
        from tester.text_layer_fixtures import text_pdf
        report=text_pdf('AI-generated, please verify')
        result['report_pdf'].update(content_base64=base64.b64encode(report).decode(),sha256=hashlib.sha256(report).hexdigest())
        suite.validate_success(result,'phase4_human_review.pdf',data)
        self.assertEqual(result['summary']['fixed_count'],0)

    def test_disallowed_llm_check_is_rejected(self):
        data=suite._input('accessibilityIssues.pdf');result=success('accessibilityIssues.pdf',data)
        finding=next(f for f in result['findings'] if f['check_id']=='CHK-STRUCTURE')
        finding.update(suggested_text='Example',suggestion_source='llm')
        with self.assertRaisesRegex(AssertionError,'LLM.*CHK-STRUCTURE'):
            suite.validate_success(result,'accessibilityIssues.pdf',data)

    def test_color_repair_is_rejected(self):
        name='wcag-1.4.1-color-only-status.pdf';data=suite._input(name);result=success(name,data)
        finding=result['findings'][0]
        result['repairs']=[{'repair_id':'R-1','finding_id':finding['finding_id'],'action':'Rewrite colors','validation_result':'passed','method':'llm','applied_text':'New text'}]
        with self.assertRaisesRegex(AssertionError,'suggestions only'):
            suite.validate_success(result,name,data)

    def test_repair_case_is_executed_and_exercises_all_components(self):
        with patch.object(suite,'request',side_effect=target),patch.dict('os.environ',{'TESTER_MODE':'contract'}):
            results=[suite.run_case(t,n,'http://example.test','sid') for t,n in suite.CASES]
        repair=next(r for r in results if r['test_id']=='T-21')
        self.assertEqual(repair['outcome'],'pass',repair)
        self.assertEqual(suite.coverage(results)['component']['covered'],8)

    def test_image_only_scan_must_be_rejected(self):
        with patch.object(suite,'request',side_effect=target):
            result=suite.run_case('T-30',dict(suite.CASES)['T-30'],'http://example.test','sid')
        self.assertEqual(result['outcome'],'pass',result)
        with patch.object(suite,'request',return_value=response(success('ocr-unreadable-scan.pdf',suite._input('ocr-unreadable-scan.pdf')))):
            result=suite.run_case('T-30',dict(suite.CASES)['T-30'],'http://example.test','sid')
        self.assertEqual(result['outcome'],'fail',result)

    def test_detection_only_target_fails_phase5_repair_case(self):
        def detection_only(method,url,**kwargs):
            name,data=kwargs['upload'];result=success(name,data)
            for f in result['findings']:
                if f['classification']=='auto_fixable': f['status']='detected'
            import hashlib
            result['repairs']=[];result['summary']['fixed_count']=0;result['outcome']='completed_no_repairs'
            result['output_pdf'].update(content_base64=base64.b64encode(data).decode(),sha256=hashlib.sha256(data).hexdigest(),modified=False)
            return response(result)
        with patch.object(suite,'request',side_effect=detection_only):
            result=suite.run_case('T-21',dict(suite.CASES)['T-21'],'http://example.test','sid')
        self.assertEqual(result['outcome'],'fail',result)
        self.assertIn('repair and revalidate',result['message'])

    def test_mixed_page_forbids_color_findings_on_scanned_page(self):
        def invalid(method,url,**kwargs):
            name,data=kwargs['upload'];result=success(name,data)
            definition=suite.CATALOG['CHK-COLOR']
            result['findings']=[{'finding_id':'F-1','check_id':'CHK-COLOR','issue_type':'color','wcag_criterion':definition['wcag_criterion'],'wcag_level':'A','classification':'human_review','status':'needs_human_review','evaluation_result':'needs_review','location':{'page':2,'description':'Scanned page'},'fix_description':'Review colors.'}]
            result['human_review_items']=['F-1'];result['summary'].update(total_issues=1,human_review_count=1)
            return response(result)
        with patch.object(suite,'request',side_effect=invalid):
            result=suite.run_case('T-31',dict(suite.CASES)['T-31'],'http://example.test','sid')
        self.assertEqual(result['outcome'],'fail',result)
        self.assertIn('text-based findings',result['message'])

    def test_llm_on_language_is_not_allowed(self):
        name='wcag-3.1.1-missing-language.pdf';data=suite._input(name);result=success(name,data)
        result['repairs'][0].update(method='llm',applied_text='en-US')
        result['findings'][0].update(suggestion_source='llm',suggested_text='en-US')
        with self.assertRaisesRegex(AssertionError,'LLM write is prohibited for CHK-LANG'):
            suite.validate_success(result,name,data)

    def test_ai_report_label_and_external_disclosure_are_enforced(self):
        name='phase4_human_review.pdf';data=suite._input(name);result=success(name,data,human=True)
        result['findings'][0].update(suggestion_source='llm',suggested_text='A chart with bars.')
        with self.assertRaisesRegex(AssertionError,'Report PDF must label'):
            suite.validate_success(result,name,data)
        from tester.text_layer_fixtures import text_pdf
        import hashlib
        report=text_pdf('AI-generated, please verify')
        result['report_pdf'].update(content_base64=base64.b64encode(report).decode(),sha256=hashlib.sha256(report).hexdigest())
        with self.assertRaisesRegex(AssertionError,'external model provider'):
            suite.validate_success(result,name,data)
        result['limitations'].append('Content sent to an external model provider.')
        suite.validate_success(result,name,data)

    def test_generated_mixed_and_ocr_fixtures_match_their_test_purpose(self):
        from tester.text_layer_fixtures import make_fixture
        from pypdf import PdfReader
        mixed=PdfReader(BytesIO(make_fixture('mixed',suite.ROOT)))
        self.assertEqual(len(mixed.pages),3)
        self.assertTrue(mixed.pages[0].extract_text().strip())
        self.assertFalse((mixed.pages[1].extract_text() or '').strip())
        self.assertFalse((mixed.pages[2].extract_text() or '').strip())
        self.assertTrue(mixed.pages[1].images)
        self.assertFalse(mixed.pages[2].images)
        ocr=PdfReader(BytesIO(make_fixture('ocr-text',suite.ROOT)))
        self.assertIn('Recognized text',ocr.pages[0].extract_text())
        self.assertIn(b'3 Tr',ocr.pages[0].get_contents().get_data())

    def test_unknown_and_missing_process_sessions_are_sent_correctly(self):
        for case in ('T-34','T-35'):
            with patch.object(suite,'request',side_effect=target) as call:
                result=suite.run_case(case,dict(suite.CASES)[case],'http://example.test','known-sid')
            self.assertEqual(result['outcome'],'pass',result)
            sent=call.call_args.kwargs
            if case=='T-34': self.assertNotEqual(sent['session_id'],'known-sid')
            else: self.assertNotIn('session_id',sent)

class TargetSetupTests(unittest.TestCase):
    def test_setup_forwards_session_and_empty_data_without_running_cases(self):
        import app
        def ready(method,url,**kwargs):
            self.assertEqual(kwargs['payload']['setup'],{})
            self.assertEqual(kwargs['timeout'],10)
            return response({'session_id':kwargs['payload']['session_id']},201)
        with patch.object(app,'request',side_effect=ready),patch.object(app,'run_case') as cases:
            result=app.setup(app.Setup(target_url='http://example.test/system'))
        cases.assert_not_called()
        self.assertIn(result['session_id'],app.sessions)
        self.assertEqual(app.sessions[result['session_id']]['state'],'ready')

    def test_invalid_target_error_is_not_forwarded_as_invalid_tester_error(self):
        import app
        with patch.object(app,'request',return_value=response({'message':42,'source':'system'},400)):
            result=app.setup(app.Setup(target_url='http://example.test'))
        self.assertEqual(result.status_code,400)
        self.assertIsInstance(json.loads(result.body)['message'],str)
        self.assertEqual(json.loads(result.body)['source'],'system')

    def test_connection_closed_during_setup_is_communication_error(self):
        import app
        from http.client import IncompleteRead
        with patch.object(app,'request',side_effect=IncompleteRead(b'partial')):
            result=app.setup(app.Setup(target_url='http://example.test'))
        self.assertEqual(result.status_code,500)
        self.assertEqual(json.loads(result.body)['source'],'communication')

    def test_failed_setup_does_not_create_a_session(self):
        import app
        before=set(app.sessions)
        with patch.object(app,'request',return_value=response({'message':'Unavailable','source':'system'},500)):
            result=app.setup(app.Setup(target_url='http://example.test'))
        self.assertEqual(result.status_code,500)
        self.assertEqual(set(app.sessions),before)
