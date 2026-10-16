"""Offline budget tests: real Broker, controlled provider calls, no credentials."""
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from verislop.errors import InfrastructureError
from verislop.providers.adapters import Completion
from verislop.providers.broker import Broker, Budget
from verislop.providers.config import Resolved
from verislop.providers.http import ProviderError


def broker(budget, output=70):
    conf = {
        'review': {'budgets': {'max_calls_per_instance': 8, 'max_total_tokens': 100,
                               'max_provider_retries': 0}},
        'providers': {'fake': {'concurrency': 2, 'api_family': 'responses',
                               'request_timeout_seconds': 1}},
        'agents': {'a': {'provider': 'fake', 'model_ref': 'mock', 'max_output_tokens': output}},
    }
    return Broker(Resolved(conf, {'fake': {'base_url': 'unused', 'auth_scheme': 'none'}},
                           {'fake'}, {'a'}), None, budget)


def result(tokens):
    return Completion('ok', 'mock', 'mock', None, 0, tokens)


class BrokerBudgetTests(unittest.TestCase):
    def call(self, b, instance='one'):
        return b.call('a', instance, '', '', 'test')

    def test_single_response_can_cross_soft_threshold(self):
        budget = Budget(max_total_tokens=100)
        b = broker(budget)
        with patch('verislop.providers.broker.complete', return_value=result(140)) as complete:
            self.call(b)
            self.assertEqual(budget.used_tokens, 140)  # never clamp away real reported usage
            with self.assertRaises(InfrastructureError):
                self.call(b, 'next')
            self.assertEqual(complete.call_count, 1)

    def test_concurrent_admission_includes_shared_reservation(self):
        budget = Budget(max_total_tokens=100)
        b = broker(budget)
        other = broker(budget)  # independent Broker, shared global budget
        entered, release = threading.Event(), threading.Event()
        def complete(*args, **kwargs):
            entered.set()
            if not release.wait(timeout=3):
                raise AssertionError("provider release timed out")
            return result(70)
        with patch('verislop.providers.broker.complete', side_effect=complete) as mock:
            with ThreadPoolExecutor(2) as pool:
                first = pool.submit(self.call, b)
                try:
                    self.assertTrue(entered.wait(timeout=3))
                    self.assertEqual(budget.reserved_tokens, 70)
                    second = pool.submit(self.call, other, 'two')
                    with self.assertRaises(InfrastructureError):
                        second.result(timeout=3)
                finally:
                    release.set()
                first.result(timeout=3)
            self.assertEqual(mock.call_count, 1)
        self.assertEqual(budget.used_tokens, 70)
        self.assertEqual(budget.reserved_tokens, 0)
        self.assertNotIn('two', budget.calls)

    def test_settlement_releases_unused_reservation(self):
        budget = Budget(max_total_tokens=100)
        b = broker(budget)
        with patch('verislop.providers.broker.complete', return_value=result(20)):
            self.call(b)
            self.call(b, 'two')
        self.assertEqual(budget.used_tokens, 40)
        self.assertEqual(budget.reserved_tokens, 0)

    def test_prompt_bytes_are_reserved_and_equality_is_admitted(self):
        budget = Budget(max_total_tokens=100)
        b = broker(budget, output=98)
        with patch('verislop.providers.broker.complete', return_value=result(100)) as mock:
            b.call('a', 'one', 'é', '', 'test')
            self.assertEqual(mock.call_count, 1)
        self.assertEqual(budget.used_tokens, 100)
        self.assertEqual(budget.reserved_tokens, 0)

    def test_oversized_request_is_not_dispatched(self):
        budget = Budget(max_total_tokens=100)
        with patch('verislop.providers.broker.complete') as mock:
            with self.assertRaises(InfrastructureError):
                self.call(broker(budget, output=101))
            mock.assert_not_called()
        self.assertEqual(budget.calls, {})
        self.assertEqual(budget.reserved_tokens, 0)

    def test_failures_release_reservation_and_preserve_call_limit(self):
        for error in (ProviderError('bad_response', 'test'), RuntimeError('unexpected')):
            with self.subTest(error=type(error).__name__):
                budget = Budget(max_total_tokens=100, max_calls_per_instance=1, max_retries=0)
                b = broker(budget)
                with patch('verislop.providers.broker.complete', side_effect=error) as mock:
                    with self.assertRaises((InfrastructureError, RuntimeError)):
                        self.call(b)
                    self.assertEqual(budget.reserved_tokens, 0)
                    with self.assertRaises(InfrastructureError):
                        self.call(b)
                    self.assertEqual(mock.call_count, 1)
                self.assertEqual(budget.calls['one'], 1)
                self.assertEqual(budget.used_tokens, 0)  # unknown failed-request usage

    def test_retry_is_one_logical_call(self):
        budget = Budget(max_total_tokens=100, max_retries=1)
        b = broker(budget)
        with patch('verislop.providers.broker.complete', side_effect=[
                ProviderError('rate_limit', 'retry', retryable=True), result(30)]) as mock:
            with patch('verislop.providers.broker.time.sleep'):
                self.call(b)
            self.assertEqual(mock.call_count, 2)
        self.assertEqual(budget.calls['one'], 1)
        self.assertEqual(budget.used_tokens, 30)
        self.assertEqual(budget.reserved_tokens, 0)

    def test_missing_usage_does_not_fabricate_actual_usage(self):
        budget = Budget(max_total_tokens=100)
        b = broker(budget)
        unknown = Completion('ok', 'mock', 'mock', None, None, None)
        with patch('verislop.providers.broker.complete', return_value=unknown):
            self.call(b)
        self.assertEqual(budget.used_tokens, 0)  # reported sum, not proof of zero cost
        self.assertEqual(budget.reserved_tokens, 0)

    def test_reservations_preserve_concurrency_when_both_fit(self):
        budget = Budget(max_total_tokens=100)
        b = broker(budget, output=50)
        barrier = threading.Barrier(2)
        def complete(*args, **kwargs):
            barrier.wait(timeout=3)
            return result(40)
        with patch('verislop.providers.broker.complete', side_effect=complete):
            with ThreadPoolExecutor(2) as pool:
                futures = [pool.submit(self.call, b, str(i)) for i in range(2)]
                for future in futures:
                    future.result(timeout=5)
        self.assertEqual(budget.used_tokens, 80)
        self.assertEqual(budget.reserved_tokens, 0)

    def test_credential_failure_releases_reservation_without_dispatch(self):
        budget = Budget(max_total_tokens=100)
        b = broker(budget)
        with patch.object(b, '_secret', side_effect=InfrastructureError('credential unavailable')):
            with patch('verislop.providers.broker.complete') as mock:
                with self.assertRaises(InfrastructureError):
                    self.call(b)
                mock.assert_not_called()
        self.assertEqual(budget.reserved_tokens, 0)
        self.assertEqual(budget.calls['one'], 1)
