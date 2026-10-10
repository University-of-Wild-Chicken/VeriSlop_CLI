"""Execute the exact finite unit registry and retain per-test outcomes."""
import argparse
from pathlib import Path
import sys
import unittest
from verislop import canonical

NAMES = [
    'test_utf8_row_and_whole_wire_bounds', 'test_escaped_control_rows_obey_encoded_wire_cap',
    'test_failed_attempt_survives_real_supervisor_receipt_path', 'test_guarantee_oracle_rejected_through_wrapper',
    'test_refinement_transfer_and_candidate_proof_oracles_rejected', 'test_definition_wrapper_is_traversed',
    'test_flat_quoted_oracle_leaf_uses_exact_name_components', 'test_missing_staged_dependency_rejected',
    'test_pinned_toolchain_leaf_recorded_without_oracle', 'test_unbounded_residual_is_still_rejected',
    'test_assignment_arity_stays_strict', 'test_wrong_wire_sort_rejected', 'test_closed_record_shape_rejected',
    'test_deadline_exhaustion_remains_unresolved', 'test_unsupported_probe_keeps_unanimity_incomplete']
PREFIX = 'tests.test_vscore3_ground_support_018.GroundSupportControls.'


class Result(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.rows = {}
        self.subtests = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.rows[test.id()] = {'status': 'PASS'}

    def addFailure(self, test, error):
        super().addFailure(test, error)
        self.rows[test.id()] = {'status': 'FAIL'}

    def addError(self, test, error):
        super().addError(test, error)
        self.rows[test.id()] = {'status': 'ERROR'}

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.rows[test.id()] = {'status': 'SKIPPED', 'reason': reason}

    def addSubTest(self, test, subtest, error):
        super().addSubTest(test, subtest, error)
        self.subtests.append({'test_id': test.id(), 'subtest_id': subtest.id(), 'status': 'PASS' if error is None else 'FAIL'})
        if error is not None:
            self.rows[test.id()] = {'status': 'FAIL'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    expected = [PREFIX + name for name in NAMES]
    suite = unittest.TestLoader().loadTestsFromNames(expected)
    result = unittest.TextTestRunner(verbosity=2, resultclass=Result).run(suite)
    report = {'format': 'verislop.ground-replay-unit-control-results/1', 'registry': expected,
              'executed': result.testsRun, 'results': result.rows, 'subtests': result.subtests,
              'success': result.wasSuccessful()}
    Path(args.output).write_bytes(canonical.dumps(report))
    return 0 if result.wasSuccessful() and set(result.rows) == set(expected) and all(row['status'] == 'PASS' for row in result.rows.values()) else 2


if __name__ == '__main__':
    sys.exit(main())
