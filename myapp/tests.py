import base64
import io
import json
import tempfile
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import OperationalError
from django.http import HttpResponse
from django.test import RequestFactory
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image

from . import ai_chat, business_info, company_knowledge, doc_extract, dropbox_backup, image_generation, privacy, request_router
from .middleware import CanonicalHostMiddleware, PublicAssetCacheMiddleware
from .models import AIGeneratedFile, AIBlock, AIConversation, AIMessage, AINote, AIReport, GitHubConnection, StoreProfile
from .views import (
    AI_CURRENT_CONVERSATION_SESSION_KEY, _ai_document_instruction,
    _ai_generated_file_spec, _extract_ai_generated_file_content,
    site_customization_context,
)


class AIConversationPersistenceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='chat-persistence@example.com',
            email='chat-persistence@example.com',
            password='test-password-123',
        )
        StoreProfile.objects.create(user=self.user, phone='9999999999')

    def test_open_conversation_is_restored_on_authenticated_refresh(self):
        self.client.force_login(self.user)
        older = AIConversation.objects.create(user=self.user, title='Older chat')
        selected = AIConversation.objects.create(user=self.user, title='Selected chat')
        AIMessage.objects.create(conversation=selected, role=AIMessage.ROLE_USER, content='Keep this open')

        response = self.client.get(f'/AI/api/conversations/{selected.id}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.session[AI_CURRENT_CONVERSATION_SESSION_KEY], selected.id)

        response = self.client.get('/AI/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['ai_resume_conversation_id'], selected.id)
        self.assertContains(response, f'var AI_RESUME_CONVERSATION_ID = {selected.id};')
        self.assertNotEqual(older.id, response.context['ai_resume_conversation_id'])

    def test_refresh_falls_back_to_newest_owned_conversation(self):
        self.client.force_login(self.user)
        conversation = AIConversation.objects.create(user=self.user, title='Latest chat')

        response = self.client.get('/AI/')

        self.assertEqual(response.context['ai_resume_conversation_id'], conversation.id)
        self.assertEqual(self.client.session[AI_CURRENT_CONVERSATION_SESSION_KEY], conversation.id)

    def test_root_url_serves_the_ai_homepage(self):
        response = self.client.get('/')

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'ai.html')
        self.assertEqual(response.context['ai_default_model'], ai_chat.CHATGPT_56_MODEL_KEY)

    def test_flux_model_is_available_in_the_ai_picker(self):
        self.assertIn(ai_chat.FLUX_KLEIN_4B_MODEL_KEY, ai_chat.MODELS)
        self.assertEqual(ai_chat.MODELS[ai_chat.FLUX_KLEIN_4B_MODEL_KEY]['label'], 'FLUX.2 Klein 4B')

        response = self.client.get('/AI/')
        self.assertContains(response, 'FLUX.2 Klein 4B')

    def test_guest_chat_survives_login_and_remains_selected(self):
        session = self.client.session
        session.save()
        guest_session_key = session.session_key
        conversation = AIConversation.objects.create(
            session_key=guest_session_key,
            title='Guest chat',
        )
        AIMessage.objects.create(conversation=conversation, role=AIMessage.ROLE_USER, content='Before login')
        session[AI_CURRENT_CONVERSATION_SESSION_KEY] = conversation.id
        session.save()

        response = self.client.post(
            '/AI/api/login/',
            data=json.dumps({
                'identifier': self.user.email,
                'password': 'test-password-123',
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        conversation.refresh_from_db()
        self.assertEqual(conversation.user, self.user)
        self.assertEqual(conversation.session_key, '')
        self.assertEqual(self.client.session[AI_CURRENT_CONVERSATION_SESSION_KEY], conversation.id)

        response = self.client.get('/AI/')
        self.assertEqual(response.context['ai_resume_conversation_id'], conversation.id)
        response = self.client.get(f'/AI/api/conversations/{conversation.id}/')
        self.assertEqual(response.json()['messages'][0]['content'], 'Before login')


class NVIDIAImageGenerationTests(TestCase):
    PNG_BYTES = b'\x89PNG\r\n\x1a\nmock-image'

    @override_settings(
        NVIDIA_FLUX_API_KEY='test-flux-key',
        NVIDIA_FLUX_EDIT_API_KEY='test-edit-key',
    )
    @patch('myapp.image_generation.requests.post')
    def test_text_prompt_uses_flux_generation_schema(self, post):
        post.return_value.status_code = 200
        post.return_value.json.return_value = {
            'artifacts': [{'base64': base64.b64encode(self.PNG_BYTES).decode()}],
        }

        result = image_generation.generate_image('A futuristic learning robot')

        self.assertEqual(result.content, self.PNG_BYTES)
        self.assertEqual(result.extension, 'png')
        request = post.call_args
        self.assertNotIn('mode', request.kwargs['json'])
        self.assertEqual(request.kwargs['json']['steps'], 4)
        self.assertNotIn('image', request.kwargs['json'])
        self.assertEqual(request.kwargs['headers']['Authorization'], 'Bearer test-flux-key')

    @override_settings(
        NVIDIA_FLUX_API_KEY='test-flux-key',
        NVIDIA_FLUX_EDIT_API_KEY='test-edit-key',
    )
    @patch('myapp.image_generation.requests.post')
    def test_attached_image_uses_flux_editing_schema(self, post):
        post.return_value.status_code = 200
        post.return_value.json.return_value = {
            'artifacts': [{'base64': base64.b64encode(self.PNG_BYTES).decode()}],
        }
        source_bytes = io.BytesIO()
        Image.new('RGBA', (8, 6), (0, 0, 255, 128)).save(source_bytes, format='PNG')
        source = 'data:image/png;base64,' + base64.b64encode(source_bytes.getvalue()).decode()

        image_generation.generate_image('Remove the background', source)

        body = post.call_args.kwargs['json']
        self.assertNotIn('mode', body)
        self.assertEqual(len(body['image']), 1)
        self.assertTrue(body['image'][0].startswith('data:image/jpeg;base64,'))
        self.assertEqual(post.call_args.kwargs['headers']['Authorization'], 'Bearer test-edit-key')

    @override_settings(NVIDIA_FLUX_API_KEY='test-flux-key')
    @patch('myapp.image_generation.requests.post')
    def test_upstream_rate_limit_is_safe_and_actionable(self, post):
        post.return_value.status_code = 429

        with self.assertRaises(image_generation.ImageGenerationError) as raised:
            image_generation.generate_image('Create a poster')

        self.assertEqual(raised.exception.status_code, 429)
        self.assertIn('limit', str(raised.exception).lower())

    @override_settings(NVIDIA_FLUX_API_KEY='')
    @patch('myapp.image_generation.requests.post')
    def test_missing_flux_key_fails_without_an_upstream_request(self, post):
        with self.assertRaises(image_generation.ImageGenerationError) as raised:
            image_generation.generate_image('Create a poster')

        self.assertIn('NVIDIA_FLUX_API_KEY', str(raised.exception))
        post.assert_not_called()

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username='flux-tests@example.com', password='test-password-123', is_staff=True,
        )
        self.client.force_login(self.user)

    @patch('myapp.views.default_storage.url', return_value='/media/ai_generated/result.png')
    @patch('myapp.views.default_storage.save', return_value='ai_generated/result.png')
    @patch('myapp.views.image_generation.generate_image')
    def test_flux_chat_turn_saves_and_returns_generated_image(self, generate, save, storage_url):
        generate.return_value = image_generation.GeneratedImage(self.PNG_BYTES, 'png')

        response = self.client.post(
            '/AI/api/send/',
            data=json.dumps({
                'message': 'A futuristic EduTrellis AI robot',
                'model': ai_chat.FLUX_KLEIN_4B_MODEL_KEY,
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), '')
        self.assertEqual(response['X-Generated-Image-Url'], '/media/ai_generated/result.png')
        self.assertEqual(response['X-Request-Category'], 'image_generation')
        generate.assert_called_once_with('A futuristic EduTrellis AI robot', None)
        assistant = AIMessage.objects.get(role=AIMessage.ROLE_ASSISTANT)
        self.assertEqual(assistant.model_key, ai_chat.FLUX_KLEIN_4B_MODEL_KEY)
        self.assertEqual(assistant.image_data, '/media/ai_generated/result.png')

        history = self.client.get(f'/AI/api/conversations/{assistant.conversation_id}/').json()
        self.assertEqual(history['messages'][-1]['image_data'], '/media/ai_generated/result.png')

    @patch('myapp.views.default_storage.url', return_value='/media/ai_generated/edited.png')
    @patch('myapp.views.default_storage.save', return_value='ai_generated/edited.png')
    @patch('myapp.views.image_generation.generate_image')
    @patch('myapp.views.image_ocr.extract_data_uri', return_value='')
    def test_flux_chat_turn_edits_attachment_instead_of_routing_to_vision(
        self, ocr, generate, save, storage_url,
    ):
        generate.return_value = image_generation.GeneratedImage(self.PNG_BYTES, 'png')
        source = 'data:image/png;base64,AA=='

        response = self.client.post(
            '/AI/api/send/',
            data=json.dumps({
                'message': 'Make the background blue',
                'model': ai_chat.FLUX_KLEIN_4B_MODEL_KEY,
                'image': source,
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), '')
        self.assertEqual(response['X-Routed-Model-Key'], ai_chat.FLUX_KLEIN_4B_MODEL_KEY)
        self.assertEqual(response['X-Request-Category'], 'image_edit')
        generate.assert_called_once_with('Make the background blue', source)

    @patch('myapp.views.default_storage.url', return_value='/media/ai_generated/chatgpt.png')
    @patch('myapp.views.default_storage.save', return_value='ai_generated/chatgpt.png')
    @patch('myapp.views.image_generation.generate_image')
    def test_chatgpt_image_generation_hides_the_flux_worker_label(self, generate, save, storage_url):
        generate.return_value = image_generation.GeneratedImage(self.PNG_BYTES, 'png')

        response = self.client.post(
            '/AI/api/send/',
            data=json.dumps({
                'message': 'Generate an image of an orange robot',
                'model': ai_chat.CHATGPT_56_MODEL_KEY,
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['X-Model-Key'], ai_chat.CHATGPT_56_MODEL_KEY)
        self.assertEqual(response['X-Routed-Model-Key'], ai_chat.FLUX_KLEIN_4B_MODEL_KEY)
        assistant = AIMessage.objects.get(role=AIMessage.ROLE_ASSISTANT)
        self.assertEqual(assistant.model_key, ai_chat.CHATGPT_56_MODEL_KEY)

    @patch('myapp.views.default_storage.url', return_value='/media/ai_generated/cat.png')
    @patch('myapp.views.default_storage.save', return_value='ai_generated/cat.png')
    @patch('myapp.views.image_generation.generate_image')
    def test_report_9_hinglish_bna_prompt_routes_to_image_generation(self, generate, save, storage_url):
        generate.return_value = image_generation.GeneratedImage(self.PNG_BYTES, 'png')
        prompt = 'Cat ka image bna ke do'

        response = self.client.post(
            '/AI/api/send/',
            data=json.dumps({'message': prompt, 'model': ai_chat.CHATGPT_56_MODEL_KEY}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['X-Routed-Model-Key'], ai_chat.FLUX_KLEIN_4B_MODEL_KEY)
        self.assertEqual(response['X-Request-Category'], 'image_generation')
        generate.assert_called_once_with(prompt, None)

    @patch('myapp.views.image_generation.generate_image')
    def test_chatgpt_image_errors_never_expose_internal_provider_or_model_names(self, generate):
        generate.side_effect = image_generation.ImageGenerationError(
            "That image request was blocked by NVIDIA's content filter. Try a different prompt or image.",
            status_code=400,
        )

        response = self.client.post(
            '/AI/api/send/',
            data=json.dumps({
                'message': 'Generate an image of a person sitting on a bus',
                'model': ai_chat.CHATGPT_56_MODEL_KEY,
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response['X-Model-Key'], ai_chat.CHATGPT_56_MODEL_KEY)
        self.assertEqual(response['X-Routed-Model-Key'], ai_chat.FLUX_KLEIN_4B_MODEL_KEY)
        detail = response.json()['detail']
        self.assertEqual(
            detail,
            'That image request was blocked by the safety filter. Try a different prompt or image.',
        )
        for hidden_name in ('NVIDIA', 'FLUX', 'Nemotron', 'Black Forest'):
            self.assertNotIn(hidden_name.lower(), detail.lower())


class AIResponseReliabilityTests(TestCase):
    def test_request_routing_does_not_need_a_runtime_ml_model(self):
        self.assertEqual(request_router.classify('Debug this Python traceback'), 'code')
        self.assertEqual(request_router.classify('Research the latest facts and sources'), 'research')
        self.assertEqual(request_router.classify('Hello, how are you?'), 'general')
        self.assertEqual(request_router.choose_model('Fix this JavaScript bug', 'quick')[0], 'code')
        self.assertEqual(request_router.choose_chatgpt_worker('Hello, how are you?')[0], 'quick')
        self.assertEqual(request_router.choose_chatgpt_worker('Write a Python function')[0], 'code')

    def test_rate_limit_returns_friendly_user_message(self):
        user = User.objects.create_user(username='rate-limit@example.com', password='pw')
        self.client.force_login(user)

        with patch('myapp.views.AI_CHAT_RATE_LIMIT', 0):
            response = self.client.post(
                '/AI/api/send/',
                data=json.dumps({'message': 'hello'}),
                content_type='application/json',
            )

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()['status'], 'rate_limited')
        self.assertIn('Limit reached', response.json()['detail'])

    def test_chatgpt_uses_worker_model_with_stable_truthful_identity(self):
        chunk = SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content='answer'))])
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
            create=Mock(return_value=iter([chunk])),
        )))

        with patch('myapp.ai_chat._get_client', return_value=client):
            result = ''.join(ai_chat.stream_chat(
                [{'role': 'user', 'content': 'Write a Python function'}],
                model_key='code', identity_model_key=ai_chat.CHATGPT_56_MODEL_KEY,
            ))

        self.assertEqual(result, 'answer')
        request = client.chat.completions.create.call_args.kwargs
        self.assertEqual(request['model'], ai_chat.MODELS['code']['id'])
        self.assertEqual(request['messages'][0]['role'], 'system')
        self.assertIn('ChatGPT 5.6 in Vidhyora AI', request['messages'][0]['content'])
        self.assertIn('not the official OpenAI gpt-5.6 API', request['messages'][0]['content'])

    def test_chatgpt_is_the_fresh_default_on_every_page_load(self):
        response = self.client.get('/AI/')

        self.assertEqual(ai_chat.DEFAULT_MODEL_KEY, ai_chat.CHATGPT_56_MODEL_KEY)
        self.assertEqual(response.context['ai_default_model'], ai_chat.CHATGPT_56_MODEL_KEY)
        self.assertEqual(response.context['ai_default_model_label'], 'ChatGPT 5.6')
        self.assertNotContains(response, "localStorage.getItem('ai_model')")
        self.assertNotContains(response, "localStorage.setItem('ai_model'")

    def test_chatgpt_routes_general_code_and_image_turns(self):
        user = User.objects.create_user(
            username='chatgpt-router@example.com', password='test-password-123', is_staff=True,
        )
        self.client.force_login(user)

        with patch('myapp.views.ai_chat.stream_chat', side_effect=lambda *args, **kwargs: iter(['reply'])) as stream_chat:
            with patch('myapp.views.light_mode.save_from_chat'):
                with patch('myapp.views.image_ocr.extract_data_uri', return_value=''):
                    cases = (
                        ({'message': 'Hello there'}, 'quick', 'general'),
                        ({'message': 'Debug this Python function'}, 'code', 'code'),
                        ({'message': 'What is in this?', 'image': 'data:image/png;base64,AA=='}, 'vision', 'image'),
                    )
                    for extra_payload, worker_key, category in cases:
                        payload = {'model': ai_chat.CHATGPT_56_MODEL_KEY, **extra_payload}
                        response = self.client.post(
                            '/AI/api/send/', data=json.dumps(payload), content_type='application/json',
                        )
                        self.assertEqual(response.status_code, 200)
                        self.assertEqual(b''.join(response.streaming_content).decode(), 'reply')
                        self.assertEqual(response['X-Model-Key'], ai_chat.CHATGPT_56_MODEL_KEY)
                        self.assertEqual(response['X-Routed-Model-Key'], worker_key)
                        self.assertEqual(response['X-Request-Category'], category)
                        call = stream_chat.call_args
                        self.assertEqual(call.kwargs['model_key'], worker_key)
                        self.assertEqual(call.kwargs['identity_model_key'], ai_chat.CHATGPT_56_MODEL_KEY)

    def test_explicit_file_request_is_routed_and_downloadable_from_every_model(self):
        cache.clear()
        self.addCleanup(cache.clear)
        user = User.objects.create_user(
            username='file-owner@example.com', password='test-password-123', is_staff=True,
        )
        self.client.force_login(user)
        prompt = 'Generate a file named greeting.txt with the exact content Hello world and share a download link.'

        with patch('myapp.views.ai_chat.stream_chat', side_effect=lambda *args, **kwargs: iter(['```txt\nHello world\n```'])) as stream_chat:
            with patch('myapp.views.light_mode.save_from_chat'):
                for selected_model in ai_chat.MODELS:
                    with self.subTest(model=selected_model):
                        response = self.client.post(
                            '/AI/api/send/',
                            data=json.dumps({'message': prompt, 'model': selected_model}),
                            content_type='application/json',
                        )
                        self.assertEqual(response.status_code, 200)
                        body = b''.join(response.streaming_content).decode()
                        self.assertIn('[Download greeting.txt](', body)
                        self.assertEqual(response['X-Routed-Model-Key'], 'code')
                        self.assertEqual(response['X-Request-Category'], 'file_generation')
                        self.assertIn('application, not you', stream_chat.call_args.kwargs['document_instruction'])

        self.assertEqual(AIGeneratedFile.objects.filter(user=user).count(), len(ai_chat.MODELS))
        generated_file = AIGeneratedFile.objects.filter(user=user).first()
        self.assertEqual(generated_file.file_name, 'greeting.txt')
        self.assertEqual(generated_file.content, 'Hello world')

        download = self.client.get(f'/AI/api/files/{generated_file.token}/download/')
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download.content.decode(), 'Hello world')
        self.assertEqual(download['Content-Disposition'], 'attachment; filename="greeting.txt"')
        self.assertEqual(download['Cache-Control'], 'private, no-store')

        other_user = User.objects.create_user(username='other-file-user@example.com', password='pw')
        self.client.force_login(other_user)
        self.assertEqual(self.client.get(f'/AI/api/files/{generated_file.token}/download/').status_code, 404)

    def test_generated_file_intent_and_fence_extraction_are_conservative(self):
        self.assertEqual(
            _ai_generated_file_spec('Create a Python file named hello.py with a print statement.'),
            {'file_name': 'hello.py'},
        )
        self.assertEqual(
            _ai_generated_file_spec('Prepare a downloadable markdown document.'),
            {'file_name': 'generated.md'},
        )
        self.assertEqual(
            _ai_generated_file_spec('make a summarise note in word file'),
            {'file_name': 'generated.docx'},
        )
        self.assertIsNone(_ai_generated_file_spec('Explain what this Python file does.'))
        self.assertEqual(
            _extract_ai_generated_file_content('```python\nprint("hello")\n```'),
            'print("hello")',
        )

    def test_report_28_returns_a_genuine_downloadable_word_document(self):
        cache.clear()
        self.addCleanup(cache.clear)
        user = User.objects.create_user(
            username='word-file-owner@example.com', password='test-password-123', is_staff=True,
        )
        self.client.force_login(user)

        with patch(
            'myapp.views.ai_chat.stream_chat',
            return_value=iter(['```markdown\n# Summary Note\n\n- First important point\n- Second important point\n```']),
        ) as stream_chat:
            with patch('myapp.views.light_mode.save_from_chat'):
                response = self.client.post(
                    '/AI/api/send/',
                    data=json.dumps({
                        'message': 'make a summarise note in word file',
                        'model': ai_chat.CHATGPT_56_MODEL_KEY,
                    }),
                    content_type='application/json',
                )
                body = b''.join(response.streaming_content).decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn('[Download generated.docx](', body)
        self.assertIn('genuine DOCX file', stream_chat.call_args.kwargs['document_instruction'])
        generated_file = AIGeneratedFile.objects.get(user=user)
        download = self.client.get(f'/AI/api/files/{generated_file.token}/download/')

        self.assertEqual(download.status_code, 200)
        self.assertEqual(
            download['Content-Type'],
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        )
        self.assertTrue(download.content.startswith(b'PK'))
        word_document = doc_extract.DocxDocument(io.BytesIO(download.content))
        document_text = '\n'.join(paragraph.text for paragraph in word_document.paragraphs)
        self.assertIn('Summary Note', document_text)
        self.assertIn('First important point', document_text)

    def test_accuracy_rules_cover_maths_and_unclear_images(self):
        self.assertTrue(ai_chat.is_math_request('Solve 2x + 5 = 17'))
        self.assertTrue(ai_chat.is_math_request('Calculate 18% of 450'))
        self.assertFalse(ai_chat.is_math_request('Write a friendly customer email'))
        self.assertTrue(ai_chat.is_code_request('Fix this Django traceback'))
        self.assertFalse(ai_chat.is_code_request('Write a friendly customer email'))
        self.assertIn('never give only a number', ai_chat.COMPACT_SYSTEM_PROMPT)
        self.assertIn('ask for a clearer image', ai_chat.COMPACT_SYSTEM_PROMPT)
        self.assertIn('Never claim an action', ai_chat.COMPACT_SYSTEM_PROMPT)
        self.assertIn('complete, secure, directly usable code', ai_chat.CODE_SYSTEM_SUFFIX)
        self.assertIn('Do not claim code was executed or tested', ai_chat.CODE_SYSTEM_SUFFIX)

        chunk = SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content='answer'))])
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
            create=Mock(return_value=iter([chunk])),
        )))
        with patch('myapp.ai_chat._get_client', return_value=client):
            list(ai_chat.stream_chat([{'role': 'user', 'content': 'Calculate 2 + 3'}], model_key='quick'))
        sent_messages = client.chat.completions.create.call_args.kwargs['messages']
        late_reminder = sent_messages[-2]['content']
        self.assertIn('step-by-step', late_reminder)
        self.assertIn('**Final answer:**', late_reminder)
        self.assertIn('verify the result', late_reminder)

    def test_mixed_multimodal_request_gets_complete_response_rules(self):
        prompt = (
            "1. Calculate 15% of 800.\n"
            "2. Analyze the attached screenshot.\n"
            "3. Fix this Python error.\n"
            "4. Explain the relevant Django setting.\n"
            "5. Check whether the logic is valid.\n"
            "6. Product cost is 500, advertising is 100, selling price is 900; calculate profit percentage."
        )
        self.assertEqual(ai_chat.count_user_requests(prompt), 6)
        chunk = SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content='answer'))])
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
            create=Mock(return_value=iter([chunk])),
        )))
        content = [
            {'type': 'text', 'text': prompt},
            {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,AA=='}},
        ]
        with patch('myapp.ai_chat._get_client', return_value=client):
            list(ai_chat.stream_chat([{'role': 'user', 'content': content}], model_key='vision'))

        sent_messages = client.chat.completions.create.call_args.kwargs['messages']
        reminder = sent_messages[-2]['content']
        self.assertIn('Answer every one exactly once', reminder)
        self.assertIn('numbered section per item', reminder)
        self.assertIn('Total cost = product cost + advertising expense', reminder)
        self.assertIn('net profit / total cost × 100', reminder)
        self.assertIn('frontend-safe Markdown', reminder)
        self.assertIn('never labels like pythonCopy', reminder)
        self.assertIn('Analyse the attached image itself', reminder)
        self.assertIn('continue answering all other items', reminder)

    def test_note_router_understands_numbered_read_and_edit_commands(self):
        self.assertEqual(request_router.match_read_note('open note 1'), '1')
        self.assertEqual(request_router.match_read_note('read my note #2'), '#2')
        self.assertEqual(request_router.match_edit_note('edit note 1'), ('1', ''))
        self.assertEqual(request_router.match_edit_note('edit note 1 to Call at 7'), ('1', 'Call at 7'))
        self.assertTrue(request_router.is_note_intent('create a note: Call at 7'))

    def test_note_router_tolerates_common_typos_without_over_correcting(self):
        # A missed match here doesn't fail quietly — it falls through to the
        # real AI model, which (per its own history of this router's past
        # confirmations) fabricates its own fake "done!" instead of just not
        # understanding. See request_router._typo_correct_note_keywords.
        self.assertEqual(request_router.match_delete_note('delet all notyes'), request_router.DELETE_ALL_NOTES)
        self.assertTrue(request_router.is_note_intent('tkae this noet'))
        self.assertTrue(request_router.is_show_notes_intent('shwo my notess'))
        self.assertEqual(request_router.match_edit_note('edti note about milk to bread'), ('milk', 'bread'))
        self.assertEqual(request_router.match_read_note('opne note 1'), '1')
        self.assertTrue(request_router.is_note_intent('remmember a noet: call home'))
        self.assertEqual(request_router.match_delete_note('eraze note 2'), '2')
        self.assertEqual(request_router.match_edit_note('renmae note 1 to New title'), ('1', 'New title'))
        self.assertTrue(request_router.is_show_notes_intent('reed all notyes'))
        # Ordinary sentences that merely contain a word close to one of the
        # trigger keywords must never get swept in as a false positive —
        # 'made' -> 'make' would otherwise turn a past-tense remark into a
        # live "make a note" command.
        self.assertFalse(request_router.is_note_intent('she made a note about it yesterday, what should I do'))
        self.assertFalse(request_router.is_note_intent('I have not opened the store today'))

    def test_company_context_contains_verified_ai_contacts(self):
        self.assertTrue(company_knowledge.is_company_query('what is the sales team number?'))
        self.assertIn('+91 96959 53183', company_knowledge.PUBLIC_SITE_CONTEXT)
        self.assertIn('Vidhyora AI is an AI assistant', company_knowledge.PUBLIC_SITE_CONTEXT)
        self.assertNotIn('/websitecreation', company_knowledge.PUBLIC_SITE_CONTEXT)
        self.assertNotIn('/store', company_knowledge.PUBLIC_SITE_CONTEXT)

    def test_company_query_detection_covers_realistic_contact_phrasings(self):
        # These specific phrasings are what actually reached the AI model
        # ungrounded before this fix (the old regex required 'your ...' or
        # 'company's ...' or the brand name) — that gap, not a wrong fact in
        # the prompt itself, is what let it fabricate a fake US toll-free
        # number and a fake sales@edutrellis.com email for "sales team
        # number" style questions. See business_info.py for the real values.
        for query in (
            'sales number', 'contact number', 'WhatsApp number', 'sales email',
            'contact EduTrellis', 'company address', 'customer-support email',
            'how can I contact you?',
        ):
            self.assertTrue(company_knowledge.is_company_query(query), msg=query)
        # Unrelated messages must not get swept in as a false positive.
        for query in ('explain object oriented programming', 'help me write a poem'):
            self.assertFalse(company_knowledge.is_company_query(query), msg=query)

    def test_no_fabricated_contact_details_anywhere_in_ai_facing_text(self):
        wrong_markers = ('555', 'edutrellis.com', 'sales@edutrellis', '1-800', '1‑800')
        for text in (ai_chat.SYSTEM_PROMPT, company_knowledge.PUBLIC_SITE_CONTEXT):
            for marker in wrong_markers:
                self.assertNotIn(marker, text)
        # The real values must come from one shared source, not be retyped.
        self.assertIn(business_info.PHONE_DISPLAY, ai_chat.SYSTEM_PROMPT)
        self.assertIn(business_info.EMAIL_SUPPORT, ai_chat.SYSTEM_PROMPT)
        self.assertIn(business_info.PHONE_DISPLAY, company_knowledge.PUBLIC_SITE_CONTEXT)
        self.assertIn('no separate sales line', ai_chat.SYSTEM_PROMPT)
        self.assertIn('toll-free', company_knowledge.PUBLIC_SITE_CONTEXT)

    def test_knowledge_base_has_no_hallucinated_contact_entries(self):
        # Regression check for the specific cached chat reply that invented
        # a fake toll-free number and sales@edutrellis.com (purged by
        # migration 0042) — asserts the *class* of bad data can't be present,
        # not just that one row is gone.
        from myapp.models import KnowledgeEntry
        wrong_markers = ('edutrellis.com', 'sales@edutrellis', '1-800-555', '1‑800‑555')
        for entry in KnowledgeEntry.objects.all():
            for marker in wrong_markers:
                self.assertNotIn(marker, entry.content, msg=f'entry {entry.pk} ({entry.topic!r})')

    @override_settings(AI_USE_PRESIDIO=False)
    def test_fast_privacy_path_redacts_common_identifiers(self):
        redacted = privacy.redact('Email me@example.com or call 9876543210')

        self.assertEqual(redacted, 'Email <EMAIL> or call <PHONE>')

    def test_default_model_retries_on_quick_backend(self):
        chunk = SimpleNamespace(
            choices=[SimpleNamespace(delta=SimpleNamespace(content='Recovered reply'))]
        )
        create = SimpleNamespace()
        create.create = Mock(
            side_effect=[TimeoutError('upstream timed out'), iter([chunk])]
        )
        client = SimpleNamespace(chat=SimpleNamespace(completions=create))

        with patch('myapp.ai_chat._get_client', return_value=client):
            result = ''.join(ai_chat.stream_chat(
                [{'role': 'user', 'content': 'Hello'}], model_key=ai_chat.DEFAULT_MODEL_KEY
            ))

        self.assertEqual(result, 'Recovered reply')
        self.assertEqual(create.create.call_count, 2)
        self.assertEqual(
            create.create.call_args_list[1].kwargs['model'],
            ai_chat.MODELS['quick']['id'],
        )


class AINoteCRUDTests(TestCase):
    """Exercises My Notes end-to-end through /AI/api/send/, not just the
    request_router regex parsing — request_router.match_read_note/
    match_edit_note being correct in isolation once shipped with a plain
    `re.fullmatch(...)` call in views._ai_matching_notes with no `import re`
    at the top of views.py, which 500'd every read/edit/delete-by-number
    request while create/show (which never call that function) kept working
    silently. A regex-level unit test alone can't catch that class of bug."""
    def setUp(self):
        self.user = User.objects.create_user(
            username='note-crud@example.com', email='note-crud@example.com', password='test-password-123',
        )
        StoreProfile.objects.create(user=self.user, phone='9999999999')
        self.client.force_login(self.user)

    def send(self, message, conversation_id=None):
        payload = {'message': message}
        if conversation_id:
            payload['conversation_id'] = conversation_id
        response = self.client.post('/AI/api/send/', data=json.dumps(payload), content_type='application/json')
        body = b''.join(response.streaming_content).decode('utf-8')
        self.assertEqual(response.status_code, 200, msg=body)
        return response, body

    def test_full_note_lifecycle_via_chat(self):
        response, _ = self.send('note down: buy milk and eggs')
        conversation_id = int(response['X-Conversation-Id'])
        self.send('note down: call dentist tomorrow', conversation_id)
        self.assertEqual(AINote.objects.filter(user=self.user).count(), 2)

        _, show_body = self.send('show my notes', conversation_id)
        self.assertIn('buy milk and eggs', show_body)
        self.assertIn('call dentist tomorrow', show_body)

        _, read_body = self.send('open note 1', conversation_id)
        self.assertIn('call dentist tomorrow', read_body)

        edit_response, edit_body = self.send('replace note about milk with buy milk, eggs and bread', conversation_id)
        self.assertEqual(edit_response['X-Notes-Changed'], '1')
        self.assertIn('buy milk, eggs and bread', AINote.objects.get(heading__icontains='bread').content)

        delete_response, delete_body = self.send('delete note about dentist', conversation_id)
        self.assertEqual(delete_response['X-Notes-Changed'], '1')
        self.assertEqual(AINote.objects.filter(user=self.user).count(), 1)

        self.send('delete all my notes', conversation_id)
        self.assertEqual(AINote.objects.filter(user=self.user).count(), 0)

    def test_contextual_partial_edit_preserves_the_rest_of_the_note(self):
        response, _ = self.send('add note: I have to work tomorow at 4pm')
        conversation_id = int(response['X-Conversation-Id'])
        note = AINote.objects.get(user=self.user)
        self.assertEqual(note.content, 'I have to work tomorrow at 4pm')

        self.send('edit note 1', conversation_id)
        update_response, update_body = self.send('update the time to 7pm', conversation_id)
        self.assertEqual(update_response['X-Notes-Changed'], '1')
        note.refresh_from_db()
        self.assertEqual(note.content, 'I have to work tomorrow at 7pm')
        self.assertIn(note.content, update_body)

    def test_ambiguous_contextual_edit_asks_then_applies_the_choice(self):
        response, _ = self.send('save note: Meeting tomorrow at 4pm')
        conversation_id = int(response['X-Conversation-Id'])
        self.send('update the first note', conversation_id)

        ambiguous_response, ambiguous_body = self.send('update it to 7pm', conversation_id)
        self.assertNotIn('X-Notes-Changed', ambiguous_response)
        self.assertEqual(ambiguous_body, 'Should I update only the time to 7pm, or replace the full note?')
        self.assertEqual(AINote.objects.get(user=self.user).content, 'Meeting tomorrow at 4pm')

        final_response, final_body = self.send('only the time', conversation_id)
        self.assertEqual(final_response['X-Notes-Changed'], '1')
        self.assertEqual(AINote.objects.get(user=self.user).content, 'Meeting tomorrow at 7pm')
        self.assertIn('Meeting tomorrow at 7pm', final_body)

    def test_explicit_database_id_targets_note_without_text_search(self):
        response, _ = self.send('add note: Original text')
        conversation_id = int(response['X-Conversation-Id'])
        note = AINote.objects.get(user=self.user)

        update_response, _ = self.send(f'replace note id {note.pk} with Replaced by database ID', conversation_id)
        self.assertEqual(update_response['X-Notes-Changed'], '1')
        note.refresh_from_db()
        self.assertEqual(note.content, 'Replaced by database ID')

    def test_rename_changes_only_heading_and_never_stores_sidebar_number(self):
        response, _ = self.send('write note: Client meeting at 3pm')
        conversation_id = int(response['X-Conversation-Id'])
        note = AINote.objects.get(user=self.user)

        rename_response, rename_body = self.send('rename the first note to Tomorrow meeting', conversation_id)
        self.assertEqual(rename_response['X-Notes-Changed'], '1')
        note.refresh_from_db()
        self.assertEqual(note.heading, 'Tomorrow meeting')
        self.assertEqual(note.content, 'Client meeting at 3pm')
        self.assertFalse(note.heading.startswith('1.'))
        self.assertIn('Tomorrow meeting', rename_body)
        self.assertIn('Client meeting at 3pm', rename_body)

    def test_bare_save_never_copies_chat_history_and_empty_copy_is_exact(self):
        response, body = self.send('take a note')
        self.assertEqual(AINote.objects.filter(user=self.user).count(), 0)
        self.assertEqual(body, 'What would you like the note to say?')

        conversation_id = int(response['X-Conversation-Id'])
        _, body = self.send('show all notes', conversation_id)
        self.assertEqual(body, 'You don’t have any saved notes.')

    def test_chat_listing_and_sidebar_api_use_identical_database_snapshot(self):
        response, _ = self.send('create a note: first database note')
        conversation_id = int(response['X-Conversation-Id'])
        self.send('remember a note: second database note', conversation_id)

        api_notes = self.client.get('/AI/api/notes/').json()['notes']
        _, chat_body = self.send('view all notes', conversation_id)
        self.assertEqual([item['content'] for item in api_notes], ['second database note', 'first database note'])
        for item in api_notes:
            self.assertIn(item['content'], chat_body)
            self.assertEqual(chat_body.count(item['content']), 1)

        delete_response, _ = self.send('delet all notyes', conversation_id)
        self.assertEqual(delete_response['X-Notes-Changed'], '1')
        self.assertEqual(self.client.get('/AI/api/notes/').json()['notes'], [])


class AIAccountProfileTests(TestCase):
    def setUp(self):
        self.media_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.media_dir.cleanup)
        media_override = override_settings(MEDIA_ROOT=self.media_dir.name)
        media_override.enable()
        self.addCleanup(media_override.disable)

        self.user = User.objects.create_user(
            username='account@example.com', email='account@example.com',
            password='old-password', first_name='Account', last_name='Owner',
        )
        self.profile = StoreProfile.objects.create(
            user=self.user, phone='9999999999',
            phone_verified=True,
            ai_subscription_until=timezone.now() + timedelta(days=10),
        )
        self.other_user = User.objects.create_user(
            username='other@example.com', email='other@example.com', password='test-password-123',
        )
        StoreProfile.objects.create(user=self.other_user, phone='8888888888')
        self.client.force_login(self.user)

    def test_account_api_returns_subscription_and_only_own_report_statuses(self):
        conversation = AIConversation.objects.create(user=self.user, title='My reported chat')
        AIReport.objects.create(
            user=self.user, conversation=conversation, reported_reply='Incorrect reply',
            explanation='The answer was wrong.', model_key='quick', status=AIReport.STATUS_RESOLVED,
        )
        other_conversation = AIConversation.objects.create(user=self.other_user, title='Private other chat')
        AIReport.objects.create(
            user=self.other_user, conversation=other_conversation, reported_reply='Other reply',
            explanation='Must remain private.', status=AIReport.STATUS_OPEN,
        )

        response = self.client.get('/AI/api/account/')
        body = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(body['user']['name'], 'Account Owner')
        self.assertEqual(body['subscription']['plan_name'], 'Vidhyora AI Premium')
        self.assertTrue(body['subscription']['active'])
        self.assertEqual(len(body['reports']), 1)
        self.assertEqual(body['reports'][0]['status'], 'resolved')
        self.assertEqual(body['reports'][0]['status_label'], 'Resolved')
        self.assertNotContains(response, 'Private other chat')
        self.assertEqual(response['Cache-Control'], 'private, no-store')

    def test_profile_update_changes_login_email_name_phone_and_avatar(self):
        image_bytes = io.BytesIO()
        Image.new('RGB', (20, 20), (220, 20, 45)).save(image_bytes, format='PNG')
        avatar = SimpleUploadedFile('avatar.png', image_bytes.getvalue(), content_type='image/png')

        response = self.client.post('/AI/api/profile/update/', {
            'name': 'Updated Person', 'email': 'updated@example.com',
            'phone': '7777777777', 'avatar': avatar,
        })
        self.user.refresh_from_db()
        self.profile.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.user.get_full_name(), 'Updated Person')
        self.assertEqual(self.user.email, 'updated@example.com')
        self.assertEqual(self.user.username, 'account@example.com')
        self.assertEqual(self.profile.phone, '7777777777')
        self.assertFalse(self.profile.phone_verified)
        self.assertTrue(self.profile.avatar.name.endswith('.png'))
        self.assertContains(response, 'avatar_url')

    def test_profile_update_rejects_another_accounts_email(self):
        response = self.client.post('/AI/api/profile/update/', {
            'name': 'Account Owner', 'email': 'other@example.com', 'phone': '9999999999',
        })

        self.assertEqual(response.status_code, 400)
        self.assertIn('email', response.json()['errors'])
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'account@example.com')

    def test_password_change_keeps_user_logged_in(self):
        response = self.client.post(
            '/AI/api/profile/password/',
            data=json.dumps({'current_password': 'old-password', 'new_password': 'new-password'}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('new-password'))
        self.assertEqual(self.client.get('/AI/api/account/').status_code, 200)

    def test_ai_page_contains_profile_dropdown_and_all_account_panels(self):
        response = self.client.get('/AI/')

        self.assertContains(response, 'Edit profile')
        self.assertContains(response, 'Upload profile image')
        self.assertContains(response, 'Subscription details')
        self.assertContains(response, 'My reports')
        self.assertNotContains(response, '> Admin Panel</a>')

    def test_superuser_profile_dropdown_contains_admin_panel(self):
        superuser = User.objects.create_superuser(
            username='superadmin@example.com', email='superadmin@example.com', password='admin-password',
        )
        self.client.force_login(superuser)

        response = self.client.get('/AI/')

        self.assertContains(response, '> Admin Panel</a>')
        self.assertContains(response, 'href="/store/dashboard/"')
        self.assertNotContains(response, 'Back to site')

    def test_anonymous_user_cannot_read_account_details(self):
        self.client.logout()

        response = self.client.get('/AI/api/account/')

        self.assertEqual(response.status_code, 401)


class GitHubAccessTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='github-user@example.com', email='github-user@example.com',
            password='github-password', is_staff=False,
        )
        StoreProfile.objects.create(user=self.user, phone='9555555555')

    def test_github_button_and_status_are_available_to_regular_logged_in_user(self):
        self.client.force_login(self.user)

        page = self.client.get('/AI/')
        status = self.client.get('/AI/api/github/status/')

        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'id="githubBtn"')
        self.assertContains(page, 'Connect a repository')
        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.json(), {'status': 'ok', 'connected': False})

        self.client.logout()
        guest_page = self.client.get('/AI/')
        guest_status = self.client.get('/AI/api/github/status/')
        self.assertNotContains(guest_page, 'id="githubBtn"')
        self.assertEqual(guest_status.status_code, 401)

    @patch('myapp.views.github_ops.list_user_repos')
    @patch('myapp.views.github_ops.get_authenticated_user')
    def test_regular_user_can_connect_token_and_select_repository(self, get_user, list_repos):
        get_user.return_value = {'login': 'octocat'}
        list_repos.return_value = [
            {'full_name': 'octocat/demo', 'private': False, 'default_branch': 'main'},
            {'full_name': 'octocat/private-app', 'private': True, 'default_branch': 'develop'},
        ]
        self.client.force_login(self.user)

        response = self.client.post(
            '/AI/api/github/connect/', data=json.dumps({'token': 'secret-test-token'}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'secret-test-token')
        connection = GitHubConnection.objects.get(user=self.user)
        self.assertEqual(connection.github_username, 'octocat')
        self.assertEqual(connection.repo_full_name, 'octocat/demo')
        self.assertEqual(connection.access_token, 'secret-test-token')

        with patch('myapp.views.github_ops.get_repo', return_value={
            'full_name': 'octocat/private-app', 'default_branch': 'develop',
        }):
            select = self.client.post(
                '/AI/api/github/repo/', data=json.dumps({'repo': 'octocat/private-app'}),
                content_type='application/json',
            )
        self.assertEqual(select.status_code, 200)
        connection.refresh_from_db()
        self.assertEqual(connection.repo_full_name, 'octocat/private-app')
        self.assertEqual(connection.default_branch, 'develop')

    @override_settings(GITHUB_OAUTH_CLIENT_ID='github-client-id')
    def test_regular_user_can_start_github_oauth(self):
        self.client.force_login(self.user)

        response = self.client.get('/AI/api/github/oauth/start/')

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('https://github.com/login/oauth/authorize?'))
        self.assertIn('github_oauth_state', self.client.session)

    @override_settings(
        GITHUB_OAUTH_CLIENT_ID='github-client-id',
        GITHUB_OAUTH_CLIENT_SECRET='github-client-secret',
    )
    @patch('myapp.views.github_ops.list_user_repos')
    @patch('myapp.views.github_ops.get_authenticated_user')
    @patch('myapp.views.requests.post')
    def test_regular_user_can_complete_github_oauth(self, post, get_user, list_repos):
        token_response = Mock()
        token_response.json.return_value = {'access_token': 'oauth-secret-token'}
        post.return_value = token_response
        get_user.return_value = {'login': 'oauth-user'}
        list_repos.return_value = [
            {'full_name': 'oauth-user/project', 'private': True, 'default_branch': 'main'},
        ]
        self.client.force_login(self.user)
        session = self.client.session
        session['github_oauth_state'] = 'expected-state'
        session.save()

        response = self.client.get(
            '/AI/api/github/oauth/callback/?state=expected-state&code=temporary-code',
        )

        self.assertRedirects(response, '/AI/?github_connected=1', fetch_redirect_response=False)
        connection = GitHubConnection.objects.get(user=self.user)
        self.assertEqual(connection.access_token, 'oauth-secret-token')
        self.assertEqual(connection.github_username, 'oauth-user')
        self.assertEqual(connection.repo_full_name, 'oauth-user/project')

    @patch('myapp.views.ai_chat.github_plan_changes')
    @patch('myapp.views.ai_chat.github_select_files')
    @patch('myapp.views.github_ops.create_pull_request')
    @patch('myapp.views.github_ops.upsert_file')
    @patch('myapp.views.github_ops.create_branch')
    @patch('myapp.views.github_ops.get_branch_sha')
    @patch('myapp.views.github_ops.get_file')
    @patch('myapp.views.github_ops.get_tree')
    def test_regular_user_prompt_pushes_review_branch_and_opens_pull_request(
        self, get_tree, get_file, get_branch_sha, create_branch, upsert_file,
        create_pull_request, select_files, plan_changes,
    ):
        GitHubConnection.objects.create(
            user=self.user, access_token='secret-token', github_username='octocat',
            repo_full_name='octocat/demo', default_branch='main',
        )
        get_tree.return_value = ['app.py', 'README.md']
        select_files.return_value = ['app.py']
        get_file.return_value = ('print("old")\n', 'existing-sha')
        plan_changes.return_value = {
            'summary': 'Updated the greeting.',
            'commit_message': 'Update greeting',
            'operations': [
                {'action': 'update', 'path': 'app.py', 'content': 'print("hello")\n'},
            ],
        }
        get_branch_sha.return_value = 'base-sha'
        create_pull_request.return_value = {'html_url': 'https://github.com/octocat/demo/pull/7'}
        self.client.force_login(self.user)

        response = self.client.post('/AI/api/github/send/', data=json.dumps({
            'message': 'Change the greeting in app.py',
            'model': ai_chat.CHATGPT_56_MODEL_KEY,
        }), content_type='application/json')

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['status'], 'ok')
        self.assertEqual(body['model_key'], ai_chat.CHATGPT_56_MODEL_KEY)
        self.assertIn('https://github.com/octocat/demo/pull/7', body['reply'])
        created_branch = create_branch.call_args.args[3]
        self.assertTrue(created_branch.startswith('ai/'))
        upsert_file.assert_called_once_with(
            'secret-token', 'octocat', 'demo', 'app.py', 'print("hello")\n',
            'Update greeting', created_branch, sha='existing-sha',
        )
        create_pull_request.assert_called_once()
        self.assertEqual(AIMessage.objects.filter(conversation__user=self.user).count(), 2)
        self.assertEqual(
            AIMessage.objects.get(
                conversation__user=self.user, role=AIMessage.ROLE_ASSISTANT,
            ).model_key,
            ai_chat.CHATGPT_56_MODEL_KEY,
        )


class LocationConsentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='location-user@example.com', email='location-user@example.com',
            password='location-password',
        )
        self.profile = StoreProfile.objects.create(user=self.user, phone='9444444444')

    def test_authenticated_user_can_save_one_location_fix(self):
        self.client.force_login(self.user)

        response = self.client.post('/AI/api/location/', data=json.dumps({
            'consent': 'granted', 'latitude': 20.296059,
            'longitude': 85.824539, 'accuracy': 18.6,
        }), content_type='application/json')

        self.assertEqual(response.status_code, 200)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.location_consent, StoreProfile.LOCATION_GRANTED)
        self.assertEqual(self.profile.location_latitude, Decimal('20.296059'))
        self.assertEqual(self.profile.location_longitude, Decimal('85.824539'))
        self.assertEqual(self.profile.location_accuracy_m, 19)
        self.assertIsNotNone(self.profile.location_updated_at)

    def test_declining_location_is_saved_and_clears_old_coordinates(self):
        self.profile.location_consent = StoreProfile.LOCATION_GRANTED
        self.profile.location_latitude = Decimal('20.296059')
        self.profile.location_longitude = Decimal('85.824539')
        self.profile.location_accuracy_m = 20
        self.profile.save()
        self.client.force_login(self.user)

        response = self.client.post(
            '/AI/api/location/', data=json.dumps({'consent': 'denied'}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.location_consent, StoreProfile.LOCATION_DENIED)
        self.assertIsNone(self.profile.location_latitude)
        self.assertIsNone(self.profile.location_longitude)
        self.assertIsNone(self.profile.location_accuracy_m)

    def test_invalid_or_anonymous_location_updates_are_rejected(self):
        anonymous = self.client.post(
            '/AI/api/location/', data=json.dumps({'consent': 'denied'}),
            content_type='application/json',
        )
        self.assertEqual(anonymous.status_code, 401)

        self.client.force_login(self.user)
        invalid = self.client.post('/AI/api/location/', data=json.dumps({
            'consent': 'granted', 'latitude': 95, 'longitude': 85, 'accuracy': 10,
        }), content_type='application/json')
        self.assertEqual(invalid.status_code, 400)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.location_consent, StoreProfile.LOCATION_UNKNOWN)

    def test_prompt_is_shown_until_a_choice_has_been_saved(self):
        self.client.force_login(self.user)

        response = self.client.get('/')
        self.assertTrue(response.context['show_location_prompt'])
        self.assertContains(response, 'Enable one-time access')
        self.assertContains(response, 'No continuous or background tracking')

        self.profile.location_consent = StoreProfile.LOCATION_DENIED
        self.profile.location_updated_at = timezone.now()
        self.profile.save(update_fields=['location_consent', 'location_updated_at'])
        response = self.client.get('/')
        self.assertFalse(response.context['show_location_prompt'])


class AIDashboardOverviewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='dashboard-admin@example.com', email='dashboard-admin@example.com',
            password='admin-password',
        )
        StoreProfile.objects.create(user=self.admin, phone='9000000000')
        self.customer = User.objects.create_user(
            username='ai-customer@example.com', email='ai-customer@example.com', password='customer-password',
        )
        self.customer_profile = StoreProfile.objects.create(
            user=self.customer, phone='9111111111',
            manual_amount_paid=Decimal('1250.50'),
            ai_subscription_until=timezone.now() + timedelta(days=30),
            location_consent=StoreProfile.LOCATION_GRANTED,
            location_latitude=Decimal('20.296059'),
            location_longitude=Decimal('85.824539'),
            location_accuracy_m=25,
            location_updated_at=timezone.now(),
        )
        self.customer_chat = AIConversation.objects.create(user=self.customer, title='Customer AI chat')
        self.guest_chat = AIConversation.objects.create(
            session_key='guest-session', ip_address='203.0.113.10', title='Guest AI chat',
        )
        AIMessage.objects.create(conversation=self.customer_chat, role=AIMessage.ROLE_USER, content='Question')
        AIMessage.objects.create(
            conversation=self.customer_chat, role=AIMessage.ROLE_ASSISTANT,
            content='Answer', model_key='quick',
        )
        AIReport.objects.create(
            user=self.customer, conversation=self.customer_chat, reported_reply='Answer',
            explanation='Needs correction', status=AIReport.STATUS_OPEN,
        )
        AIReport.objects.create(
            conversation=self.guest_chat, session_key='guest-session', reported_reply='Guest answer',
            explanation='Already handled', status=AIReport.STATUS_RESOLVED,
        )
        AIBlock.objects.create(user=self.customer, reason='Test block', created_by=self.admin)
        self.client.force_login(self.admin)

    def test_overview_contains_ai_metrics_and_recent_ai_data(self):
        response = self.client.get('/store/dashboard/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_conversations'], 2)
        self.assertEqual(response.context['total_messages'], 2)
        self.assertEqual(response.context['registered_ai_users'], 1)
        self.assertEqual(response.context['guest_conversations'], 1)
        self.assertEqual(response.context['active_subscribers'], 1)
        self.assertEqual(response.context['open_reports'], 1)
        self.assertEqual(response.context['resolved_reports'], 1)
        self.assertEqual(response.context['active_blocks'], 1)
        self.assertContains(response, 'Customer AI chat')
        self.assertContains(response, 'Guest AI chat')
        self.assertContains(response, 'Needs correction')
        self.assertContains(response, 'AI Overview')
        self.assertEqual(len(response.context['daily_activity']), 7)
        self.assertEqual(response.context['registered_conversations'], 1)
        self.assertEqual(response.context['registered_pct'], 50)
        self.assertEqual(response.context['guest_pct'], 50)
        self.assertEqual(response.context['report_total'], 2)
        self.assertEqual(response.context['report_open_pct'], 50)
        self.assertEqual(response.context['model_usage'][0]['key'], 'quick')
        self.assertEqual(response.context['location_enabled'], 1)
        self.assertEqual(response.context['location_declined'], 0)
        self.assertEqual(response.context['location_not_asked'], 1)
        self.assertEqual(response.context['location_enabled_pct'], 50)
        self.assertContains(response, 'AI activity')
        self.assertContains(response, 'Conversation audience')
        self.assertContains(response, 'Report status')
        self.assertContains(response, 'AI model usage')
        self.assertContains(response, 'Location permission')

    def test_sidebar_keeps_only_ai_pwa_and_backup_options(self):
        response = self.client.get('/store/dashboard/')

        for label in ('Overview', 'Signups', 'AI Management', 'AI Activity', 'AI Reports', 'PWA / Install App', 'Backup &amp; Restore'):
            self.assertContains(response, label)
        self.assertContains(response, 'href="/" class="dash-logo"')
        self.assertNotContains(response, 'Back to store')
        self.assertNotContains(response, 'Back to site')
        for removed_path in (
            '/store/dashboard/contacts/', '/store/dashboard/categories/',
            '/store/dashboard/products/', '/store/dashboard/orders/', '/store/dashboard/delivery/',
            '/store/dashboard/payments/', '/store/dashboard/payment-settings/',
            '/store/dashboard/fee-settings/', '/store/dashboard/email-settings/',
            '/store/dashboard/about/', '/store/dashboard/policies/',
        ):
            self.assertNotContains(response, 'href="' + removed_path + '"')

    def test_signups_page_shows_graph_total_and_per_user_amount(self):
        response = self.client.get('/store/dashboard/signups/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_amount_paid'], Decimal('1250.50'))
        self.assertEqual(len(response.context['signup_chart']), 7)
        self.assertEqual(response.context['signups_today'], 2)
        self.assertEqual(response.context['signups_last_7_days'], 2)
        self.assertEqual(response.context['signups_this_month'], 2)
        self.assertEqual(response.context['paid_users'], 1)
        self.assertEqual(response.context['no_recorded_payment'], 1)
        self.assertEqual(response.context['paid_users_pct'], 50)
        self.assertEqual(
            [(role['label'], role['count']) for role in response.context['account_roles']],
            [('Customers', 1), ('Staff', 0), ('Superusers', 1)],
        )
        self.assertContains(response, 'Signups — last 7 days')
        self.assertContains(response, 'Total Amount Paid')
        self.assertContains(response, 'Joined Today')
        self.assertContains(response, 'Recorded payment coverage')
        self.assertContains(response, 'Account roles')
        self.assertContains(response, 'Location Enabled')
        self.assertContains(response, '20.2961, 85.8245')
        self.assertContains(response, '1250.50')
        self.assertContains(response, 'name="amount_paid"')

    def test_manual_user_amount_paid_is_optional_and_saved_when_provided(self):
        response = self.client.post('/store/dashboard/users/add/', {
            'next': 'dashboard_signups', 'name': 'Paid Customer',
            'email': 'paid-customer@example.com', 'phone': '9222222222',
            'password': 'customer-password', 'amount_paid': '499.99',
        })

        self.assertRedirects(response, '/store/dashboard/signups/')
        paid_profile = StoreProfile.objects.get(user__email='paid-customer@example.com')
        self.assertEqual(paid_profile.manual_amount_paid, Decimal('499.99'))

        optional_response = self.client.post('/store/dashboard/users/add/', {
            'next': 'dashboard_signups', 'name': 'Free Customer',
            'email': 'free-customer@example.com', 'phone': '9333333333',
            'password': 'customer-password', 'amount_paid': '',
        })
        self.assertRedirects(optional_response, '/store/dashboard/signups/')
        free_profile = StoreProfile.objects.get(user__email='free-customer@example.com')
        self.assertEqual(free_profile.manual_amount_paid, Decimal('0.00'))


class DashboardBackupDeletionTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='backup-admin@example.com', email='backup-admin@example.com', password='admin-password',
        )
        StoreProfile.objects.create(user=self.admin, phone='9444444444')
        self.client.force_login(self.admin)

    def test_backup_page_contains_typed_delete_all_confirmation(self):
        response = self.client.get('/store/dashboard/backup/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Delete All Backups')
        self.assertContains(response, 'name="confirmation"')
        self.assertContains(response, 'pattern="DELETE ALL"')
        self.assertContains(response, '/store/dashboard/backup/delete-all/')

    @patch('myapp.views.SiteCustomization.get_solo', side_effect=OperationalError('no such table'))
    def test_pages_survive_an_old_backup_before_customization_migration(self, get_solo):
        context = site_customization_context(RequestFactory().get('/store/'))

        self.assertEqual(context, {'SITE_FAVICON_URL': None})

    @patch('myapp.views.call_command')
    @patch('myapp.views.dropbox_backup.restore_backup')
    def test_restore_automatically_migrates_an_older_backup(self, restore_backup, call_command):
        with patch('django.contrib.sessions.backends.db.SessionStore.save') as session_save:
            response = self.client.post(
                '/store/dashboard/backup/restore/', {'filename': 'older-backup.sqlite3'},
            )

        self.assertRedirects(response, '/store/dashboard/backup/', fetch_redirect_response=False)
        restore_backup.assert_called_once()
        call_command.assert_called_once_with('migrate', interactive=False, verbosity=0)
        self.assertTrue(any(call.kwargs.get('must_create') for call in session_save.call_args_list))

    @patch('myapp.views.dropbox_backup.delete_all_backups')
    def test_delete_all_view_requires_exact_confirmation(self, delete_all):
        response = self.client.post(
            '/store/dashboard/backup/delete-all/', {'confirmation': 'delete all'}, follow=True,
        )

        self.assertEqual(response.status_code, 200)
        delete_all.assert_not_called()
        self.assertContains(response, 'Type DELETE ALL exactly')

    @patch('myapp.views.dropbox_backup.delete_all_backups', return_value=3)
    def test_delete_all_view_calls_dropbox_after_confirmation(self, delete_all):
        response = self.client.post(
            '/store/dashboard/backup/delete-all/', {'confirmation': 'DELETE ALL'}, follow=True,
        )

        self.assertEqual(response.status_code, 200)
        delete_all.assert_called_once()
        self.assertContains(response, 'Deleted 3 Dropbox backup items.')

    def test_helper_deletes_only_entries_inside_backup_folder_including_latest(self):
        dbx = Mock()
        dbx.files_list_folder.return_value = SimpleNamespace(
            entries=[
                SimpleNamespace(path_lower='/edutrellis store/backups/db_20260831.sqlite3'),
                SimpleNamespace(path_lower='/edutrellis store/backups/db_latest.sqlite3'),
                SimpleNamespace(path_lower='/unrelated/never-delete.sqlite3'),
            ],
            has_more=False,
        )

        with patch('myapp.dropbox_backup._client', return_value=dbx):
            deleted = dropbox_backup.delete_all_backups(SimpleNamespace())

        self.assertEqual(deleted, 2)
        self.assertEqual(dbx.files_delete_v2.call_count, 2)
        dbx.files_delete_v2.assert_any_call('/edutrellis store/backups/db_20260831.sqlite3')
        dbx.files_delete_v2.assert_any_call('/edutrellis store/backups/db_latest.sqlite3')


