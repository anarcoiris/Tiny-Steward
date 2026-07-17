"""Unit tests for F5 vision: image parts, normalize, refuse, atomic strip."""

from __future__ import annotations

import base64
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.help import HelpEngine
from core.llm import LLMClient, estimate_content_tokens
from core.runtime import Runtime, normalize_messages_for_llm
from core.session import Session
from core.skill_loader import Skill, SkillIndex
from core.vision import (
    IMAGE_MAX_BYTES,
    build_user_image_content,
    encode_image_data_uri,
    is_image_path,
    materialize_image_refs,
    probe_multimodal,
    resolve_vision_enabled,
    strip_images_for_text_lane,
    vision_disabled_message,
)


def _tiny_png(path: Path) -> Path:
    # 1x1 PNG
    raw = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )
    path.write_bytes(raw)
    return path


class TestVisionHelpers(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_is_image_path(self):
        self.assertTrue(is_image_path("a.PNG"))
        self.assertTrue(is_image_path("x.webp"))
        self.assertFalse(is_image_path("note.md"))

    def test_build_image_ref_parts(self):
        png = _tiny_png(self.temp / "shot.png")
        parts = build_user_image_content("Describe this.", [png], as_refs=True)
        self.assertEqual(parts[0]["type"], "text")
        self.assertEqual(parts[1]["type"], "image_ref")
        self.assertEqual(parts[1]["mime"], "image/png")
        self.assertIn("shot.png", parts[1]["path"])

    def test_encode_data_uri(self):
        png = _tiny_png(self.temp / "t.png")
        uri, err = encode_image_data_uri(png)
        self.assertIsNone(err)
        self.assertTrue(uri.startswith("data:image/png;base64,"))

    def test_encode_rejects_oversized(self):
        big = self.temp / "big.png"
        big.write_bytes(b"x" * (IMAGE_MAX_BYTES + 1))
        uri, err = encode_image_data_uri(big)
        self.assertEqual(uri, "")
        self.assertIn("too large", err or "")

    def test_materialize_converts_ref(self):
        png = _tiny_png(self.temp / "m.png")
        messages = [
            {
                "role": "user",
                "content": build_user_image_content("hi", [png], as_refs=True),
            }
        ]
        out, errs = materialize_image_refs(messages)
        self.assertEqual(errs, [])
        content = out[0]["content"]
        self.assertIsInstance(content, list)
        img = next(p for p in content if p["type"] == "image_url")
        self.assertTrue(img["image_url"]["url"].startswith("data:image/png;base64,"))

    def test_strip_images_for_atomic(self):
        png = _tiny_png(self.temp / "a.png")
        messages = [
            {
                "role": "user",
                "content": build_user_image_content("see", [png], as_refs=True),
            }
        ]
        out = strip_images_for_text_lane(messages)
        self.assertIsInstance(out[0]["content"], str)
        self.assertIn("omitted", out[0]["content"])
        self.assertIn("a.png", out[0]["content"])

    def test_resolve_vision_modes(self):
        enabled, reason = resolve_vision_enabled("off", base_url="http://x", probe=True)
        self.assertFalse(enabled)
        enabled, reason = resolve_vision_enabled("auto", base_url="http://x", probe=True)
        self.assertTrue(enabled)
        enabled, reason = resolve_vision_enabled("on", base_url="http://x", probe=False)
        self.assertFalse(enabled)
        self.assertIn("probe", reason)

    def test_probe_multimodal_capabilities(self):
        payload = {
            "models": [{"name": "m", "capabilities": ["completion", "multimodal"]}],
            "data": [{"id": "m"}],
        }
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = payload
        with patch("core.vision.httpx.Client") as Client:
            Client.return_value.__enter__.return_value.get.return_value = mock_resp
            self.assertTrue(probe_multimodal("http://127.0.0.1:11440"))


class TestNormalizePreservesImages(unittest.TestCase):
    def test_preserves_image_parts(self):
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "look"},
                    {"type": "image_ref", "path": "x.png", "mime": "image/png"},
                ],
            }
        ]
        out = normalize_messages_for_llm(messages)
        self.assertEqual(out[0]["content"][1]["type"], "image_ref")
        self.assertEqual(out[0]["content"][1]["path"], "x.png")

    def test_estimate_content_tokens_list(self):
        n = estimate_content_tokens(
            [
                {"type": "text", "text": "abcd"},
                {"type": "image_ref", "path": "a.png", "mime": "image/png"},
            ]
        )
        self.assertGreaterEqual(n, 512)


