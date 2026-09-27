import unittest

from build_mq_column_payloads import build_payloads


class MqColumnPayloadTests(unittest.TestCase):
    def test_has_exactly_the_seven_optional_mq_columns(self):
        payloads = build_payloads()
        expected = {
            "mqterminalstatus": "cr6cb_Mqterminalstatus",
            "mqexpectedcount": "cr6cb_Mqexpectedcount",
            "mqloggedcount": "cr6cb_Mqloggedcount",
            "mqmissingcount": "cr6cb_Mqmissingcount",
            "mqmissingids": "cr6cb_Mqmissingids",
            "mqcomparisonstatus": "cr6cb_Mqcomparisonstatus",
            "mqresulttext": "cr6cb_Mqresulttext",
        }
        self.assertEqual(set(payloads), set(expected))
        for logical_name, schema_name in expected.items():
            with self.subTest(logical_name=logical_name):
                self.assertEqual(payloads[logical_name]["SchemaName"], schema_name)
                self.assertEqual(payloads[logical_name]["RequiredLevel"]["Value"], "None")

    def test_integers_allow_zero_and_text_fields_have_explicit_lengths(self):
        payloads = build_payloads()
        for logical_name in ("mqexpectedcount", "mqloggedcount", "mqmissingcount"):
            with self.subTest(logical_name=logical_name):
                self.assertEqual(payloads[logical_name]["AttributeType"], "Integer")
                self.assertEqual(payloads[logical_name]["MinValue"], 0)
                self.assertEqual(payloads[logical_name]["MaxValue"], 2147483647)
        for logical_name in ("mqterminalstatus", "mqcomparisonstatus", "mqmissingids", "mqresulttext"):
            with self.subTest(logical_name=logical_name):
                self.assertGreater(payloads[logical_name]["MaxLength"], 0)


if __name__ == "__main__":
    unittest.main()
