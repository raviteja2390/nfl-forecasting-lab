import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import promotion_report
import research_register as register


class RegisterTests(unittest.TestCase):
    def test_inventory_includes_tuning_and_missing_ci_is_explicit(self):
        report=register.review()
        self.assertEqual(report['errors'],[])
        self.assertEqual(report['counts'],{'2023':26,'2024':5,'2024-2025':5,'2025':5})
        margin=[e for e in report['entries'] if e['model']=='margin-ridge-v1']
        self.assertTrue(all(e['ciExcludesZero'] is None for e in margin))
        self.assertFalse(report['historicalPromotionAllowed'])
        self.assertEqual(report['opponentAdjustedLogLoss']['confidenceLevel'],.99)
        self.assertFalse(report['opponentAdjustedLogLoss']['favorsCandidate'])

    def test_no_overwrite_and_missing_entry_blocks_audit(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d);entry=register.historical_entries()[0]
            register.append(entry,folder);register.append(entry,folder)
            changed={**entry,'logLossImprovement':999}
            with self.assertRaises(ValueError):register.append(changed,folder)
            self.assertTrue(register.review(folder)['errors'])

    def test_added_test_increases_family_count_and_widens_interval(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d)
            for e in register.historical_entries():register.append(e,folder)
            before=register.review(folder)
            e=copy.deepcopy(next(e for e in before['entries'] if e['cohort']=='2024-2025'))
            e.update(id='test-additional-trial',variant='additional-trial',interval95=None,ciExcludesZero=None,ciFavorsCandidate=None,ciStatus='not-computed')
            register.append(e,folder);after=register.review(folder)
            self.assertEqual(after['counts']['2024-2025'],6)
            self.assertLessEqual(after['opponentAdjustedLogLoss']['interval'][0],before['opponentAdjustedLogLoss']['interval'][0])
            self.assertGreaterEqual(after['opponentAdjustedLogLoss']['interval'][1],before['opponentAdjustedLogLoss']['interval'][1])

    def test_promotion_integrity_blocks_incomplete_register(self):
        with tempfile.TemporaryDirectory() as d,patch.object(register,'review',return_value={'errors':['unlogged model'],'counts':{}}):
            report=promotion_report.evaluate(Path(d),at='2027-02-08T12:00:00Z')
            self.assertTrue(report['errors'])
            self.assertTrue(all(not c['gates']['integrity'] for c in report['comparisons'].values()))
            self.assertFalse(report['automaticPromotion'])


if __name__=='__main__':unittest.main()
