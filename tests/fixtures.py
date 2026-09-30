"""Example API responses written for these tests.

These are not recordings of a real deployment. This tool has never been run
against a real instance; the shape here follows the public REST client and API
specification of the upstream project, and its only job is to exercise the
redaction, flattening and rendering code.
"""

PEERS = [
    {
        "id": "ch8i4ug6lnn4g9hqv7m0",
        "name": "laptop-01",
        "ip": "100.72.0.1",
        "dns_label": "laptop-01.netbird.cloud",
        "connected": True,
        "last_seen": "2026-09-30T09:12:44Z",
        "os": "Darwin 25.5.0",
        "version": "0.58.2",
        "hostname": "laptop-01",
        "ssh_enabled": False,
        "groups": [
            {"id": "ch8i4ug6lnn4g9hqv7m1", "name": "All", "peers_count": 2},
            {"id": "ch8i4ug6lnn4g9hqv7m2", "name": "office", "peers_count": 1},
        ],
    },
    {
        "id": "ch8i4ug6lnn4g9hqv7m5",
        "name": "build-runner",
        "ip": "100.72.0.2",
        "dns_label": "build-runner.netbird.cloud",
        "connected": False,
        "last_seen": "2026-09-28T22:05:01Z",
        "os": "Linux 6.8.0",
        "version": "0.58.1",
        "hostname": "build-runner",
        "ssh_enabled": True,
        "groups": [{"id": "ch8i4ug6lnn4g9hqv7m1", "name": "All", "peers_count": 2}],
    },
]

USERS = [
    {
        "id": "google-oauth2|1",
        "email": "ada@example.org",
        "name": "Ada",
        "role": "owner",
        "status": "active",
        "is_service_user": False,
        "auto_groups": [],
    },
    {
        "id": "api-token-user",
        "email": "",
        "name": "ci-service",
        "role": "admin",
        "status": "active",
        "is_service_user": True,
        "auto_groups": ["ch8i4ug6lnn4g9hqv7m2"],
    },
]

SETUP_KEYS = [
    {
        "id": "ch8i4ug6lnn4g9hqv7n0",
        "name": "office laptops",
        "key": "A616097E-FCF0-48FA-9354-CA4A61142761",
        "expires": "2026-12-31T00:00:00Z",
        "type": "reusable",
        "valid": True,
        "revoked": False,
        "used_times": 3,
        "last_used": "2026-09-29T14:00:00Z",
        "state": "valid",
        "ephemeral": False,
        "auto_groups": ["ch8i4ug6lnn4g9hqv7m2"],
    }
]

GROUPS = [
    {
        "id": "ch8i4ug6lnn4g9hqv7m1",
        "name": "All",
        "issued": "api",
        "peers": [
            {"id": "ch8i4ug6lnn4g9hqv7m0", "name": "laptop-01"},
            {"id": "ch8i4ug6lnn4g9hqv7m5", "name": "build-runner"},
        ],
    },
    {
        "id": "ch8i4ug6lnn4g9hqv7m2",
        "name": "office",
        "issued": "api",
        "peers": [{"id": "ch8i4ug6lnn4g9hqv7m0", "name": "laptop-01"}],
    },
]

BY_PATH = {
    "/api/peers": PEERS,
    "/api/users": USERS,
    "/api/setup-keys": SETUP_KEYS,
    "/api/groups": GROUPS,
}


def fake_fetch(url, path, header, timeout=30):
    """Stands in for core.http_fetch, and checks the caller's contract."""
    if not header.startswith(("Token ", "Bearer ")):
        raise AssertionError("unexpected Authorization header: %r" % header)
    return BY_PATH[path]
