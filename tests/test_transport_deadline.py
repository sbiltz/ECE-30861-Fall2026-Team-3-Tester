from io import BytesIO
from unittest.mock import patch
import unittest
from tester import transport

class TransportDeadlineTests(unittest.TestCase):
    def test_slow_body_counts_toward_whole_request_deadline_without_retry(self):
        clock=[0.0]
        class SlowReply(BytesIO):
            status=200
            headers={'Content-Type':'application/json'}
            def read1(self,size=-1):
                clock[0]=61.0
                return super().read1(size)
        with patch.object(transport,'monotonic',side_effect=lambda:clock[0],create=True),patch.object(transport,'urlopen',return_value=SlowReply(b'{}')) as call:
            with self.assertRaises(TimeoutError):transport.request('GET','http://example.test/health')
        self.assertEqual(call.call_count,1)

    def test_response_header_delay_counts_toward_setup_deadline(self):
        clock=[0.0]
        class Reply(BytesIO):
            status=201
            headers={}
        def delayed(*args,**kwargs):
            clock[0]=11.0
            return Reply(b'{}')
        with patch.object(transport,'monotonic',side_effect=lambda:clock[0],create=True),patch.object(transport,'urlopen',side_effect=delayed):
            with self.assertRaises(TimeoutError):transport.request('POST','http://example.test/test/setup',payload={},timeout=10)
