"""Run on the deployed server to test its actual chat configuration safely."""
import time

from django.core.management.base import BaseCommand, CommandError
from myapp import ai_chat


class Command(BaseCommand):
    help = 'Check the configured chat endpoint without exposing credentials or using fallback.'

    def handle(self, *args, **options):
        cfg = ai_chat.MODELS['quick']
        self.stdout.write('Upstream model: ' + cfg['id'])
        started = time.monotonic()
        try:
            stream = ai_chat._get_client().chat.completions.create(
                model=cfg['id'], messages=[{'role': 'user', 'content': 'Reply with OK only.'}],
                max_tokens=64, stream=True, timeout=25,
                extra_body={'chat_template_kwargs': {'enable_thinking': False, 'force_nonempty_content': True}},
            )
            received = False
            try:
                for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        self.stdout.write(f'First content: {time.monotonic() - started:.2f}s')
                        received = True
                        break
            finally:
                stream.close()
            if not received:
                raise CommandError('Upstream returned no answer content.')
        except CommandError:
            raise
        except Exception as exc:
            raise CommandError(
                f'{type(exc).__name__}; HTTP {getattr(exc, "status_code", "unavailable")}; '
                f'elapsed {time.monotonic() - started:.2f}s. Check the deployed API key/model and provider status.'
            ) from None
        self.stdout.write(self.style.SUCCESS('Upstream responded successfully.'))
