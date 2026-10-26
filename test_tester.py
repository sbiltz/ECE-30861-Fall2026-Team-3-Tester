import json
import unittest
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile
from unittest.mock import patch
import app
from suite import CASES, ROOT, compare


def rewrite(raw, change):
    out=BytesIO()
    with ZipFile(BytesIO(raw)) as source, ZipFile(out,'w') as target:
        for name in source.namelist():
            data=source.read(name)
            if name=='report.json':
                report=json.loads(data);change(report);data=json.dumps(report).encode()
            target.writestr(name,data)
    return out.getvalue()


class Comparisons(unittest.TestCase):
    def test_all_supplied_baselines(self):
        for _,name in CASES:
            with self.subTest(name=name):
                raw=(ROOT/'fixtures'/'expected'/(Path(name).stem+'_review.zip')).read_bytes()
                original=(ROOT/'fixtures'/'inputs'/name).read_bytes()
                compare(raw,raw,name,original)

    def test_generated_id_may_change_but_status_must_match(self):
        name='goodAccessible.pdf'
        raw=(ROOT/'fixtures'/'expected'/'goodAccessible_review.zip').read_bytes()
        original=(ROOT/'fixtures'/'inputs'/name).read_bytes()
        compare(rewrite(raw,lambda r:r.update(evaluation_id='new-id')),raw,name,original)
        with self.assertRaises(AssertionError):
            compare(rewrite(raw,lambda r:r.update(status='error')),raw,name,original)

    def test_expected_rejection_cannot_be_silently_changed(self):
        name='encrypted.pdf'
        raw=(ROOT/'fixtures'/'expected'/'encrypted_review.zip').read_bytes()
        original=(ROOT/'fixtures'/'inputs'/name).read_bytes()
        with self.assertRaises(AssertionError):
            compare(rewrite(raw,lambda r:r.update(error_code='OTHER')),raw,name,original)

    def test_contract_allows_other_teams_report_wording(self):
        from suite import validate_success
        raw=(ROOT/'fixtures'/'expected'/'goodAccessible_review.zip').read_bytes()
        original=(ROOT/'fixtures'/'inputs'/'goodAccessible.pdf').read_bytes()
        with ZipFile(BytesIO(raw)) as archive:result=json.loads(archive.read('report.json'))
        result['limitations'][0]='Another implementation; these checks are deferred.'
        result['evaluation_id']='12345678-1234-4234-8234-123456789abc'
        validate_success(result,'goodAccessible.pdf',original)
        result['output_pdf']['sha256']='bad'
        with self.assertRaises(AssertionError):validate_success(result,'goodAccessible.pdf',original)

    def test_contract_uses_json_and_expected_http_errors(self):
        import suite
        from unittest.mock import patch
        with patch.dict('os.environ',{'TESTER_MODE':'contract'}):
            for test_id,name in CASES:
                with self.subTest(name=name):
                    raw=(ROOT/'fixtures'/'expected'/(Path(name).stem+'_review.zip')).read_bytes()
                    with ZipFile(BytesIO(raw)) as archive:result=json.loads(archive.read('report.json'))
                    code=result.get('error_code')
                    status={'FILE_TOO_LARGE':413,'INVALID_FILE_TYPE':415,'PASSWORD_PROTECTED_PDF':422,'ENCRYPTED_PDF':422}.get(code,200)
                    if code:result['message']='Different valid explanation.'
                    with patch.object(suite,'request',return_value=(status,{'Content-Type':'application/json'},json.dumps(result).encode())) as request:
                        outcome=suite.run_case(test_id,name,'http://example.test','session')
                        self.assertEqual(outcome['outcome'],'pass',outcome)
                        self.assertEqual(request.call_args.kwargs['accept'],'application/json')
                    with patch.object(suite,'request',return_value=(200 if status!=200 else 422,{'Content-Type':'application/json'},json.dumps(result).encode())):
                        self.assertEqual(suite.run_case(test_id,name,'http://example.test','session')['outcome'],'fail')

    def test_abort_keeps_report_and_consumes_session(self):
        sid='abort-test'
        app.sessions[sid]={'target_url':'http://example.test','state':'ready','report':None}
        with patch.object(app,'run_case',side_effect=FileNotFoundError('fixture missing')), patch.object(app,'read_code',return_value={'covered':None,'total':None,'basis':'Unavailable'}):
            response=app.run(app.Run(session_id=sid))
        self.assertEqual(response.status_code,500)
        report=app.report(sid)
        self.assertEqual(len(report['results']),6)
        self.assertEqual(report['results'][0]['outcome'],'error')
        self.assertTrue(all(r['outcome']=='skip' for r in report['results'][1:]))
        self.assertEqual(app.run(app.Run(session_id=sid)).status_code,409)
        self.assertEqual(app.report(sid),report)

if __name__=='__main__': unittest.main()
