import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from aurix_agent.core import AURIXAgent


class AgentLoopTests(unittest.TestCase):
    def test_agent_executes_tool_then_returns_final_answer(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "note.txt").write_text("Proof: tool output is real.", encoding="utf-8")
            config = {
                "active_provider": "mock",
                "providers": [{"name": "mock", "endpoint": "https://mock.example/v1/chat/completions", "model": "mock", "api_key": "", "enabled": True}],
                "max_tool_rounds": 3,
                "request_timeout_seconds": 10,
            }
            tool_response = {"tool_calls": [{
                "id": "call-1",
                "type": "function",
                "function": {"name": "read_file", "arguments": json.dumps({"path": "note.txt"})},
            }]}
            final_response = {"content": "I read the note and verified the content."}
            events = []
            with patch("aurix_agent.core.OpenAICompatibleClient.chat", side_effect=[(tool_response, "mock"), (final_response, "mock")]) as chat:
                agent = AURIXAgent(config, temp, event=lambda kind, message: events.append((kind, message)), cancel=threading.Event())
                result = agent.run("Read note.txt")
            self.assertIn("verified", result)
            self.assertEqual(chat.call_count, 2)
            second_messages = chat.call_args_list[1].args[0]
            tool_messages = [m for m in second_messages if m.get("role") == "tool"]
            self.assertEqual(len(tool_messages), 1)
            self.assertIn("Proof: tool output is real.", tool_messages[0]["content"])
            self.assertTrue(any(kind == "complete" for kind, _ in events))


if __name__ == "__main__":
    unittest.main()