class TestAttachImage(unittest.TestCase):
    def setUp(self):
        skill = Skill(name="t", slug="t", path="t.md", skill_type="skill")
        self.temp = Path(tempfile.mkdtemp())
        self.rt = Runtime(
            llm=LLMClient(base_url="http://mock", model="m"),
            help_engine=HelpEngine(SkillIndex([skill], vectors=None), None),
            session=Session("vision-test"),
            use_streaming=False,
            rules_enabled=False,
            vision_enabled=True,
        )

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_text_path_unchanged(self):
        f = self.temp / "note.md"
        f.write_text("hello attach", encoding="utf-8")
        out, notes, refs = self.rt._expand_at_attachments(f'Review @"{f}" please')
        self.assertIn("hello attach", out)
        self.assertEqual(refs, [])
        self.assertTrue(any("Expanded" in n for n in notes))

    def test_image_at_path_collects_ref(self):
        png = _tiny_png(self.temp / "pic.png")
        out, notes, refs = self.rt._expand_at_attachments(f'What is @"{png}"?')
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0]["type"], "image_ref")
        self.assertIn("Image attached", out)

    def test_attach_image_meta(self):
        png = _tiny_png(self.temp / "shot.png")
        messages: list = []
        ok = self.rt._handle_meta_command(f"/image {png}", messages)
        self.assertTrue(ok)
        self.assertEqual(len(messages), 1)
        content = messages[0]["content"]
        self.assertIsInstance(content, list)
        self.assertEqual(content[1]["type"], "image_ref")
        # Session stores path ref, not base64
        stored = self.rt.session.messages[-1]["content"]
        self.assertIsInstance(stored, list)
        self.assertEqual(stored[1]["type"], "image_ref")
        blob = str(stored)
        self.assertNotIn("base64,", blob)

    def test_refuse_when_vision_off(self):
        self.rt.vision_enabled = False
        png = _tiny_png(self.temp / "nope.png")
        messages: list = []
        self.rt._handle_meta_command(f"/attach {png}", messages)
        self.assertEqual(messages, [])
        self.assertIn("-WithVision", vision_disabled_message())

    def test_llm_body_passthrough_list_content(self):
        client = LLMClient(base_url="http://mock", model="m")
        parts = [
            {"type": "text", "text": "hi"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,xx"}},
        ]
        body = client._build_body(
            [{"role": "user", "content": parts}],
            stream=False,
            max_tokens=1,
            temperature=0.1,
        )
        self.assertIsInstance(body["messages"][0]["content"], list)
        self.assertEqual(body["messages"][0]["content"][1]["type"], "image_url")

    def test_call_llm_strips_images_on_atomic(self):
        png = _tiny_png(self.temp / "atom.png")
        atomic = LLMClient(base_url="http://mock-atomic", model="a", gate_lane="atomic")
        self.rt.atomic_llm = atomic
        messages = [
            {"role": "system", "content": "sys"},
            {
                "role": "user",
                "content": build_user_image_content("see", [png], as_refs=True),
            },
        ]
        with patch.object(atomic, "chat", return_value="ok") as chat:
            self.rt.use_streaming = False
            resp, _, _ = self.rt._call_llm(messages, turn=1, backend="secondary")
            self.assertEqual(resp, "ok")
            sent = chat.call_args[0][0]
            # Atomic must not receive image_url / image_ref
            for msg in sent:
                c = msg.get("content")
                if isinstance(c, list):
                    self.assertFalse(any(
                        isinstance(p, dict) and p.get("type") in ("image_ref", "image_url")
                        for p in c
                    ))
                else:
                    self.assertIsInstance(c, str)


if __name__ == "__main__":
    unittest.main()
