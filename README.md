# netbirdexport

```
pip install netbirdexport
```

Export your NetBird account inventory to CSV and JSON in one command, using your own access token. Peers, users, setup keys and groups, one CSV and one JSON file each, plus a manifest. Standard library only, no dependencies.

Not affiliated with NetBird. "NetBird" is used here only to say which API this tool reads.

## Why this exists

In [netbirdio/netbird#4437](https://github.com/netbirdio/netbird/issues/4437), open since September 2025, `chirag-rastogi` wrote:

> Currently, there's no way to download or back up information like the list of users, peers, or setup keys.

The management API already exposes every one of those objects: `/api/users`, `/api/peers` and `/api/setup-keys` all exist and are read by the project's own REST client. The missing part was the one command that reads them and writes them out for an audit or a migration. That is all this tool is.

## Use

Create a personal access token in the management dashboard, then:

```
export NETBIRD_TOKEN=nbp_xxxxxxxxxxxxxxxx
netbirdexport
```

```
netbirdexport 0.1.0
source  https://api.netbird.io
output  netbird-export

resource    rows  files
peers          2  peers.csv, peers.json
users          2  users.csv, users.json
setup-keys     1  setup-keys.csv, setup-keys.json
groups         2  groups.csv, groups.json

never written, matched by field name: setup-keys.key
wrote 9 files including manifest.json
```

The token is read from `NETBIRD_TOKEN` and is never accepted as a command line argument, so it does not appear in the argument list of the running process. It is still in that process's environment, and typing `export NETBIRD_TOKEN=...` at a prompt does put it in your shell history, so read it from a secret store or from a file you control if that matters to you.

Self hosted, and more resources:

```
netbirdexport --url https://netbird.example.org --resources peers,users,setup-keys,groups,policies,routes,nameservers --out audit-2026-09
```

Options:

- `--url` management API base URL, default `https://api.netbird.io`.
- `--out` directory to write into, created if missing, default `netbird-export`.
- `--resources` comma separated, in output order. Available: `peers`, `users`, `setup-keys`, `groups`, `policies`, `routes`, `nameservers`.
- `--format` comma separated, `csv` and `json`, default both.
- `--bearer` send the token as `Bearer` instead of `Token`, for an OAuth access token rather than a personal access token.
- `--version` print the version and exit.

Nothing is written until every request has succeeded, so a failure halfway through leaves no half exported directory behind.

## What the two formats are for

`<resource>.json` keeps the nested shape the API returned, which is what you want for a diff between two dates. `<resource>.csv` flattens the same objects to one row each: a nested object becomes a `parent.child` column, and every list gets a `<field>_count` column, whatever it holds and even when it is empty, so that a column never appears or disappears just because a list happened to be empty on one run. A list of values also gets `<field>` with the values joined by a vertical bar; a list of objects also gets `<field>_ids` when every object in the list carries a string `id`. Columns are the union of the keys seen across all rows, so a field that only some objects carry still gets a column.

Columns are not a fixed list. This tool writes whatever the API returns, minus the redacted fields below, which means it does not silently drop a field that a newer server version added.

`manifest.json` records the tool version, the source URL, the UTC time of the run, and for each resource its API path, its row count and the names of the fields that were dropped.

## Secrets: what is dropped, and what that does not promise

A field is never written when its own name, lowercased, is one of `key`, `token`, `secret`, `password`, `passphrase`, `private_key`, `privatekey`, `client_secret`, `api_key`, `access_token`, `refresh_token`, or ends with `_secret`, `_password`, `_token` or `_private_key`. This applies at every depth, inside nested objects and inside lists. Every dropped field is named on the console and in `manifest.json`, so nothing is removed silently.

Read this next part before you share an export. **This is a match on field names, not a classification of content.** It drops the setup key field, which is named `key`, and it deliberately keeps fields like `setup_key_id` or `public_key`, which identify rather than authenticate. It cannot know that some future field with an innocent name holds something sensitive. An export of an administration inventory contains user emails, host names and internal addresses in any case: treat the output directory as sensitive, and read it before sending it anywhere.

## Honest limits

**This tool has never been run against a real NetBird instance.** It has no test deployment and no token behind it. Its test suite runs against example API responses written for those tests, and the shape of those responses follows the upstream project's public REST client and API specification, read on 2026-09-30. If you run it against a real account and something is wrong, open an issue and it will be fixed.

It issues one GET per resource and sends nothing else of its own. It does not follow redirects: a redirect is reported as an error rather than followed, because following one would resend your `Authorization` header to whatever host the server pointed at. It never asks the API to change anything, because every request it makes is a GET.

It does not paginate: it reads each list endpoint once and writes what came back. The project's own REST client takes no page parameter on these list calls, but if some server version paginates one of them, this tool would write only the first page, and that has not been tested against a real instance.

It reads only a whole account: there is no filter by group, by name or by date. An export is the inventory as it stands at the moment of the run.

An export is not a restore file. Nothing here writes back, the default set covers four resources out of seven, and a setup key cannot be recreated from an export because its value is deliberately absent. Treat the output as an audit and migration record, not as a backup you could restore from.

`policies`, `routes` and `nameservers` are available but not exported by default. The default set is peers, users and setup keys, the three the request above named, plus groups, because a peer row carries group ids and those ids mean nothing without the group names.

Python 3.9 or newer.

## Upstream licence

NetBird is published by NetBird GmbH and its authors. Its repository is BSD 3-Clause except the `management/`, `signal/`, `relay/` and `combined/` directories, which are GNU AGPL version 3. This package is MIT and is not derived from it: no upstream line is copied here. What was read is the public shape of its HTTP interface, and this tool is an outside client that speaks to that interface over the network.

## Licence

MIT, Younes Z. See `LICENSE`.

Built with AI assistance, reviewed and tested by me.
