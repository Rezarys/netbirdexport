import unittest
import urllib.request

from fixtures import GROUPS, PEERS, SETUP_KEYS, USERS
from netbirdexport.core import (
    ExportError,
    _NoRedirect,
    auth_header,
    columns_of,
    flatten,
    is_redacted,
    redact,
    to_csv,
)


class RedactionTest(unittest.TestCase):
    def test_a_field_named_key_is_redacted_and_reported(self):
        dropped = set()
        clean = redact(SETUP_KEYS[0], (), dropped)
        self.assertNotIn("key", clean)
        self.assertEqual({"key"}, dropped)

    def test_every_other_setup_key_field_survives(self):
        clean = redact(SETUP_KEYS[0], (), set())
        expected = set(SETUP_KEYS[0]) - {"key"}
        self.assertEqual(expected, set(clean))

    def test_the_name_match_is_case_insensitive_and_covers_suffixes(self):
        for name in ("Key", "TOKEN", "client_secret", "db_password", "x_private_key"):
            self.assertTrue(is_redacted(name), name)

    def test_an_identifier_that_merely_mentions_a_key_is_kept(self):
        for name in ("setup_key_id", "public_key", "keys_count", "monkey"):
            self.assertFalse(is_redacted(name), name)

    def test_redaction_reaches_inside_nested_objects_and_lists(self):
        dropped = set()
        clean = redact(
            {"a": {"token": "t", "b": 1}, "c": [{"secret": "s", "d": 2}]}, (), dropped
        )
        self.assertEqual({"a": {"b": 1}, "c": [{"d": 2}]}, clean)
        self.assertEqual({"a.token", "c.secret"}, dropped)

    def test_redaction_does_not_mutate_its_input(self):
        redact(SETUP_KEYS[0], (), set())
        self.assertIn("key", SETUP_KEYS[0])


class FlattenTest(unittest.TestCase):
    def test_a_list_of_objects_becomes_a_count_and_the_joined_ids(self):
        flat = flatten(PEERS[0])
        self.assertEqual(2, flat["groups_count"])
        self.assertEqual("ch8i4ug6lnn4g9hqv7m1|ch8i4ug6lnn4g9hqv7m2", flat["groups_ids"])

    def test_an_empty_list_of_objects_is_a_zero_count_not_a_missing_column(self):
        self.assertEqual({"auto_groups_count": 0}, flatten({"auto_groups": []}))

    def test_a_list_of_scalars_is_joined_with_a_bar_and_still_counted(self):
        self.assertEqual({"g": "a|b", "g_count": 2}, flatten({"g": ["a", "b"]}))

    def test_every_list_gets_a_count_whether_it_holds_values_or_objects(self):
        # Otherwise a column would appear or disappear between two runs only
        # because a list happened to be empty, which reads as a server change.
        for value in ([], ["a"], [{"id": "x"}]):
            self.assertIn("g_count", flatten({"g": value}), value)

    def test_booleans_are_written_as_words_not_as_python_repr(self):
        flat = flatten(PEERS[0])
        self.assertEqual("true", flat["connected"])
        self.assertEqual("false", flat["ssh_enabled"])

    def test_a_nested_object_is_dotted(self):
        self.assertEqual({"a.b": 1}, flatten({"a": {"b": 1}}))

    def test_none_becomes_an_empty_cell(self):
        self.assertEqual({"a": ""}, flatten({"a": None}))

    def test_no_flattened_column_of_a_peer_is_a_container(self):
        for key, value in flatten(PEERS[1]).items():
            self.assertNotIsInstance(value, (dict, list), key)


class ColumnsTest(unittest.TestCase):
    def test_identifying_columns_come_first_then_the_rest_sorted(self):
        cols = columns_of([{"z": 1, "name": 2, "id": 3, "a": 4}])
        self.assertEqual(["id", "name", "a", "z"], cols)

    def test_columns_are_the_union_over_rows_so_a_sparse_row_is_not_dropped(self):
        self.assertEqual(["id", "a", "b"], columns_of([{"id": 1, "a": 2}, {"b": 3}]))

    def test_a_missing_value_is_written_as_an_empty_cell(self):
        text = to_csv([{"id": "1", "a": "x"}, {"id": "2"}])
        self.assertEqual("id,a\n1,x\n2,\n", text)


class CsvTest(unittest.TestCase):
    def test_the_header_is_present_even_with_no_rows(self):
        self.assertEqual("\n", to_csv([]))

    def test_a_group_renders_its_member_ids_in_one_cell(self):
        rows = [flatten(redact(item, (), set())) for item in GROUPS]
        text = to_csv(rows)
        self.assertIn("ch8i4ug6lnn4g9hqv7m0|ch8i4ug6lnn4g9hqv7m5", text)

    def test_a_user_email_is_exported_because_it_identifies_not_authenticates(self):
        rows = [flatten(redact(item, (), set())) for item in USERS]
        self.assertIn("ada@example.org", to_csv(rows))


class RedirectTest(unittest.TestCase):
    def test_a_redirect_is_refused_rather_than_followed(self):
        # Following one would resend the Authorization header to the target,
        # which the standard library opener does by default and this one must not.
        request = urllib.request.Request("https://nb.example.org/api/peers")
        with self.assertRaises(ExportError) as caught:
            _NoRedirect().redirect_request(
                request, None, 302, "Found", {}, "https://elsewhere.example/api/peers"
            )
        self.assertIn("elsewhere.example", str(caught.exception))

    def test_the_opener_used_for_fetching_carries_no_redirect_handler(self):
        from netbirdexport.core import _OPENER

        followers = [
            handler
            for handler in _OPENER.handlers
            if type(handler) is urllib.request.HTTPRedirectHandler
        ]
        self.assertEqual([], followers)


class AuthHeaderTest(unittest.TestCase):
    def test_a_personal_access_token_is_sent_as_token(self):
        self.assertEqual("Token abc", auth_header("abc"))

    def test_an_oauth_access_token_is_sent_as_bearer(self):
        self.assertEqual("Bearer abc", auth_header("abc", bearer=True))


if __name__ == "__main__":
    unittest.main()
