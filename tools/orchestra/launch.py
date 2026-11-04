"""The launcher: the orchestrator's clock and its only door to the proxy.

A launchd timer runs ``launch.py once`` every ten minutes.  This module runs
one cycle of ``orchestra`` under a lock file, records a crash where a human
will see it, and hands the scheduler the one object in the orchestra that may
open a connection: a client for the local proxy, and nothing else.

The interface and the rules are set out in tests/test_orchestra_launch.py.
Python 3.9, standard library only.
"""

import datetime as dt
import errno
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# imported from this file's own folder, so a timer may run it from anywhere
sys.path.insert(0, str(Path(__file__).resolve().parent))

import orchestra  # noqa: E402

MODEL = "deepseek-flash"
DEFAULT_RATES = {"gemma4:26b": 58.0, "qwen3.8:27b": 19.0}
LOCK_MAX_AGE = 2 * 3600.0          # seconds; an older lock is a dead cycle's
HEALTH_PATH = "/health"
USAGE_SUFFIX = "/usage"
CHAT_SUFFIX = "/v1/chat/completions"
JOB_NAME = re.compile(r"orch-[A-Za-z0-9_-]{1,43}")


class ProxyError(Exception):
    """The proxy was not reached, refused the job, or did not answer properly."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """The client never follows a redirect: it says so and stops."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ProxyError("the proxy tried to redirect to %s" % (newurl,))


def _local_base(base):
    """'http://127.0.0.1:<port>' or 'http://localhost:<port>'; else ValueError."""
    try:
        parts = urllib.parse.urlsplit(str(base))
    except ValueError as exc:
        raise ValueError("base %r is not a URL: %s" % (base, exc))
    if parts.scheme.lower() != "http":
        raise ValueError("base %r is not plain http" % (base,))
    if parts.username is not None or parts.password is not None:
        raise ValueError("base %r carries credentials" % (base,))
    host = (parts.hostname or "").lower()
    if host not in ("127.0.0.1", "localhost"):
        raise ValueError("base %r is not 127.0.0.1 or localhost" % (base,))
    try:
        port = parts.port
    except ValueError as exc:
        raise ValueError("base %r has no usable port: %s" % (base, exc))
    if port is None:
        raise ValueError("base %r has no port" % (base,))
    if (parts.path or "") not in ("", "/"):
        raise ValueError("base %r carries a path" % (base,))
    if parts.query or parts.fragment:
        raise ValueError("base %r carries a query or fragment" % (base,))
    return "http://%s:%d" % (host, port)


def _error_text(raw):
    """The reply's error, as ': <text>'; never the request's body."""
    if not raw:
        return ""
    text = raw.decode("utf-8", "replace").strip()
    if not text:
        return ""
    try:
        obj = json.loads(text)
    except ValueError:
        obj = None
    if isinstance(obj, dict):
        err = obj.get("error")
        if isinstance(err, dict):
            err = err.get("message") or json.dumps(err, sort_keys=True)
        if err is not None:
            return ": " + str(err)
    text = " ".join(text.split())
    return (": " + text[:200]) if text else ""