class RemovedPublicSurfaceTests(TestCase):
    def test_storefront_and_websitecreation_urls_are_gone(self):
        for path in (
            '/store/', '/store', '/estore', '/estore/',
            '/websitecreation/', '/websitecreation/contact/',
            '/contact/', '/store/api/cart/', '/store/product/anything/',
            '/store/policy/privacy/',
        ):
            self.assertEqual(self.client.get(path).status_code, 404, msg=path)

    def test_404_uses_the_saved_ai_frontend_theme(self):
        response = self.client.get('/missing-page/')
        self.assertContains(response, "localStorage.getItem('ai_theme')", status_code=404)
        self.assertContains(response, "localStorage.getItem('ai_color_theme')", status_code=404)
        self.assertContains(response, 'data-accent="blue"', status_code=404)
        self.assertContains(response, '--red:#ff7a00', status_code=404)

    def test_ai_and_dashboard_routes_remain(self):
        self.assertEqual(self.client.get('/').status_code, 200)
        self.assertEqual(self.client.get('/AI/').status_code, 200)

        staff = User.objects.create_user('dashboard-admin', password='password', is_staff=True)
        StoreProfile.objects.create(user=staff)
        self.client.force_login(staff)
        self.assertEqual(self.client.get('/store/dashboard/').status_code, 200)

    def test_mobile_feature_intro_lists_images_and_models_and_closes_model_stack(self):
        response = self.client.get('/AI/')
        self.assertContains(response, 'Generate and edit images')
        self.assertContains(response, 'Access multiple AI models')
        self.assertContains(response, "localStorage.setItem('ai_model_intro_seen', '1')")
        self.assertContains(response, 'if (modelDropdown) modelDropdown.hidden = true')
        self.assertContains(response, 'max-height:calc(100dvh - 24px)')

    def test_apex_domain_redirects_to_ai_homepage(self):
        middleware = CanonicalHostMiddleware(lambda request: HttpResponse('page'))
        response = middleware(RequestFactory().get('/', HTTP_HOST='edutrellis.in', secure=True))
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response['Location'], 'https://www.edutrellis.in/')

    def test_ai_assets_receive_browser_cache_headers(self):
        middleware = PublicAssetCacheMiddleware(lambda request: HttpResponse('asset'))
        response = middleware(RequestFactory().get('/static/ai-icon-192.png'))
        self.assertIn('max-age=86400', response['Cache-Control'])


