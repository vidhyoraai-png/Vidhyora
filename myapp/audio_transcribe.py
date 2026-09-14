"""Local speech-to-text powered by faster-whisper."""
import os
import tempfile

_model = None


def transcribe(filename, file_bytes):
    global _model
    try:
        if _model is None:
            from faster_whisper import WhisperModel
            _model = WhisperModel('tiny', device='cpu', compute_type='int8')
        suffix = os.path.splitext(filename or '')[1] or '.webm'
        path = None
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
            path = handle.name
            handle.write(file_bytes)
        try:
            segments, _ = _model.transcribe(path, beam_size=1, vad_filter=True)
            return ' '.join(segment.text.strip() for segment in segments).strip()
        finally:
            if path and os.path.exists(path):
                os.unlink(path)
    except Exception as exc:
        raise RuntimeError(f"Could not transcribe that audio: {exc}")
