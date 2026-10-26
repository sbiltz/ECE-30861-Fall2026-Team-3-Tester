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
