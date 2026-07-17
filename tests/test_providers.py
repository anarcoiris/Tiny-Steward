"""Provider profile registry and dialect locking."""

from __future__ import annotations

import unittest

from core.providers import list_providers, resolve_provider
from core.providers.qwen_json import QwenJsonProfile
from core.providers.qwythos import QwythosProfile


QWEN_XML_LOOKALIKE = """\
<tool_call>
{"name": "ls", "arguments": {"path": "skills/"}}
</tool_call>
"""

QWYTHOS_CALL = """\
<tool_call>
<function=ls>
<parameter=path>skills/</parameter>
</function>
</tool_call>
"""


class TestProviderRegistry(unittest.TestCase):
    def test_list_canonical_ids(self):
        self.assertEqual(list_providers(), ["qwythos", "qwen3_json"])

    def test_resolve_defaults_and_aliases(self):
        self.assertEqual(resolve_provider(None, default="qwythos").id, "qwythos")
        self.assertEqual(resolve_provider("qwen", default="qwythos").id, "qwen3_json")
        with self.assertRaises(ValueError):
            resolve_provider("nope", default="qwythos")

    def test_qwythos_skips_qwen_json(self):
        profile = QwythosProfile()
        # JSON body is not Qwythos XML — profile must not parse it as ls.
        self.assertEqual(profile.extract_actions(QWEN_XML_LOOKALIKE), [])

    def test_qwen_parses_json_only(self):
        profile = QwenJsonProfile()
        actions = profile.extract_actions(QWEN_XML_LOOKALIKE)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["name"], "ls")
        # Qwythos XML should not satisfy qwen_json dialect
        self.assertEqual(profile.extract_actions(QWYTHOS_CALL), [])

    def test_qwythos_parses_xml(self):
        profile = QwythosProfile()
        actions = profile.extract_actions(QWYTHOS_CALL)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["name"], "ls")
        self.assertEqual(actions[0]["body"], "skills/")


if __name__ == "__main__":
    unittest.main()
