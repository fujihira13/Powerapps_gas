import json
import unittest
from pathlib import Path

from build_osts_wrappers import (
    OUTPUT_DIR,
    SCRIPT_NAMES,
    WRAPPER_VERSION,
    build_wrappers,
)


EXPECTED_PARAMETERS = {
    "read_validate_batch_input": ("logText",),
    "write_mq_comparison": ("validationJson", "caseId"),
    "readback_mq_comparison": ("validationJson", "caseId"),
}


class OstWrapperTests(unittest.TestCase):
    def test_wrappers_keep_source_body_verbatim_and_are_explicitly_unverified(self):
        wrappers = build_wrappers()
        self.assertEqual(set(wrappers), {f"{name}.osts" for name in SCRIPT_NAMES})
        self.assertEqual(WRAPPER_VERSION, "0.2.0")
        for filename, document in wrappers.items():
            with self.subTest(filename=filename):
                self.assertEqual(
                    set(document),
                    {"version", "body", "description", "parameterInfo", "apiInfo"},
                )
                self.assertEqual(document["version"], WRAPPER_VERSION)
                self.assertEqual(document["description"], "")
                source = Path(__file__).parent / "office-scripts" / filename.replace(".osts", ".ts")
                self.assertEqual(document["body"], source.read_text(encoding="utf-8"))

    def test_parameter_and_return_metadata_match_each_main_signature(self):
        wrappers = build_wrappers()
        for script_name, script_parameters in EXPECTED_PARAMETERS.items():
            filename = f"{script_name}.osts"
            with self.subTest(filename=filename):
                document = wrappers[filename]
                parameter_info = json.loads(document["parameterInfo"])
                self.assertEqual(
                    parameter_info["originalParameterOrder"],
                    [
                        {"name": name, "index": index}
                        for index, name in enumerate(script_parameters)
                    ],
                )
                self.assertEqual(
                    parameter_info["parameterSchema"],
                    {
                        "type": "object",
                        "required": list(script_parameters),
                        "properties": {
                            name: {"type": "string"} for name in script_parameters
                        },
                    },
                )
                self.assertEqual(
                    parameter_info["returnSchema"],
                    {"type": "object", "properties": {"result": {"type": "string"}}},
                )
                self.assertEqual(
                    json.loads(document["apiInfo"]),
                    {"variant": "synchronous", "variantVersion": 2},
                )

    def test_generated_files_are_valid_json_and_match_source(self):
        for filename, expected in build_wrappers().items():
            with self.subTest(filename=filename):
                target = OUTPUT_DIR / filename
                expected_bytes = (
                    json.dumps(expected, ensure_ascii=False, indent=2) + "\n"
                ).encode("utf-8")
                self.assertEqual(target.read_bytes(), expected_bytes)
                payload = json.loads(target.read_text(encoding="utf-8"))
                self.assertEqual(payload, expected)
                self.assertIsInstance(json.loads(payload["parameterInfo"]), dict)
                self.assertIsInstance(json.loads(payload["apiInfo"]), dict)


if __name__ == "__main__":
    unittest.main()
