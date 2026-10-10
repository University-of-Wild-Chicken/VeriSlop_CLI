"""Real-process regressions for the specified fail-stop native test channel."""

from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from verislop import canonical, sandbox
from verislop.targets.python_target import Harness, HarnessError


@unittest.skipUnless(sandbox.filesystem_isolation_available() and sandbox.network_isolation_available(),
                     "filesystem/network namespaces unavailable")
class FailStopHarnessChannel(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="verislop-channel-regression-")
        self.addCleanup(self.temp.cleanup)
        self.impl = Path(self.temp.name) / "impl"
        self.impl.mkdir()

    def harness(self, source: str, **kwargs) -> Harness:
        target = self.impl / "target.py"
        target.write_text(source, encoding="utf-8")
        harness = Harness(self.impl, {"target.py": canonical.digest_file(target)},
                          {"probe": ("target.py", "probe")}, **kwargs)
        self.addCleanup(harness.close)
        return harness

    def assert_closed(self, harness: Harness) -> None:
        self.assertTrue(harness.closed)
        self.assertIsNotNone(harness.proc.poll(), "failed channel still has a live process")
        self.assertEqual(bytearray(), harness._stdout_buffer)
        self.assertFalse(Path(harness.tmp).exists())
        calls = harness.calls
        started = time.monotonic()
        with patch.object(harness, "_send", wraps=harness._send) as send:
            with self.assertRaises(HarnessError) as caught:
                harness.call("probe", [])
            self.assertEqual("closed", caught.exception.kind)
            self.assertEqual({}, harness.coverage())
            send.assert_not_called()
        self.assertEqual(calls, harness.calls, "closed call consumed a request ID")
        self.assertLess(time.monotonic() - started, 0.5)
        harness.close()  # Teardown is idempotent and never sends another request.

    def test_slow_call_terminates_before_any_late_response_can_be_reused(self):
        harness = self.harness("import time\ndef probe():\n time.sleep(60)\n return 7\n",
                               per_call_timeout=0.1)
        started = time.monotonic()
        with self.assertRaises(HarnessError) as caught:
            harness.call("probe", [])
        self.assertEqual("timeout", caught.exception.kind)
        self.assertLess(time.monotonic() - started, 2)
        self.assertEqual(1, harness.calls)
        self.assert_closed(harness)

    def test_partial_line_timeout_also_irrevocably_closes(self):
        harness = self.harness("import os,time\ndef probe():\n os.write(1,b'{')\n time.sleep(60)\n",
                               per_call_timeout=0.1)
        with self.assertRaises(HarnessError) as caught:
            harness.call("probe", [])
        self.assertEqual("timeout", caught.exception.kind)
        self.assert_closed(harness)

    def test_wrong_missing_and_boolean_response_ids_are_rejected(self):
        for response_id in (0, 2, None, True):
            with self.subTest(response_id=response_id):
                response = {"op": "result", "value": {"int": "7"}}
                if response_id is not None:
                    response["id"] = response_id
                encoded = (json.dumps(response) + "\n").encode()
                harness = self.harness(f"import os\ndef probe():\n os.write(1,{encoded!r})\n return 7\n")
                with self.assertRaises(HarnessError) as caught:
                    harness.call("probe", [])
                self.assertEqual("protocol", caught.exception.kind)
                self.assert_closed(harness)

    def test_malformed_outer_response_closes_without_stale_result(self):
        replies = (b"not-json\n", b"[]\n", b'{"op":"result","id":1}\n',
                   b'{"op":"other","id":1,"value":{"int":"7"}}\n',
                   b'{"op":"result","id":1,"value":{"int":"7"},"extra":0}\n',
                   b'{"op":"exception","id":1,"type":7,"message":"bad"}\n',
                   b"[" * 2000 + b"0" + b"]" * 2000 + b"\n")
        for encoded in replies:
            with self.subTest(reply=encoded[:50]):
                harness = self.harness(f"import os\ndef probe():\n os.write(1,{encoded!r})\n return 7\n")
                with self.assertRaises(HarnessError) as caught:
                    harness.call("probe", [])
                self.assertEqual("protocol", caught.exception.kind)
                self.assert_closed(harness)

    def test_eof_and_failed_send_close_the_real_process_channel(self):
        harness = self.harness("import os\ndef probe():\n os._exit(0)\n")
        with self.assertRaises(HarnessError) as caught:
            harness.call("probe", [])
        self.assertEqual("crash", caught.exception.kind)
        self.assert_closed(harness)

        harness = self.harness("def probe():\n return 7\n")
        sandbox.kill_process_group(harness.proc)
        harness.proc.wait(timeout=2)
        with self.assertRaises(HarnessError) as caught:
            harness.call("probe", [])
        self.assertEqual("crash", caught.exception.kind)
        self.assert_closed(harness)

    def test_valid_results_and_target_exceptions_keep_the_channel_usable(self):
        harness = self.harness("def probe(value):\n if value < 0: raise ValueError('negative')\n return value + 1\n")
        self.assertEqual({"op": "result", "id": 1, "value": {"int": "8"}},
                         harness.call("probe", [{"int": "7"}]))
        self.assertEqual({"op": "exception", "id": 2, "type": "ValueError", "message": "negative"},
                         harness.call("probe", [{"int": "-1"}]))
        self.assertEqual({"op": "result", "id": 3, "value": {"int": "1"}},
                         harness.call("probe", [{"int": "0"}]))
        self.assertFalse(harness.closed)
        coverage = harness.coverage()
        self.assertIn("target.py", coverage)
        self.assertTrue(coverage["target.py"]["executed"])
        self.assertEqual(3, harness.calls)


if __name__ == "__main__":
    unittest.main()