class HTMLExtractionTests(TestCase):
    HTML = b'''<!doctype html>
        <html><head><style>.hidden { display:none }</style></head>
        <body><h1>Upload title</h1><p>Tom &amp; Jerry</p>
        <script>stealSecret()</script><noscript>hidden fallback</noscript></body></html>'''

    def test_html_uses_standard_library_fallback_without_bs4(self):
        with patch.dict('sys.modules', {'bs4': None}):
            text, truncated = doc_extract.extract('example.html', self.HTML)

        self.assertIn('Upload title', text)
        self.assertIn('Tom & Jerry', text)
        self.assertNotIn('stealSecret', text)
        self.assertNotIn('display:none', text)
        self.assertNotIn('hidden fallback', text)
        self.assertFalse(truncated)

    def test_html_upload_endpoint_returns_extracted_text(self):
        upload = SimpleUploadedFile('example.html', self.HTML, content_type='text/html')

        response = self.client.post('/AI/api/extract/', {'file': upload})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'ok')
        self.assertIn('Upload title', response.json()['text'])
        self.assertIn('<h1>Upload title</h1>', response.json()['coding_text'])
        self.assertIn('<script>stealSecret()</script>', response.json()['coding_text'])

    def test_common_source_code_file_is_supported_without_renaming(self):
        source = b'def greet(name):\n    return f"Hello {name}"\n'

        text, truncated = doc_extract.extract('app.py', source)
        coding_text, coding_truncated = doc_extract.extract_editable_source('app.py', source, text)

        self.assertEqual(text, source.decode())
        self.assertEqual(coding_text, source.decode())
        self.assertFalse(truncated)
        self.assertFalse(coding_truncated)

    def test_document_action_instructions_keep_coding_and_details_separate(self):
        coding = _ai_document_instruction('coding', 'index.html')
        details = _ai_document_instruction('details', 'index.html')

        self.assertIn('COMPLETE updated file', coding)
        self.assertIn('never return only a patch', coding)
        self.assertIn('Analyse and explain only', details)
        self.assertIn('Do not rewrite the file', details)


class AIDocumentActionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='document-actions@example.com',
            email='document-actions@example.com',
            password='test-password-123',
            is_staff=True,
        )
        self.client.force_login(self.user)

    def test_coding_action_forces_code_mode_and_full_file_instruction(self):
        payload = {
            'message': 'Change the theme colors to blue.',
            'model': 'light',
            'document_name': 'index.html',
            'document_text': '<html><body>Original</body></html>',
            'document_mode': 'coding',
            'document_truncated': False,
        }
        with patch('myapp.views.ai_chat.stream_chat', return_value=iter(['updated file'])) as stream_chat:
            with patch('myapp.views.light_mode.save_from_chat'):
                response = self.client.post(
                    '/AI/api/send/', data=json.dumps(payload), content_type='application/json'
                )
                body = b''.join(response.streaming_content).decode()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(body, 'updated file')
        kwargs = stream_chat.call_args.kwargs
        self.assertEqual(kwargs['model_key'], 'code')
        self.assertEqual(kwargs['max_tokens'], 6000)
        self.assertIn('COMPLETE updated file', kwargs['document_instruction'])

    def test_details_action_keeps_analysis_only_instruction(self):
        payload = {
            'message': 'Show details about this file only.',
            'model': 'quick',
            'document_name': 'report.pdf',
            'document_text': 'Quarterly report content',
            'document_mode': 'details',
        }
        with patch('myapp.views.ai_chat.stream_chat', return_value=iter(['details'])) as stream_chat:
            with patch('myapp.views.light_mode.save_from_chat'):
                response = self.client.post(
                    '/AI/api/send/', data=json.dumps(payload), content_type='application/json'
                )
                b''.join(response.streaming_content)

        kwargs = stream_chat.call_args.kwargs
        self.assertEqual(kwargs['model_key'], 'quick')
        self.assertIsNone(kwargs['max_tokens'])
        self.assertIn('Do not rewrite the file', kwargs['document_instruction'])
