import unittest
from tester import suite


class ContractSchemaTests(unittest.TestCase):
    def test_current_shared_version_is_loaded(self):
        self.assertEqual(suite.SPEC['info']['version'],'0.5.0')

    def test_detected_status_is_valid_for_unrepaired_auto_fixable_issue(self):
        suite.validate('Finding',{'finding_id':'F-1','check_id':'CHK-TITLE',
            'issue_type':'missing_document_title','wcag_criterion':'2.4.2','wcag_level':'A',
            'location':{'page':None,'description':'Document title metadata'},
            'evaluation_result':'fail','classification':'auto_fixable','status':'detected',
            'fix_description':'Supply a meaningful title.'})

    def test_new_invalid_request_error_is_valid(self):
        suite.validate('Error',{'status':'error','error_code':'INVALID_REQUEST','message':'Invalid output format.'})

    def test_malformed_optional_bbox_is_rejected(self):
        with self.assertRaises(AssertionError):
            suite.validate('Location',{'description':'Page region','bbox':[1,2]})
