import base64
import io
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings
from PIL import Image

from myapp import ai_chat, image_generation
from myapp.views import _ai_public_routed_model_key, _chatgpt_image_error_detail


class ImageEditAdapterTests(SimpleTestCase):
    @override_settings(NVIDIA_FLUX_API_KEY='primary', NVIDIA_FLUX_BACKUP_API_KEY='secondary',
                       NVIDIA_FLUX_DEV_API_KEY='dev')
    @patch('myapp.image_generation._decode_artifact')
    @patch('myapp.image_generation.requests.post')
    def test_klein_key_failover_before_dev(self, post, decode):
        failed = Mock(status_code=503)
        failed.json.return_value = {}
        success = Mock(status_code=200)
        for failures in (1, 2):
            with self.subTest(failures=failures):
                post.reset_mock()
                post.side_effect = [failed] * failures + [success]
                self.assertIs(image_generation.generate_image('A blue mug'), decode.return_value)
                calls = post.call_args_list
                self.assertEqual(len(calls), failures + 1)
                self.assertEqual(calls[0].kwargs['headers']['Authorization'], 'Bearer primary')
                self.assertEqual(calls[1].kwargs['headers']['Authorization'], 'Bearer secondary')
                self.assertEqual(calls[0].args[0], calls[1].args[0])
                self.assertEqual(calls[0].kwargs['json'], calls[1].kwargs['json'])
                if failures == 2:
                    self.assertTrue(calls[2].args[0].endswith('/flux.1-dev'))
                    self.assertEqual(calls[2].kwargs['headers']['Authorization'], 'Bearer dev')

    @override_settings(NVIDIA_FLUX_DEV_API_KEY='backup-test-key')
    @patch('myapp.image_generation._decode_artifact')
    @patch('myapp.image_generation.requests.post')
    @patch('myapp.image_generation._dispatch_generate')
    def test_generation_failure_uses_flux_dev_schema_and_credential(self, dispatch, post, decode):
        dispatch.side_effect = image_generation.ImageGenerationError('Primary unavailable')
        post.return_value.status_code = 200
        result = image_generation.generate_image('A blue mug', model_key='flux-klein-4b')
        self.assertIs(result, decode.return_value)
        self.assertTrue(post.call_args.args[0].endswith('/flux.1-dev'))
        self.assertEqual(post.call_args.kwargs['headers']['Authorization'], 'Bearer backup-test-key')
        body = post.call_args.kwargs['json']
        self.assertEqual(body['prompt'], 'A blue mug')
        self.assertEqual((body['width'], body['height']), (1024, 1024))
        self.assertEqual(body['mode'], 'base')
        self.assertNotIn('image', body)
        post.assert_called_once()

    @override_settings(NVIDIA_FLUX_DEV_API_KEY='backup-test-key')
    @patch('myapp.image_generation._generate_flux_dev')
    @patch('myapp.image_generation._dispatch_generate')
    def test_success_does_not_call_backup(self, dispatch, backup):
        self.assertIs(image_generation.generate_image('A blue mug'), dispatch.return_value)
        backup.assert_not_called()

    @override_settings(NVIDIA_FLUX_DEV_API_KEY='backup-test-key')
    @patch('myapp.image_generation._generate_flux_dev')
    @patch('myapp.image_generation._dispatch_generate')
    def test_upload_and_other_model_failures_do_not_call_backup(self, dispatch, backup):
        dispatch.side_effect = image_generation.ImageGenerationError('Unavailable')
        for source, model in [('upload', None), (None, 'sdxl-lightning')]:
            with self.subTest(source=source, model=model):
                with self.assertRaises(image_generation.ImageGenerationError):
                    image_generation.generate_image('A blue mug', source, model_key=model)
        backup.assert_not_called()

    @override_settings(QWEN_IMAGE_EDIT_API_URL='')
    @patch('myapp.image_generation.requests.post')
    def test_qwen_requires_deployment(self, post):
        with self.assertRaises(image_generation.ImageGenerationError) as raised:
            image_generation.generate_image('Make it blue', 'image', model_key='qwen-image-edit')
        self.assertIn('not connected', str(raised.exception))
        post.assert_not_called()

    @override_settings(QWEN_IMAGE_EDIT_API_URL='http://localhost:8002/v1/infer', QWEN_IMAGE_EDIT_ENDPOINT_KEY='')
    @patch('myapp.image_generation._decode_artifact')
    @patch('myapp.image_generation.requests.post')
    def test_qwen_sends_uploaded_image_to_nim(self, post, decode):
        source = io.BytesIO()
        Image.new('RGB', (64, 64), 'red').save(source, 'PNG')
        uri = 'data:image/png;base64,' + base64.b64encode(source.getvalue()).decode()
        post.return_value.status_code = 200
        image_generation.generate_image('Make it blue', uri, model_key='qwen-image-edit')
        self.assertEqual(post.call_args.args[0], 'http://localhost:8002/v1/infer')
        self.assertNotIn('Authorization', post.call_args.kwargs['headers'])
        self.assertTrue(post.call_args.kwargs['json']['image'].startswith('data:image/jpeg;base64,'))
        decode.assert_called_once()

    @override_settings(NVIDIA_FLUX_KONTEXT_API_KEY='kontext-test', FLUX_EDIT_API_URL='')
    @patch('myapp.image_generation._decode_artifact')
    @patch('myapp.image_generation.requests.post')
    def test_kontext_uses_own_key_and_single_image_schema(self, post, decode):
        source = io.BytesIO()
        Image.new('RGB', (64, 64), 'red').save(source, 'PNG')
        uri = 'data:image/png;base64,' + base64.b64encode(source.getvalue()).decode()
        post.return_value.status_code = 200
        image_generation.generate_image('Make it blue', uri, model_key='flux-kontext-dev')
        request = post.call_args
        self.assertTrue(request.args[0].endswith('flux.1-kontext-dev'))
        self.assertEqual(request.kwargs['headers']['Authorization'], 'Bearer kontext-test')
        body = request.kwargs['json']
        self.assertIsInstance(body['image'], str)
        self.assertEqual(body['steps'], 30)
        self.assertNotIn('width', body)
        self.assertNotIn('height', body)

    def test_kontext_requires_source_image(self):
        with self.assertRaises(image_generation.ImageGenerationError) as raised:
            image_generation.generate_image('Draw a cat', model_key='flux-kontext-dev')
        self.assertEqual(raised.exception.status_code, 400)

    @override_settings(FLUX_EDIT_API_URL='http://localhost:8001/v1/infer', FLUX_EDIT_API_KEY='')
    @patch('myapp.image_generation._decode_artifact')
    @patch('myapp.image_generation.requests.post')
    def test_upload_is_converted_and_sent_to_edit_server_without_hosted_key(self, post, decode):
        source = io.BytesIO()
        Image.new('RGBA', (2048, 1024), (255, 0, 0, 128)).save(source, 'PNG')
        uri = 'data:image/png;base64,' + base64.b64encode(source.getvalue()).decode()
        post.return_value.status_code = 200
        image_generation.generate_image('change name to sindore', uri)
        self.assertEqual(post.call_args.args[0], 'http://localhost:8001/v1/infer')
        self.assertNotIn('Authorization', post.call_args.kwargs['headers'])
        encoded = post.call_args.kwargs['json']['image'][0].split(',', 1)[1]
        with Image.open(io.BytesIO(base64.b64decode(encoded))) as converted:
            self.assertEqual(converted.mode, 'RGB')
            self.assertEqual(converted.size, (1024, 512))
        decode.assert_called_once()

    @override_settings(FLUX_EDIT_API_URL='', NVIDIA_FLUX_EDIT_API_KEY='hosted-preview-key')
    @patch('myapp.image_generation.requests.post')
    def test_hosted_preview_is_not_sent_arbitrary_uploads(self, post):
        source = io.BytesIO()
        Image.new('RGB', (64, 64), 'red').save(source, 'PNG')
        uri = 'data:image/png;base64,' + base64.b64encode(source.getvalue()).decode()

        with self.assertRaises(image_generation.ImageGenerationError) as raised:
            image_generation.generate_image('Make it blue', uri)

        self.assertTrue(raised.exception.editing_unavailable)
        post.assert_not_called()

    def test_preview_restriction_does_not_blame_file_size(self):
        response = Mock(status_code=422)
        response.json.return_value = {'detail': 'expected: example_id'}
        error = image_generation._safe_error(response)
        self.assertEqual(error.status_code, 503)
        self.assertNotIn('smaller', str(error))

    def test_gpt_names_survive_image_routing(self):
        for key in (ai_chat.CHATGPT_56_MODEL_KEY, 'gpt-oss-20b'):
            self.assertEqual(_ai_public_routed_model_key(key, ai_chat.FLUX_KLEIN_4B_MODEL_KEY), key)
            error = image_generation.ImageGenerationError('NVIDIA unavailable')
            self.assertIn(ai_chat.MODELS[key]['label'], _chatgpt_image_error_detail(error, key))
        self.assertTrue(ai_chat.is_image_edit_instruction('change name to sindore'))
