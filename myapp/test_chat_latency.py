from types import SimpleNamespace
from unittest.mock import Mock, patch

import httpx
from django.test import SimpleTestCase
from openai import APITimeoutError

from myapp import ai_chat


class ChatLatencyTests(SimpleTestCase):
    @patch('myapp.ai_chat._get_client')
    def test_gpt_timeout_uses_one_fast_fallback(self, get_client):
        stalled, fallback = Mock(), Mock()
        stalled.chat.completions.create.side_effect = APITimeoutError(
            request=httpx.Request('POST', 'https://example.test/chat'))
        fallback.chat.completions.create.return_value = iter([
            SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content='4'))])
        ])
        get_client.side_effect = [stalled, fallback]
        answer = ''.join(ai_chat.stream_chat(
            [{'role': 'user', 'content': 'What is 2+2?'}], model_key='gpt-oss-20b'))
        self.assertEqual(answer, '4')
        self.assertEqual(stalled.chat.completions.create.call_args.kwargs['timeout'], 15)
        self.assertEqual(fallback.chat.completions.create.call_args.kwargs['timeout'], 15)
        self.assertEqual(fallback.chat.completions.create.call_args.kwargs['model'], ai_chat.MODELS['quick']['id'])
        self.assertEqual(stalled.chat.completions.create.call_count, 1)
        self.assertEqual(fallback.chat.completions.create.call_count, 1)
