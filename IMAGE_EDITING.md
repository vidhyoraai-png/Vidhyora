Uploaded image editing
======================

Pillow already normalizes uploaded PNG, JPEG, and WebP images: EXIF orientation,
proportional resizing to 1024 pixels, transparency flattening, and JPEG encoding.
Edit instructions with an attachment route automatically to FLUX; the selected
ChatGPT 5.5 or 5.6 name is retained in response headers and saved messages.

The hosted NVIDIA FLUX preview accepts only preset example images. Conversion
cannot make it accept an arbitrary upload:
https://docs.api.nvidia.com/nim/reference/black-forest-labs-flux_2-klein-4b-infer

To enable actual uploads, deploy an upload-capable FLUX.2 Klein NIM and set
FLUX_EDIT_API_URL to its full inference URL. Set FLUX_EDIT_API_KEY only if that
deployment requires bearer authentication. Restart Django after configuration.
The adapter sends the existing FLUX JSON request with an image array containing
a JPEG data URI and expects the NIM artifacts/base64 response. Normal image
generation continues to use the hosted endpoint. Hosted credentials are never
forwarded to the custom endpoint.

Deployment documentation:
https://docs.nvidia.com/nim/visual-genai/latest/getting-started.html

An upload-capable deployment has not been configured or live-tested here.

Qwen Image Edit
---------------

The model picker also supports Qwen Image Edit. Set QWEN_IMAGE_EDIT_API_URL to
the full /v1/infer URL of a running Qwen Image Edit NIM. If that server requires
bearer authentication, set QWEN_IMAGE_EDIT_ENDPOINT_KEY. Restart Django.
The adapter sends prompt, a normalized JPEG image data URI, and seed, and
validates the returned artifacts/base64 image before saving it.

The supplied NVIDIA key is stored in the ignored .secrets directory and loaded
as NVIDIA_QWEN_IMAGE_EDIT_API_KEY. It is not automatically sent to a custom
server. No documented hosted inference endpoint was found; a probe of
https://ai.api.nvidia.com/v1/genai/qwen/qwen-image-edit returned HTTP 404.
This does not validate or invalidate the key. No live Qwen edit has succeeded.

NVIDIA deployment and upload examples:
https://docs.nvidia.com/nim/visual-genai/latest/getting-started.html
