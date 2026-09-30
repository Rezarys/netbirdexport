"""Fetching, redaction and rendering.

The HTTP layer is kept behind a single callable so that every other part of this
package is pure and testable without a network.
"""

import csv
import io
import json
import urllib.error
import urllib.request

# Resource name as written on the command line, mapped to its API path.
# Every path here is read from the upstream REST client at
# shared/management/client/rest/ and from its own documentation links, not
# guessed from the resource name.
RESOURCES = {
    "peers": "/api/peers",
    "users": "/api/users",
    "setup-keys": "/api/setup-keys",
    "groups": "/api/groups",
    "policies": "/api/policies",
    "routes": "/api/routes",
    "nameservers": "/api/dns/nameservers",
}

DEFAULT_RESOURCES = ("peers", "users", "setup-keys", "groups")

DEFAULT_URL = "https://api.netbird.io"

# A field is never written when its own name, lowercased, is listed here or ends
# with one of REDACT_SUFFIXES. This is a name match, not a classification: see
# the README for what that does and does not guarantee.
REDACT_NAMES = frozenset(
    (
        "key",
        "token",
        "secret",
        "password",
        "passphrase",
        "private_key",
        "privatekey",
        "client_secret",
        "api_key",
        "access_token",
        "refresh_token",
    )
)

REDACT_SUFFIXES = ("_secret", "_password", "_token", "_private_key")


class ExportError(Exception):
    """Anything that should end the run with a readable message."""


def is_redacted(name):
    """True when a field with this name must never be written."""
    low = name.lower()
    if low in REDACT_NAMES:
        return True
    return any(low.endswith(suffix) for suffix in REDACT_SUFFIXES)


def redact(value, path=(), dropped=None):
    """Return value with every redacted field removed, structure preserved.

    Collects the dotted path of each removed field into dropped.
    """
    if dropped is None:
        dropped = set()
    if isinstance(value, dict):
        out = {}
        for name in value:
            here = path + (name,)
            if is_redacted(name):
                dropped.add(".".join(here))
                continue
            out[name] = redact(value[name], here, dropped)
        return out
    if isinstance(value, list):
        return [redact(item, path, dropped) for item in value]
    return value


def flatten(value, prefix=""):
    """Flatten one already redacted object into a single level of scalars.

    A nested object becomes parent.child. Every list gets a <field>_count,
    whatever it holds and even when it is empty, so that a column never appears
    or disappears just because a list happened to be empty on one run. A list of
    values also gets <field> with the values joined by a vertical bar; a list of
    objects also gets <field>_ids when every object carries a string id.
    """
    flat = {}
    if isinstance(value, dict):
        for name in value:
            key = prefix + "." + name if prefix else name
            flat.update(flatten(value[name], key))
        return flat
    if isinstance(value, list):
        flat[prefix + "_count"] = len(value)
        if not value:
            return flat
        if all(isinstance(item, dict) for item in value):
            ids = [item.get("id") for item in value]
            if all(isinstance(one, str) for one in ids):
                flat[prefix + "_ids"] = "|".join(ids)
            return flat
        flat[prefix] = "|".join("" if item is None else str(item) for item in value)
        return flat
    if isinstance(value, bool):
        flat[prefix] = "true" if value else "false"
        return flat
    flat[prefix] = "" if value is None else value
    return flat


def columns_of(rows):
    """The union of the keys of every row, id and name first, then sorted."""
    seen = set()
    for row in rows:
        seen.update(row)
    lead = [name for name in ("id", "name", "email") if name in seen]
    rest = sorted(name for name in seen if name not in lead)
    return lead + rest


def to_csv(rows):
    """Render rows as CSV text with a header line, newline terminated."""
    cols = columns_of(rows)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=cols, lineterminator="\n", restval="")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buf.getvalue()


def to_json(items):
    """Render already redacted items as indented JSON text."""
    return json.dumps(items, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def auth_header(token, bearer=False):
    """The Authorization header value.

    Read from the upstream REST client: a personal access token created in the
    management dashboard is sent as Token, an OAuth access token as Bearer.
    """
    return ("Bearer " if bearer else "Token ") + token


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuses every redirect instead of following it.

    The default opener would follow up to ten redirects and, doing so, would
    copy the Authorization header onto the target, which can be another host.
    An administration token is not something to hand to whatever a server
    points at, so a redirect is an error here and says so.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ExportError(
            "%s answered HTTP %s, a redirect to %s. This tool does not follow "
            "redirects, because following one would send your token to the "
            "target. Point --url at the final address instead."
            % (req.selector, code, newurl)
        )


_OPENER = urllib.request.build_opener(_NoRedirect)


def http_fetch(url, path, header, timeout=30):
    """GET one API path and decode its JSON body.

    This is the only function in the package that touches the network. It sends
    exactly one GET per call, never follows a redirect, and sends the token only
    in the Authorization header of that one request.
    """
    request = urllib.request.Request(
        url.rstrip("/") + path,
        headers={"Authorization": header, "Accept": "application/json"},
        method="GET",
    )
    try:
        with _OPENER.open(request, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as err:
        raise ExportError(
            "%s returned HTTP %s. A 401 or 403 usually means the token is wrong "
            "or lacks the admin role." % (path, err.code)
        )
    except urllib.error.URLError as err:
        raise ExportError("%s could not be reached: %s" % (path, err.reason))
    try:
        body = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise ExportError("%s did not return JSON." % path)
    if not isinstance(body, list):
        raise ExportError("%s did not return a list of objects." % path)
    return body


def export(resources, url, header, fetch=http_fetch):
    """Fetch and redact each resource.

    Returns a mapping of resource name to a pair of the redacted items and the
    sorted dotted paths of the fields that were dropped from them.
    """
    result = {}
    for name in resources:
        items = fetch(url, RESOURCES[name], header)
        dropped = set()
        clean = [redact(item, (), dropped) for item in items]
        result[name] = (clean, sorted(dropped))
    return result
