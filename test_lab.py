import unittest
from unittest.mock import patch
import lab


class VDiffGateTests(unittest.TestCase):
    def report(self, **changes):
        return dict(Workflow='customer2shards', Keyspace='customer', State='completed',
                    HasMismatch=False, RowsCompared=60) | changes

    def test_accepts_completed_nonempty_diff(self):
        self.assertEqual(lab.validate_vdiff(self.report(), 'customer2shards'), 60)

    def test_rejects_unsafe_reports(self):
        for report in [None, {}, self.report(State='started'),
                       self.report(HasMismatch=True), self.report(HasMismatch='false'),
                       self.report(RowsCompared=0), self.report(RowsCompared=True),
                       self.report(Workflow='old_workflow'), self.report(Keyspace='other'),
                       self.report(Errors={'-80': 'failed'}),
                       self.report(ShardSummaries={'-80': {'State': 'error'}})]:
            with self.subTest(report=report), self.assertRaises(ValueError):
                lab.validate_vdiff(report, 'customer2shards')

    def test_mismatch_prevents_all_traffic_changes(self):
        with patch.object(lab, 'check', side_effect=ValueError('mismatch')), patch.object(lab, 'wf') as wf:
            with self.assertRaises(ValueError): lab.switch('reshard')
            wf.assert_not_called()

    def test_reads_switch_before_writes_and_both_have_dry_run(self):
        with patch.object(lab, 'check') as check, patch.object(lab, 'wf') as wf:
            lab.switch('reshard')
            check.assert_called_once_with('reshard')
            self.assertEqual([c.args for c in wf.call_args_list], [
                ('reshard', 'switchtraffic', '--tablet-types', 'replica', '--dry-run'),
                ('reshard', 'switchtraffic', '--tablet-types', 'replica'),
                ('reshard', 'switchtraffic', '--tablet-types', 'primary', '--dry-run'),
                ('reshard', 'switchtraffic', '--tablet-types', 'primary'),
                ('reshard', 'status')])

    def test_read_switch_failure_prevents_write_switch(self):
        with patch.object(lab, 'check'), patch.object(lab, 'wf', side_effect=[None, RuntimeError('fail')]) as wf:
            with self.assertRaises(RuntimeError): lab.switch('move')
            self.assertEqual(wf.call_count, 2)

    def test_kubectl_always_targets_dedicated_context(self):
        with patch.object(lab, 'run') as run:
            lab.kubectl('get', 'pods')
            self.assertEqual(run.call_args.args[0], ['kubectl', '--context', 'vitess-lab', '-n', 'vitess-lab', 'get', 'pods'])

    def test_old_vdiff_not_used(self):
        import json
        with patch.object(lab, 'vt', side_effect=['', json.dumps(self.report())]) as vt:
            lab.check('reshard')
            create, show = (c.args for c in vt.call_args_list)
            self.assertEqual(create[5], 'create')
            self.assertEqual(show[5], 'show')
            self.assertEqual(create[6], show[6])
            self.assertNotEqual(show[6], 'last')


if __name__ == '__main__': unittest.main()
