from datetime import date
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cycle
import live
import operations
import recheck_results as recheck
import snapshots
from score_live import score_store


class OperationsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.store=Path(self.temp.name)

    def test_failure_keeps_last_success_and_is_recorded(self):
        with patch.object(snapshots,'now',return_value='2026-09-27T14:06:00Z'):
            operations.record_status('2026-09-27T14:05:00Z',report={'errors':[]},store=self.store)
        operations.record_status('2026-09-27T15:05:00Z',error=ValueError('download failed'),store=self.store)
        state=json.loads((self.store/'operations/status.json').read_text())
        self.assertEqual(state['state'],'failed')
        self.assertEqual(state['lastSuccessAt'],'2026-09-27T14:06:00Z')
        self.assertEqual(len(list((self.store/'operations/failures').glob('*.json'))),1)

    def test_cycle_lock_rejects_overlap(self):
        with operations.cycle_lock(self.store):
            with self.assertRaisesRegex(RuntimeError,'already running'):
                with operations.cycle_lock(self.store): pass

    def test_due_accounts_for_game_day_midnight_and_grace(self):
        dates={'2026-09-27'}
        self.assertEqual(operations.latest_due('2026-09-27T14:24:00Z',dates).isoformat(),'2026-09-27T13:05:00+00:00')
        self.assertEqual(operations.latest_due('2026-09-27T14:25:00Z',dates).isoformat(),'2026-09-27T14:05:00+00:00')
        self.assertEqual(operations.latest_due('2026-09-28T04:15:00Z',dates).isoformat(),'2026-09-28T03:05:00+00:00')
        self.assertEqual(operations.latest_due('2026-09-29T20:00:00Z',dates).isoformat(),'2026-09-29T04:05:00+00:00')

    def test_due_preserves_repeated_dst_hour(self):
        dates={'2026-11-01'}
        self.assertEqual(operations.latest_due('2026-11-01T06:35:00Z',dates).isoformat(),'2026-11-01T06:05:00+00:00')

    def test_health_alert_dedup_and_recovery(self):
        body=b'game_type,gameday\nREG,2026-09-27\nREG,2026-12-01\n'
        with patch.object(snapshots,'select_as_of',return_value={'found':True,'observation':{}}), patch.object(snapshots,'verified_body',return_value=body):
            first=operations.check_health(self.store,at='2026-09-27T14:35:00Z')
            again=operations.check_health(self.store,at='2026-09-27T14:36:00Z')
            self.assertTrue(first['notify']); self.assertFalse(first['healthy']); self.assertFalse(again['notify'])
            operations.atomic_json(self.store/'operations/status.json',{'state':'succeeded','lastSuccessAt':'2026-09-27T14:30:00Z'})
            recovered=operations.check_health(self.store,at='2026-09-27T14:37:00Z')
            self.assertTrue(recovered['notify']); self.assertTrue(recovered['healthy'])

    def test_bad_schedule_fails_closed(self):
        with patch.object(snapshots,'select_as_of',return_value={'found':False,'reason':'stale'}):
            self.assertFalse(operations.check_health(self.store,at='2026-09-27T14:35:00Z')['healthy'])

    def test_cycle_exception_logged_offline_does_not_refresh_heartbeat(self):
        with patch.object(live,'LIVE',self.store),patch.object(cycle,'_run_cycle',side_effect=RuntimeError('source down')):
            with self.assertRaisesRegex(RuntimeError,'source down'): cycle.run_cycle()
        self.assertEqual(json.loads((self.store/'operations/status.json').read_text())['state'],'failed')
        original=(self.store/'operations/status.json').read_bytes()
        with patch.object(live,'LIVE',self.store),patch.object(cycle,'_run_cycle',return_value={'errors':[]}): cycle.run_cycle(False)
        self.assertEqual(original,(self.store/'operations/status.json').read_bytes())

    def test_recent_settled_and_old_pending_dates(self):
        folder=self.store/'forecasts/outcome-logit-v1'; folder.mkdir(parents=True)
        for event,day in [('recent','2026-09-26'),('old','2026-09-01'),('pending','2026-08-01'),('future','2026-10-01')]:
            (folder/f'{event}.json').write_text(json.dumps({'eventId':event,'dateEastern':day}))
        with patch.object(recheck,'latest_results',return_value={'recent':{},'old':{}}):
            self.assertEqual(recheck.dates_to_recheck(self.store,date(2026,9,27)),['2026-08-01','2026-09-26'])

    def test_correction_keeps_original_and_records_change(self):
        folder=self.store/'results/event'; folder.mkdir(parents=True)
        old={'eventId':'event','homeScore':20,'awayScore':17,'finalizedAt':'2026-09-27T21:00:00Z','espnObservationId':'old'}
        (folder/'old.json').write_text(json.dumps(old))
        original=(folder/'old.json').read_bytes()
        def settle(day,store):
            (folder/'new.json').write_text(json.dumps({**old,'homeScore':19,'finalizedAt':'2026-09-28T01:00:00Z','espnObservationId':'new'}))
            return {'date':day,'pending':[],'sourceDisagreements':[],'resultsStored':1}
        with patch.object(live,'settle',side_effect=settle):
            report=recheck.settle_and_audit('2026-09-27',self.store)
        self.assertEqual(len(report['corrections']),1)
        self.assertEqual(original,(folder/'old.json').read_bytes())

    def test_dispute_withholds_old_score_until_recheck_resolves(self):
        f={'eventId':'2026_03_LAC_BUF','mode':'prospective','modelVersion':'outcome-logit-v1','generatedAt':'2026-09-26T14:00:00Z','featureCutoffAt':'2026-09-26T13:59:00Z','kickoffAt':'2026-09-27T17:00:00Z','probabilities':{'homeWin':.6,'awayWin':.39,'tie':.01}}
        operations.atomic_json(self.store/'forecasts/outcome-logit-v1'/f"{f['eventId']}.json",f)
        operations.atomic_json(self.store/'results'/f['eventId']/'original.json',{'eventId':f['eventId'],'homeScore':24,'awayScore':17,'finalizedAt':'2026-09-27T21:00:00Z','timingBasis':'observed-final-in-two-sources','espnObservationId':'one'})
        audit={'date':'2026-09-27','checkedAt':'2026-09-28T01:00:00Z','sourceDisagreements':[f['eventId']],'previouslyFinalNowPending':[]}
        operations.atomic_json(self.store/'rechecks/one.json',audit)
        self.assertEqual(score_store(self.store,'2026-09-27T22:00:00Z')['models']['outcome-logit-v1']['games'],1)
        self.assertEqual(score_store(self.store,'2026-09-28T02:00:00Z')['models']['outcome-logit-v1']['disputed'],1)
        operations.atomic_json(self.store/'rechecks/two.json',{**audit,'checkedAt':'2026-09-28T03:00:00Z','sourceDisagreements':[]})
        self.assertEqual(score_store(self.store,'2026-09-28T04:00:00Z')['models']['outcome-logit-v1']['games'],1)


class ScheduledRunTests(unittest.TestCase):
    def test_followup_does_not_collect_twice_after_success(self):
        import scheduled_run
        with tempfile.TemporaryDirectory() as temp:
            store=Path(temp)
            operations.atomic_json(store/'operations/status.json',{'state':'succeeded','lastSuccessAt':'2026-09-27T14:06:00Z'})
            body=b'game_type,gameday\nREG,2026-09-27\n'
            with patch.object(snapshots,'select_as_of',return_value={'found':True,'observation':{}}),patch.object(snapshots,'verified_body',return_value=body):
                self.assertFalse(scheduled_run.collection_due(store,store,'2026-09-27T14:35:00Z'))
                self.assertTrue(scheduled_run.collection_due(store,store,'2026-09-27T15:05:00Z'))
                operations.atomic_json(store/'operations/status.json',{'state':'failed','lastSuccessAt':'2026-09-27T14:06:00Z'})
                self.assertTrue(scheduled_run.collection_due(store,store,'2026-09-27T14:35:00Z'))


if __name__=='__main__': unittest.main()
