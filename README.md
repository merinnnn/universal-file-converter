# Universal File Converter
## Run with Docker 

```bash
docker compose up --build -d
```

Visit http://your-server-ip (nginx on port 80). 

## Adding a new conversion type

1. Create `app/converters/your_type.py`
2. Subclass `Converter`, implement `async def convert(self, input_path, output_path)`
3. Register format pairs: `register("from_ext", "to_ext")(YourConverterClass)`
4. Add `from . import your_type` to `app/converters/__init__.py`
5. If it needs a system binary, add it to the `Dockerfile`'s `apt-get install` line

## Security hardening

- **Content validation**: `app/validation.py` checks uploaded files' actual magic bytes against their claimed extension before conversion runs a `.png` that's actually a text file or executable gets rejected with a 400, not silently handed to a converter.
- **Rate limiting**: via `slowapi`. Global default of 60 requests/minute per IP, with a tighter 10/minute limit specifically on `/api/convert` since that's the expensive endpoint. Keyed off `X-Forwarded-For` (set by `nginx.conf`) so it tracks real client IPs, not nginx's own container IP.
