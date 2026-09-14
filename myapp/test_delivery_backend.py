"""Dependency-free checks: python myapp/test_delivery_backend.py."""
import ast
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import random
import threading
import time
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parent.parent


def function_from_source(path, name, namespace):
    tree = ast.parse((ROOT / path).read_text(encoding='utf-8'))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), namespace)
    return namespace[name]


class DeliveryBackendTests(unittest.TestCase):
    def test_python_syntax(self):
        for path in ('myapp/views.py', 'myapp/ai_chat.py', 'edutrellis/settings.py'):
            ast.parse((ROOT / path).read_text(encoding='utf-8'))

    def test_concurrent_requests_share_client_without_changing_options(self):
        created = []

        def client(**options):
            time.sleep(0.005)
            result = SimpleNamespace(options=options)
            created.append(result)
            return result

        namespace = {'_clients': {}, '_clients_lock': threading.Lock(), 'OpenAI': client}
        get_client = function_from_source('myapp/ai_chat.py', '_client_for_key', namespace)
        with ThreadPoolExecutor(max_workers=12) as pool:
            clients = list(pool.map(lambda _: get_client('test-key'), range(24)))
        self.assertEqual(len(created), 1)
        self.assertTrue(all(c is clients[0] for c in clients))
        self.assertEqual(clients[0].options, dict(
            base_url='https://integrate.api.nvidia.com/v1', api_key='test-key',
            timeout=25.0, max_retries=0))
        self.assertIsNot(get_client('different-key'), clients[0])

    def test_gate_result_preserved_and_redundant_count_skipped(self):
        profile = SimpleNamespace(is_ai_subscribed=False, ai_free_messages_used=5)
        counted = []
        namespace = {
            '_ai_has_admin_access': lambda user: False,
            'StoreProfile': SimpleNamespace(objects=SimpleNamespace(get_or_create=lambda **kw: (profile, False))),
            '_ip_free_messages_used': lambda ip: counted.append(ip) or 0,
            'AI_FREE_MESSAGE_LIMIT': 5, 'AI_GUEST_MESSAGE_LIMIT': 3,
            '_ai_purchase_url': lambda: '/subscribe/',
        }
        gate = function_from_source('myapp/views.py', '_ai_profile_gate', namespace)
        self.assertEqual(gate(object(), '127.0.0.1')['status'], 'subscription_required')
        self.assertEqual(counted, [])
        profile.ai_free_messages_used = 0
        self.assertIsNone(gate(object(), '127.0.0.1'))
        self.assertEqual(counted, ['127.0.0.1'])

    def test_history_matches_previous_algorithm(self):
        source = (ROOT / 'myapp/views.py').read_text(encoding='utf-8')
        start = source.index('    history_chars = sum(')
        end = source.index('\n\n', start)
        code = compile(__import__('textwrap').dedent(source[start:end]), '<history>', 'exec')
        rng = random.Random(42)
        for _ in range(500):
            history = [{'content': 'x' * rng.randrange(80)} for _ in range(rng.randrange(1, 50))]
            budget = rng.randrange(400)
            expected = history[:]
            while len(expected) > 1 and sum(len(m['content']) for m in expected) > budget:
                expected.pop(0)
            namespace = {'clean_history': history[:], '_content_char_len': len,
                         'AI_CHAT_HISTORY_CHAR_BUDGET': budget}
            exec(code, namespace)
            self.assertEqual(namespace['clean_history'], expected)


if __name__ == '__main__':
    unittest.main()
