"""Fast, best-effort OCR for images attached to Vidhyora AI."""
import base64
import io
import logging

from PIL import Image

logger = logging.getLogger(__name__)
MAX_OCR_CHARS = 6000
_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        from rapidocr_onnxruntime import RapidOCR
        _engine = RapidOCR()
    return _engine


def extract_data_uri(data_uri):
    """Return detected text, QR/barcode values, or empty text on failure."""
    try:
        import numpy as np
        encoded = data_uri.split(',', 1)[1]
        raw = base64.b64decode(encoded, validate=True)
        image = Image.open(io.BytesIO(raw)).convert('RGB')
        pixels = np.asarray(image)
        extras = []
        try:
            import cv2
            bgr = cv2.cvtColor(pixels, cv2.COLOR_RGB2BGR)
            gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
            gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
            # If the photo looks like a sheet of paper, flatten its four
            # corners before OCR. Ordinary photos simply keep the enhanced
            # grayscale image.
            edges = cv2.Canny(gray, 60, 180)
            contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
            for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:5]:
                perimeter = cv2.arcLength(contour, True)
                corners = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
                if len(corners) != 4 or cv2.contourArea(corners) < gray.size * 0.2:
                    continue
                points = corners.reshape(4, 2).astype('float32')
                sums, diffs = points.sum(axis=1), np.diff(points, axis=1).reshape(-1)
                ordered = np.array([
                    points[np.argmin(sums)], points[np.argmin(diffs)],
                    points[np.argmax(sums)], points[np.argmax(diffs)],
                ], dtype='float32')
                tl, tr, br, bl = ordered
                width = int(max(np.linalg.norm(br - bl), np.linalg.norm(tr - tl)))
                height = int(max(np.linalg.norm(tr - br), np.linalg.norm(tl - bl)))
                target = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], dtype='float32')
                gray = cv2.warpPerspective(gray, cv2.getPerspectiveTransform(ordered, target), (width, height))
                break
            processed = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)
            qr_value, _, _ = cv2.QRCodeDetector().detectAndDecode(bgr)
            if qr_value:
                extras.append(f"QR code: {qr_value}")
        except Exception:
            processed = pixels
        try:
            from pyzbar.pyzbar import decode
            for barcode in decode(image):
                value = barcode.data.decode('utf-8', errors='replace')
                extras.append(f"{barcode.type}: {value}")
        except Exception:
            pass
        result, _ = _get_engine()(processed)
        if not result:
            return '\n'.join(extras)[:MAX_OCR_CHARS]
        lines = [str(item[1]).strip() for item in result if len(item) > 1 and str(item[1]).strip()]
        return '\n'.join(extras + lines)[:MAX_OCR_CHARS]
    except Exception as exc:
        # Vision analysis must continue even if optional local OCR fails.
        logger.info("Image OCR unavailable or unsuccessful: %s", exc)
        return ''
