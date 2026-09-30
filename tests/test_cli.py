import csv
import io
import json
import os
import shutil
import tempfile
import unittest

from fixtures import fake_fetch
from netbirdexport.cli import TOKEN_ENV, run
from netbirdexport.core import ExportError

# The exact text the tool prints, also recopied by hand into the README. The
# test below compares this constant to the tool's real output, so the tool
# cannot change its output without turning this suite red. It does not read
# README.md, so keeping the README in step with this constant stays a manual
# step; what the suite guarantees is that this constant is not stale.
README_SAMPLE = """netbirdexport 0.1.0
source  https://api.netbird.io
output  netbird-export

resource    rows  files
peers          2  peers.csv, peers.json
users          2  users.csv, users.json
setup-keys     1  setup-keys.csv, setup-keys.json
groups         2  groups.csv, groups.json

never written, matched by field name: setup-keys.key
wrote 9 files including manifest.json
"""


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.out = os.path.join(self.tmp, "netbird-export")
        self.env = {TOKEN_ENV: "pat-example"}

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def invoke(self, *extra):
        stdout = io.StringIO()
        code = run(
            ["--out", self.out] + list(extra),
            fetch=fake_fetch,
            env=self.env,
            stdout=stdout,
        )
        return code, stdout.getvalue()

    def read(self, name):
        with open(os.path.join(self.out, name), encoding="utf-8") as handle:
            return handle.read()

    def test_the_whole_rendering_is_the_one_shown_in_the_readme(self):
        stdout = io.StringIO()
        code = run([], fetch=fake_fetch, env=self.env, stdout=stdout)
        try:
            self.assertEqual(0, code)
            self.assertEqual(README_SAMPLE, stdout.getvalue())
        finally:
            shutil.rmtree("netbird-export", ignore_errors=True)

    def test_it_writes_one_csv_and_one_json_per_resource_plus_a_manifest(self):
        code, _ = self.invoke()
        self.assertEqual(0, code)
        self.assertEqual(
            sorted(
                [
                    "groups.csv",
                    "groups.json",
                    "manifest.json",
                    "peers.csv",
                    "peers.json",
                    "setup-keys.csv",
                    "setup-keys.json",
                    "users.csv",
                    "users.json",
                ]
            ),
            sorted(os.listdir(self.out)),
        )

    def test_the_setup_key_value_is_in_no_written_byte_anywhere(self):
        self.invoke()
        for name in os.listdir(self.out):
            self.assertNotIn("A616097E", self.read(name), name)

    def test_the_manifest_names_the_fields_it_dropped(self):
        self.invoke()
        manifest = json.loads(self.read("manifest.json"))
        self.assertEqual(["key"], manifest["resources"]["setup-keys"]["redacted_fields"])
        self.assertEqual([], manifest["resources"]["peers"]["redacted_fields"])

    def test_the_manifest_records_the_source_and_the_row_counts(self):
        self.invoke("--url", "https://nb.example.org")
        manifest = json.loads(self.read("manifest.json"))
        self.assertEqual("https://nb.example.org", manifest["source"])
        self.assertEqual(2, manifest["resources"]["peers"]["rows"])
        self.assertEqual("/api/peers", manifest["resources"]["peers"]["path"])

    def test_the_csv_has_a_header_and_one_line_per_object(self):
        self.invoke()
        rows = list(csv.DictReader(io.StringIO(self.read("peers.csv"))))
        self.assertEqual(2, len(rows))
        self.assertEqual("laptop-01", rows[0]["name"])
        self.assertEqual("100.72.0.2", rows[1]["ip"])

    def test_the_json_keeps_the_nested_shape_the_api_returned(self):
        self.invoke()
        peers = json.loads(self.read("peers.json"))
        self.assertEqual("All", peers[0]["groups"][0]["name"])

    def test_only_the_requested_resources_are_fetched_and_in_that_order(self):
        code, text = self.invoke("--resources", "users,peers")
        self.assertEqual(0, code)
        self.assertEqual(["manifest.json", "peers.csv", "peers.json", "users.csv", "users.json"], sorted(os.listdir(self.out)))
        self.assertLess(text.index("users "), text.index("peers "))

    def test_asking_for_csv_only_writes_no_json_except_the_manifest(self):
        self.invoke("--format", "csv")
        self.assertEqual(
            ["groups.csv", "manifest.json", "peers.csv", "setup-keys.csv", "users.csv"],
            sorted(os.listdir(self.out)),
        )

    def test_a_repeated_resource_is_exported_once(self):
        _, text = self.invoke("--resources", "peers,peers")
        self.assertEqual(1, text.count("peers.csv"))

    def test_a_missing_token_is_an_error_that_names_the_variable(self):
        self.env = {}
        with self.assertRaises(ExportError) as caught:
            self.invoke()
        self.assertIn(TOKEN_ENV, str(caught.exception))

    def test_a_blank_token_counts_as_missing(self):
        self.env = {TOKEN_ENV: "   "}
        with self.assertRaises(ExportError):
            self.invoke()

    def test_an_unknown_resource_is_refused_and_the_list_is_shown(self):
        with self.assertRaises(ExportError) as caught:
            self.invoke("--resources", "peers,widgets")
        self.assertIn("widgets", str(caught.exception))
        self.assertIn("setup-keys", str(caught.exception))

    def test_an_unknown_format_is_refused(self):
        with self.assertRaises(ExportError):
            self.invoke("--format", "xlsx")

    def test_nothing_is_written_before_every_fetch_has_succeeded(self):
        def failing(url, path, header, timeout=30):
            if path == "/api/groups":
                raise ExportError("boom")
            return fake_fetch(url, path, header)

        stdout = io.StringIO()
        with self.assertRaises(ExportError):
            run(["--out", self.out], fetch=failing, env=self.env, stdout=stdout)
        self.assertFalse(os.path.exists(self.out))


if __name__ == "__main__":
    unittest.main()
