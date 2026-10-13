#!/usr/bin/env python3
"""Optional Bark notifications using only the Python standard library."""

from http.client import HTTPException
import json
import os
import re
import sys
from urllib.error import HTTPError
from urllib.parse import unquote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NoRedirects(HTTPRedirectHandler):
    """Do not forward notification credentials to a redirect destination."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def send_notification(title, body, environ=None):
    environ = os.environ if environ is None else environ
    key = environ.get("BARK_KEY", "")
    if not key:
        return True

    server = environ.get("BARK_SERVER_URL") or "https://api.day.app"
    timeout = environ.get("BARK_TIMEOUT_SECONDS") or "5"
    try:
        url = urlsplit(server)
        # Accept reverse-proxy paths, but keep device keys out of the URL.
        if (url.scheme not in ("http", "https") or not url.hostname or
                url.username is not None or url.password is not None or
                url.query or url.fragment or any(c.isspace() for c in server) or
                key in unquote(server)):
            raise ValueError
        # Accessing .port also validates malformed/out-of-range ports.
        url.port
        if not re.fullmatch(r"[1-9][0-9]?", timeout) or int(timeout) > 60:
            raise ValueError
    except ValueError:
        print("WARNING: Invalid Bark server URL or timeout; notification skipped.", file=sys.stderr)
        return False

    payload = {"device_key": key, "title": title, "body": body}
    for variable, field in (("BARK_SOUND", "sound"), ("BARK_GROUP", "group")):
        value = environ.get(variable, "")
        if value:
            payload[field] = value
    try:
        request = Request(server.rstrip("/") + "/push",
                          data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                          headers={"Content-Type": "application/json; charset=utf-8"},
                          method="POST")
        with build_opener(NoRedirects()).open(request, timeout=int(timeout)) as response:
            data = response.read(65537)
        if len(data) > 65536:
            raise ValueError
        result = json.loads(data)
        if not isinstance(result, dict) or result.get("code") != 200:
            print("WARNING: Bark rejected the notification.", file=sys.stderr)
            return False
    except HTTPError as error:
        error.close()
        print(f"WARNING: Bark notification failed (HTTP {error.code}).", file=sys.stderr)
        return False
    except (OSError, HTTPException, ValueError):
        # URLs, exception messages and response bodies may contain credentials.
        print("WARNING: Bark notification failed; check connectivity and configuration.", file=sys.stderr)
        return False
    return True


def main():
    if len(sys.argv) != 3:
        print("Usage: bark_push.py TITLE BODY", file=sys.stderr)
        return 1
    return 0 if send_notification(sys.argv[1], sys.argv[2]) else 1


if __name__ == "__main__":
    sys.exit(main())
