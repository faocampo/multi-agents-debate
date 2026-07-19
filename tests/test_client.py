import unittest

from multi_agent_experts import ChatClientError, HTTPChatClient


class HTTPChatClientTests(unittest.TestCase):
    def test_extracts_ollama_response(self):
        result = HTTPChatClient._extract_content(
            {"message": {"role": "assistant", "content": "ollama result"}}
        )
        self.assertEqual(result, "ollama result")

    def test_extracts_openai_response(self):
        result = HTTPChatClient._extract_content(
            {"choices": [{"message": {"role": "assistant", "content": "openai result"}}]}
        )
        self.assertEqual(result, "openai result")

    def test_extracts_segmented_content(self):
        result = HTTPChatClient._extract_content(
            {"choices": [{"message": {"content": [{"text": "one"}, {"text": " two"}]}}]}
        )
        self.assertEqual(result, "one two")

    def test_rejects_missing_content(self):
        with self.assertRaises(ChatClientError):
            HTTPChatClient._extract_content({"choices": []})

    def test_rejects_non_object_response(self):
        with self.assertRaises(ChatClientError):
            HTTPChatClient._extract_content([])


if __name__ == "__main__":
    unittest.main()