def _positive(value):
    """The value as a positive finite float, or None."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number if number > 0 else None


class ProxyClient(object):
    """The scheduler's proxy: local, plain http, never a redirect, never silent."""

    def __init__(self, base="http://127.0.0.1:8787", marks=None, timeout=900):
        self.base = _local_base(base)
        self.marks = Path(marks) if marks is not None else Path("proxy-jobs")
        try:
            self.timeout = float(timeout)
        except (TypeError, ValueError):
            raise ValueError("timeout %r is not a number" % (timeout,))
        # no proxies from the environment, no redirects, ever
        self._opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), _NoRedirect())
        # the proxy admits an orch- job only while its marker is here, so only the main user may write here
        # (Claude's read, 2026-11-03: the worker's account must never be able to mint a job)
        try:
            self.marks.mkdir(mode=0o700, parents=True, exist_ok=True)
            os.chmod(str(self.marks), 0o700)
        except (IOError, OSError):
            pass

    # ------------------------------------------------------------- transport

    def _call(self, method, path, payload=None):
        """The (status, object) of a 2xx JSON answer; ProxyError otherwise."""
        url = self.base + path
        data = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            try:
                data = json.dumps(payload).encode("utf-8")
            except (TypeError, ValueError) as exc:
                raise ProxyError("%s %s: cannot encode the request: %s"
                                 % (method, path, exc))
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=data, headers=headers,
                                         method=method)
        try:
            with self._opener.open(request, timeout=self.timeout) as answer:
                status = int(answer.getcode())
                raw = answer.read()
        except urllib.error.HTTPError as exc:
            raw = b""
            try:
                raw = exc.read()
            except (IOError, OSError, ValueError):
                pass
            try:
                status = int(exc.code)
            except (TypeError, ValueError):
                status = 0
            raise ProxyError("%s %s: HTTP %s%s"
                             % (method, path, status, _error_text(raw)))
        except ProxyError:
            raise
        except urllib.error.URLError as exc:
            raise ProxyError("%s %s: %s" % (method, path, exc.reason))
        except (IOError, OSError) as exc:
            raise ProxyError("%s %s: %s" % (method, path, exc))
        if status < 200 or status >= 300:
            raise ProxyError("%s %s: HTTP %s" % (method, path, status))
        try:
            obj = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            raise ProxyError("%s %s: the reply was not JSON" % (method, path))
        return status, obj

    # --------------------------------------------------------------- answers

    def health(self):
        """The proxy's own health: a dict, or ProxyError."""
        _status, obj = self._call("GET", HEALTH_PATH)
        if not isinstance(obj, dict):
            raise ProxyError("GET /health: the answer was not an object")
        return obj

    def chat(self, job, messages, thinking=False):
        """One deepseek-flash call, marked, costed; never an empty answer."""
        if thinking:
            raise ProxyError("chat: thinking is not permitted through the launcher")
        job = str(job)
        if not JOB_NAME.fullmatch(job):
            raise ProxyError("chat: job %r is not an orch- name" % (job,))

        path = "/j/%s" % job
        marker = self.marks / job
        try:
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_bytes(b"")
        except (IOError, OSError) as exc:
            raise ProxyError("chat: cannot mark job %s: %s" % (job, exc))
        try:
            body = {"model": MODEL, "messages": messages, "temperature": 0}
            _status, obj = self._call("POST", path + CHAT_SUFFIX, body)
            content = None
            if isinstance(obj, dict):
                choices = obj.get("choices")
                if isinstance(choices, list) and choices:
                    first = choices[0]
                    if isinstance(first, dict):
                        message = first.get("message")
                        if isinstance(message, dict):
                            content = message.get("content")
            if not isinstance(content, str):
                raise ProxyError("chat: job %s: the 200 had no "
                                 "choices[0].message.content" % (job,))
            return {"content": content, "cost": self._cost(path)}
        finally:
            try:
                marker.unlink()
            except (IOError, OSError):
                pass

    def _cost(self, path):
        """The job's cost from GET <path>/usage; 0.0 if it cannot be read."""
        try:
            _status, obj = self._call("GET", path + USAGE_SUFFIX)
        except ProxyError:
            return 0.0
        if isinstance(obj, dict):
            try:
                value = float(obj.get("cost"))
            except (TypeError, ValueError):
                return 0.0
            if value == value and value >= 0.0:
                return value
        return 0.0


# --------------------------------------------------------------------- rates

def load_rates(path):
    """Model -> calls a minute; a missing, broken or bad entry is the default."""
    rates = dict(DEFAULT_RATES)
    try:
        with open(str(path), "r", encoding="utf-8") as f:
            data = json.load(f)
    except (IOError, OSError, ValueError):
        return rates
    if not isinstance(data, dict):
        return rates
    for model, value in data.items():
        number = _positive(value)
        if number is not None:
            rates[str(model)] = number
    return rates


# --------------------------------------------------------------------- clock

def _utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _record(home, message):
    """A crash, written where the human's status file lives."""
    payload = {"error": message, "now": _utc_now()}
    try:
        (Path(home) / "status.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
    except (IOError, OSError):
        pass


def run_once(home, grunt, proxy, now=None):
    """One cycle under a lock: 0 ran, 1 crashed, 2 another cycle is running."""
    home = Path(home)
    grunt = Path(grunt)
    try:
        home.mkdir(parents=True, exist_ok=True)
    except (IOError, OSError):
        return 1

    lock = home / "cycle.lock"
    if lock.exists():
        try:
            age = time.time() - lock.stat().st_mtime
        except (IOError, OSError):
            age = 0.0
        if age < LOCK_MAX_AGE:
            return 2
        try:
            lock.unlink()             # a dead cycle's lock; take it over
        except (IOError, OSError):
            return 2

    try:
        handle = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except OSError as exc:
        return 2 if exc.errno == errno.EEXIST else 1
    os.close(handle)

    # the security seat, 2026-11-03: the home is the main user's alone (the pass names, the results and this
    # module's own folder stay unreadable to the worker's account), and a marker a killed cycle left behind is
    # swept, so no orch- name stays admitted by the proxy between calls
    try:
        os.chmod(str(home), 0o700)
    except (IOError, OSError):
        pass
    marks = home / "proxy-jobs"
    if marks.is_dir():
        for stale in marks.iterdir():
            try:
                stale.unlink()
            except (IOError, OSError):
                pass

    try:
        try:
            env = orchestra.Env(home, grunt, now, proxy,
                                load_rates(home / "rates.json"))
            orchestra.cycle(env)
        except Exception as exc:      # noqa: BLE001 - one warning, then silence
            _record(home, "%s: %s" % (type(exc).__name__, exc))
            return 1
        return 0
    finally:
        try:
            lock.unlink()
        except (IOError, OSError):
            pass


# ---------------------------------------------------------------------- main

def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    while args and str(args[0]).startswith("-"):
        args = args[1:]
    if args and os.path.basename(str(args[0])) in ("launch.py", "launch"):
        args = args[1:]
    if args != ["once"]:
        sys.stderr.write("usage: launch.py once\n")
        return 2
    home = Path.home() / "orchestra"
    try:
        proxy = ProxyClient(marks=home / "proxy-jobs")
    except ValueError as exc:
        sys.stderr.write("launch: %s\n" % (exc,))
        return 1
    return run_once(home, Path.home() / "grunt", proxy)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
