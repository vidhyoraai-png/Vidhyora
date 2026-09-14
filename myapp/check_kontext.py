"""Run with python manage.py shell -c 'from myapp.check_kontext import run; run()'."""
import base64
import io
from pathlib import Path

import requests
from django.conf import settings
from PIL import Image, ImageDraw

from myapp.image_generation import _decode_artifact


def run():
    image = Image.new('RGB', (512, 512), 'white')
    ImageDraw.Draw(image).rectangle((128, 128, 384, 384), fill='red')
    buffer = io.BytesIO()
    image.save(buffer, 'PNG')
    uploaded = 'data:image/png;base64,' + base64.b64encode(buffer.getvalue()).decode()
    for name, source in [('upload', uploaded), ('preset', 'data:image/png;example_id,0')]:
        response = requests.post(
            'https://ai.api.nvidia.com/v1/genai/black-forest-labs/flux.1-kontext-dev',
            headers={'Authorization': 'Bearer ' + settings.NVIDIA_FLUX_KONTEXT_API_KEY},
            json={'prompt': 'Change the main subject to blue. Keep the composition unchanged.',
                  'image': source,
                  'steps': 30, 'samples': 1, 'seed': 1, 'aspect_ratio': 'match_input_image'},
            timeout=120,
        )
        print(name, 'HTTP', response.status_code, flush=True)
        if response.status_code == 200:
            result = _decode_artifact(response.json())
            target = Path(settings.BASE_DIR) / 'media' / 'ai_generated' / ('kontext-test-' + name + '.' + result.extension)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(result.content)
            print('Decoded image saved:', target.name, flush=True)
        else:
            detail = response.json().get('detail', '')
            print([item.get('msg') for item in detail] if isinstance(detail, list) else str(detail)[:500], flush=True)
