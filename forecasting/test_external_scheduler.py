import json
import unittest
from unittest.mock import patch
import setup_external_scheduler as setup

class ExternalSchedulerTests(unittest.TestCase):
    def test_public_only_nonforced_hourly_dispatch(self):
        j=setup.job('fixture-secret')
        self.assertIn('/nfl-forecasting-lab/actions/workflows/nfl-collector.yml/',j['url'])
        self.assertEqual(j['schedule']['minutes'],[7])
        self.assertEqual(j['schedule']['hours'],[-1])
        self.assertEqual(j['schedule']['timezone'],'UTC')
        self.assertFalse(j['saveResponses'])
        self.assertFalse(j['redirectSuccess'])
        self.assertFalse(json.loads(j['extendedData']['body'])['inputs']['force'])
        self.assertNotIn('fixture-secret',j['url'])

    def test_private_job_is_never_reused(self):
        private={'jobId':1,'title':'NFL private archive hourly dispatch','url':setup.DISPATCH.replace('nfl-forecasting-lab','nfl-collection-archive')}
        with patch.object(setup,'request',return_value={'jobs':[private]}):
            self.assertIsNone(setup.find_job('fixture'))

    def test_existing_public_job_reused_and_ambiguity_rejected(self):
        item={'jobId':3,'title':setup.TITLE,'url':setup.DISPATCH}
        with patch.object(setup,'request',return_value={'jobs':[item]}):
            self.assertEqual(setup.find_job('fixture'),3)
        for value in ({'jobs':[item,item]},{'someFailed':True,'jobs':[]}):
            with patch.object(setup,'request',return_value=value),self.assertRaises(ValueError):
                setup.find_job('fixture')

    def test_setup_verifies_dispatch_before_creating_job(self):
        calls=[]
        def request(url,key,method='GET',body=None):
            calls.append((url,method))
            if url==setup.BASE+'/jobs' and method=='GET':return {'jobs':[]}
            if url=='https://api.github.com/repos/'+setup.REPO:return {'private':False,'full_name':setup.REPO}
            if url==setup.DISPATCH:return {}
            if method=='PUT':return {'jobId':123}
            return {'jobDetails':setup.job('github_pat_fixture')}
        with patch.object(setup,'hidden',side_effect=['fixture-api','github_pat_fixture']),patch.object(setup,'request',side_effect=request),patch('builtins.print'):
            setup.main()
        self.assertLess(calls.index((setup.DISPATCH,'POST')),calls.index((setup.BASE+'/jobs','PUT')))

    def test_redirects_not_followed(self):
        self.assertIsNone(setup.NoRedirect().redirect_request(None,None,302,'',{},'https://example.com'))
