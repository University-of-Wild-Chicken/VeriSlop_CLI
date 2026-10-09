"""Child-side test execution. Expected outputs stay in the supervisor, never here."""
import contextlib
import importlib.util
import io
import json
import signal
import sys
import time


def alarm(_signum, _frame):
    raise TimeoutError("case time budget exceeded")


def main():
    request = json.load(sys.stdin)
    signal.signal(signal.SIGALRM, alarm)
    sys.path.insert(0, request["root"])
    results = []
    module = None
    load_error = None
    try:
        signal.setitimer(signal.ITIMER_REAL, request["case_seconds"])
        spec = importlib.util.spec_from_file_location("candidate", request["entry_file"])
        module = importlib.util.module_from_spec(spec)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            spec.loader.exec_module(module)
        function = getattr(module, "solve")
        if not callable(function):
            raise TypeError("solve is not callable")
    except BaseException as exc:
        load_error = {"type": type(exc).__name__, "message": str(exc)[:1000]}
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
    for case in request["cases"]:
        start = time.monotonic()
        record = {"id": case["id"]}
        if load_error:
            record["error"] = load_error
        else:
            try:
                signal.setitimer(signal.ITIMER_REAL, request["case_seconds"])
                # Fresh JSON copy prevents one test from altering a later test's input.
                data = json.loads(json.dumps(case["input"], allow_nan=False))
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    value = function(data)
                record["observed"] = json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))
            except BaseException as exc:
                record["error"] = {"type": type(exc).__name__, "message": str(exc)[:1000]}
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0)
        record["seconds"] = round(time.monotonic() - start, 6)
        results.append(record)
    print(json.dumps({"results": results}, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
