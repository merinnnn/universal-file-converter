# Universal File Converter

Self-hosted, extensible file conversion service. Drag-and-drop UI, plugin-based converter registry, no persistent storage of uploaded or converted files.

# What's here

- **Image conversions** (Pillow): png/jpg/webp/bmp/tiff/ico, all pairs
- **Video/audio conversions** (ffmpeg): mp4/mov/avi/mkv/webm/wav/mp3/flac/m4a, common pairs
- **Document/PDF/ebook conversions**:
  - LibreOffice: docx<-->pdf, pptx-->pdf, xlsx-->pdf, odt<-->pdf, docx<-->odt
  - Poppler (`pdftoppm`): pdf-->jpg, pdf-->png
  - Pillow: jpg/png-->pdf
  - Pandoc + Weasyprint: epub<-->pdf, epub<-->docx, epub-->html
  - The registry chains these automatically
- **HEIC/HEIF conversions** (pillow-heif): heic/heif<-->jpg/png/webp
- **JFIF**: essentially a JPEG variant, converts to/from jpg/png/webp
- **Vectorization** (vtracer): png/jpg-->svg. Works best on flat-color art (logos, icons), photos will trace but produce large, messy SVGs since that's inherent to vectorization, not a bug
- **GIF/animation conversions**:
  - video<-->gif via ffmpeg
  - image<-->gif via Pillow (static image --> single-frame gif, gif --> first frame as png/jpg)
  - apng<-->gif via Pillow, extracting every animation frame and re-encoding into the target container
- Drag-and-drop frontend at `/`
- Ephemeral job storage: files live in `/tmp/fileconverter_jobs/<uuid>/`,
  deleted immediately after download, and swept by TTL (15 min default) as a backstop
- Docker + docker-compose + nginx reverse proxy, ready to deploy

## Run with Docker 

```bash
docker compose up --build -d
```

Visit http://your-server-ip (nginx on port 80). 

## Run locally (no Docker)

```bash
pip install -r requirements.txt
# also need ffmpeg on your system: apt install ffmpeg
uvicorn app.main:app --reload --port 8000
```

Visit http://localhost:8000

## Adding a new conversion type

1. Create `app/converters/your_type.py`
2. Subclass `Converter`, implement `async def convert(self, input_path, output_path)`
3. Register format pairs: `register("from_ext", "to_ext")(YourConverterClass)`
4. Add `from . import your_type` to `app/converters/__init__.py`
5. If it needs a system binary, add it to the `Dockerfile`'s `apt-get install` line

## Security hardening

- **Content validation**: `app/validation.py` checks uploaded files' actual magic bytes against their claimed extension before conversion runs a `.png` that's actually a text file or executable gets rejected with a 400, not silently handed to a converter.
- **Rate limiting**: via `slowapi`. Global default of 60 requests/minute per IP, with a tighter 10/minute limit specifically on `/api/convert` since that's the expensive endpoint. Keyed off `X-Forwarded-For` (set by `nginx.conf`) so it tracks real client IPs, not nginx's own container IP.
