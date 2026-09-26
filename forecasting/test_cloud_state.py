import gzip
import json
from pathlib import Path
import tempfile
import unittest

import cloud_state


class CloudStateTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name); self.root=self.base/'source'; self.state=self.base/'state'
        self.name='forecasting/data/feeds/blobs/example'
        self.source=self.root/self.name; self.source.parent.mkdir(parents=True); self.source.write_bytes(b'original bytes')

    def test_roundtrip_and_deterministic_compression(self):
        cloud_state.save(self.state,self.root)
        packed=self.state/'files'/(self.name+'.gz'); first=packed.read_bytes()
        cloud_state.save(self.state,self.root); self.assertEqual(packed.read_bytes(),first)
        destination=self.base/'restored'; cloud_state.restore(self.state,destination)
        self.assertEqual((destination/self.name).read_bytes(),b'original bytes')

    def test_archive_corruption_is_rejected(self):
        cloud_state.save(self.state,self.root)
        (self.state/'files'/(self.name+'.gz')).write_bytes(gzip.compress(b'tampered'))
        with self.assertRaisesRegex(ValueError,'checksum'): cloud_state.restore(self.state,self.base/'restored')

    def test_immutable_change_and_disappearance_are_rejected(self):
        cloud_state.save(self.state,self.root)
        self.source.write_bytes(b'edited')
        with self.assertRaisesRegex(ValueError,'Immutable'): cloud_state.save(self.state,self.root)
        self.source.unlink()
        with self.assertRaisesRegex(ValueError,'discard'): cloud_state.save(self.state,self.root)

    def test_unsafe_paths_and_empty_archive_fail_closed(self):
        for name in ('../secret','/tmp/secret','forecasting/live/../secret','forecasting/live/.env','unrelated/path'):
            with self.assertRaises(ValueError): cloud_state.safe_path(name)
        with self.assertRaisesRegex(ValueError,'manifest missing'): cloud_state.restore(self.state,self.base/'restored')

    def test_existing_issued_forecast_cannot_be_replaced(self):
        cloud_state.save(self.state,self.root)
        dest=self.base/'restore'; target=dest/self.name; target.parent.mkdir(parents=True); target.write_bytes(b'conflict')
        with self.assertRaisesRegex(ValueError,'Immutable local'): cloud_state.restore(self.state,dest)

    def test_mutable_status_can_advance(self):
        status=self.root/'forecasting/live/operations/status.json'; status.parent.mkdir(parents=True); status.write_text('{"state":"running"}')
        cloud_state.save(self.state,self.root)
        status.write_text('{"state":"succeeded"}'); cloud_state.save(self.state,self.root)
        dest=self.base/'restore'; cloud_state.restore(self.state,dest)
        self.assertEqual(json.loads((dest/'forecasting/live/operations/status.json').read_text())['state'],'succeeded')


if __name__=='__main__': unittest.main()
