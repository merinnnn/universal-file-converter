import asyncio
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app import jobs
from app import validation
from app.converters import registry
import app.converters  # noqa: F401 - triggers registration of all converters

MAX_UPLOAD_BYTES = 500 * 1024 * 1024  # 500 MB

def get_client_ip(request: Request):
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return get_remote_address(request)

limiter = Limiter(key_func=get_client_ip, default_limits=["60/minute"])

app = FastAPI(title="Universal File Converter")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.on_event("startup")
async def start_background_sweeper():
    asyncio.create_task(jobs.sweep_expired_jobs_forever())

@app.get("/api/formats")
def list_targets(from_ext: str):
    targets = registry.available_targets(from_ext.lower().lstrip("."))
    return {
        "from": from_ext.lower(),
        "targets": targets
        }

@app.post("/api/convert")
@limiter.limit("10/minute")
async def converter(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    to: str = "",
):
    if not to:
        raise HTTPException(400, "missing target format ?to=...")

    original_name = file.filename or "upload"
    from_ext = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""
    to_ext = to.lower().lstrip(".")

    if not from_ext:
        raise HTTPException(400, "could not determine source file extension")

    path = registry.find_path(from_ext, to_ext)
    if path is None:
        raise HTTPException(
            415,
            f"no conversion path from '{from_ext}' to '{to_ext}'. "
            f"Available targets for '{from_ext}': {registry.available_targets(from_ext)}",
        )

    job = jobs.create_job()
    input_path = job.dir / f"input.{from_ext}"

    size = 0
    header = b""
    validated = False
    with open(input_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                jobs.delete_job(job.id)
                raise HTTPException(413, "file too large")
            f.write(chunk)

            # Validate against magic bytes as soon as we have enough of the file to do so
            if not validated:
                header += chunk
                if len(header) >= validation.SNIFF_BYTES_NEEDED:
                    if not validation.sniff_matches(from_ext, header):
                        jobs.delete_job(job.id)
                        raise HTTPException(
                            400,
                            f"file content does not match its '.{from_ext}' extension",
                        )
                    validated = True

    if not validated and not validation.sniff_matches(from_ext, header):
        jobs.delete_job(job.id)
        raise HTTPException(400, f"file content does not match its '.{from_ext}' extension")

    job.status = "processing"
    background_tasks.add_task(_run_conversion, job.id, path, input_path, to_ext)

    return{
        "job_id": job.id, 
        "status": job.status
        }

async def _run_conversion(job_id: str, converter_chain, input_path: Path, to_ext: str):
    job = jobs.get_job(job_id)
    if job is None: 
        return
    try:
        current_input = input_path
        for i, converter in enumerate(converter_chain):
            is_last = i == len(converter_chain) - 1
            out_name = f"output.{to_ext}" if is_last else f"intermediate_{i}.{converter.to_ext}"
            out_path = job.dir / out_name
            await converter.convert(current_input, out_path)
            if current_input != input_path:
                # Cleanup
                current_input.unlink(missing_ok=True)
            current_input = out_path

        job.output_filename = current_input.name
        job.status = "done"
    except Exception as e:
        job.status = "failed"
        job.error = str(e)
    finally:
        # Delete original file past this point
        jobs.delete_input_file(job, input_path)

@app.get("/api/status/{job_id}")
def status(job_id: str):
    job = jobs.get_job(job_id)
    if job is None:
        raise HTTPException(404, "job not found or already expired")
    return {
        "job_id": job.id,
        "status": job.status,
        "error": job.error
    }

@app.get("/api/download/{job_id}")
def download(job_id: str, background_tasks: BackgroundTasks):
    job = jobs.get_job(job_id)
    if job is None:
        raise HTTPException(404, "job not found or already expired")
    if job.status != "done" or job.output_path is None or not job.output_path.exists():
        raise HTTPException(409, f"job is not ready (status: {job.status})")

    output_path = job.output_path
    filename = output_path.name

    background_tasks.add_task(jobs.delete_job, job_id)

    return FileResponse(path=output_path, filename=filename, background=background_tasks)

@app.delete("/api/job/{job_id}")
def cancel_or_discard(job_id: str):
    """Manual discard endpoint."""
    jobs.delete_job(job_id)
    return {"deleted": True}

@app.post("/api/job/{job_id}/discard")
def discard_via_beacon(job_id: str):
    """
    navigator.sendBeacon only supports POST, so this mirrors the
    DELETE endpoint above for the beforeunload best-effort cleanup.
    """
    jobs.delete_job(job_id)
    return {"deleted": True}

app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")