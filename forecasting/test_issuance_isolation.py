import json
from datetime import timedelta
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import cycle
import live
import snapshots
import isolated_issuance
from forecast_coverage import write_coverage


class IsolationTests(unittest.TestCase):
    def test_one_bad_game_does_not_block_next_or_shadows(self):
        report = {'errors': [], 'forecastRuns': []}
        def publish(day, event_id):
            if event_id == 'bad': raise ValueError('venue classification mismatch')
            return {'event': event_id}
        with patch.object(live, 'publish', side_effect=publish), patch.object(cycle.feeds, 'latest'), patch.object(isolated_issuance, 'publish_shadow_event', return_value={}) as shadow:
            cycle.issue_targets([{'eventId':'bad'}, {'eventId':'good'}], '2026-10-11', 2026, False, report)
        self.assertEqual(report['errors'][0]['eventId'], 'bad')
        self.assertEqual(report['forecastRuns'][0], {'event':'good'})
        shadow.assert_called_once_with('2026-10-11', 'good')

    def test_capture_failure_is_isolated(self):
        report = {'errors': [], 'forecastRuns': []}
        with tempfile.TemporaryDirectory() as t, patch.object(live, 'LIVE', Path(t)), patch.object(live, 'required_dates', side_effect=lambda d,a,event_id:[event_id]), patch.object(cycle.feeds,'capture',side_effect=[ValueError('down'),None]), patch.object(cycle.feeds,'latest'), patch.object(live,'publish',return_value={}) as publish, patch.object(isolated_issuance,'publish_shadow_event',return_value={}):
            cycle.issue_targets([{'eventId':'bad'}, {'eventId':'good'}], '2026-10-11',2026,True,report)
        publish.assert_called_once_with('2026-10-11',event_id='good')
        self.assertEqual(report['errors'][0]['eventId'],'bad')

    def test_scoped_publish_keeps_venue_guard_and_deadline(self):
        games = live.parse_games((live.ROOT/'data/raw/nflverse-games.csv').read_bytes())
        targets = [g for g in games if g['localDate'].isoformat()=='2023-09-10']
        good = targets[-1]
        at = (good['kickoff']-timedelta(hours=30)).isoformat()
        def verify(targets, rows, games, at):
            self.assertEqual([g['eventId'] for g in targets],[good['eventId']])
            raise ValueError('venue classification mismatch')
        with tempfile.TemporaryDirectory() as t, patch.object(live,'current_games',return_value=({},games)), patch.object(snapshots,'now',return_value=at), patch.object(live,'verify_inputs',side_effect=verify):
            with self.assertRaisesRegex(ValueError,'venue classification'):
                live.publish('2023-09-10',Path(t),event_id=good['eventId'])
            self.assertFalse(list(Path(t).rglob('*.json')))
        with tempfile.TemporaryDirectory() as t, patch.object(live,'current_games',return_value=({},games)):
            with self.assertRaisesRegex(ValueError,'deadline'):
                live.publish('2023-09-10',Path(t),event_id=good['eventId'])

    def test_persistent_coverage_excludes_prelaunch_and_future(self):
        with tempfile.TemporaryDirectory() as t:
            store=Path(t); p=store/'forecasts/outcome-logit-v1';p.mkdir(parents=True)
            (p/'start.json').write_text(json.dumps({'kickoffAt':'2026-10-01T17:00:00Z'}))
            games=[{'eventId':n,'kickoff':snapshots.parse_time(k)} for n,k in [('before','2026-09-01T17:00:00Z'),('missed','2026-10-11T17:00:00Z'),('future','2026-10-20T17:00:00Z')]]
            r=write_coverage(games,store,'2026-10-12T00:00:00Z')
            self.assertEqual([g['eventId'] for g in r['missed']],['missed'])
            self.assertEqual(len(r['missed'][0]['missingModels']),3)
            self.assertEqual(write_coverage([],store,'2026-10-13T00:00:00Z')['missedGames'],1)

    def test_coverage_alert_deduplicates_and_reopens_only_for_new_gaps(self):
        import cloud_alert
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); folder=root/'live/reports';folder.mkdir(parents=True)
            (folder/'forecast-coverage.json').write_text(json.dumps({'missed':[{'eventId':'game','missingModels':['outcome-logit-v1']}]}))
            with patch.object(cloud_alert,'__file__',str(root/'cloud_alert.py')), patch.dict(cloud_alert.os.environ,{'REPOSITORY':'raviteja2390/nfl-forecasting-lab'}):
                with patch.object(cloud_alert,'gh',return_value='[]') as gh:
                    cloud_alert.coverage_alert()
                    create=gh.call_args_list[-1].args
                    body=create[-1]
                existing=json.dumps([{'number':1,'title':'NFL forecast coverage gaps require review','body':body,'state':'CLOSED'}])
                with patch.object(cloud_alert,'gh',return_value=existing) as gh:
                    cloud_alert.coverage_alert()
                    self.assertEqual(gh.call_count,1)
                existing=json.dumps([{'number':1,'title':'NFL forecast coverage gaps require review','body':'older gap list','state':'CLOSED'}])
                with patch.object(cloud_alert,'gh',return_value=existing) as gh:
                    cloud_alert.coverage_alert()
                    self.assertEqual(gh.call_args_list[-1].args[:2],('issue','reopen'))
