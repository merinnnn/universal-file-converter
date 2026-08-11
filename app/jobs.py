import asyncio
import shutil
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

JOBS_ROOT = Path("/tmp/fileconverter_jobs")
JOB_TTL_SECONDS = 15 * 60   # delete anything older
SWEEP_INTERVAL_SECONDS = 60

JOBS_ROOT.mkdir(parents=True, exist_ok=True)

@dataclass
class Job:
    id: str
    status: str = "pending"
    error: Optional[str] = None
    output_filename: Optional[str] = None
    created_at: float = field(default_factory=time.time)

    @property
    def dir(self) -> Path:
        return JOBS_ROOT / self.id

    @property
    def output_path(self) -> Optional[Path]:
        if self.output_filename is None:
            return None
        return self.dir / self.output_filename



_JOBS: Dict[str, Job] = {}

def create_job() -> Job:
    job = Job(id=str(uuid.uuid4()))
    job.dir.mkdir(parents=True, exist_ok=True)
    _JOBS[job.id] = job
    return job

def get_job(job_id: str) -> Optional[Job]:
    return _JOBS.get(job_id)

def delete_job(job_id: str) -> None:
    job = _JOBS.pop(job_id, None)
    if job and job.dir.exists():
        shutil.rmtree(job.dir, ignore_errors=True)

def delete_input_file(job: Job, input_path: Path) -> None:
    if input_path.exists():
        input_path.unlink(missing_ok=True)

async def sweep_expired_jobs_forever() -> None:
    while True:
        await asyncio.sleep(SWEEP_INTERVAL_SECONDS)
        now = time.time()
        expired = [j.id for j in list(_JOBS.values()) if now - j.created_at > JOB_TTL_SECONDS]
        for job_id in expired:
            delete_job(job_id)

        for child in JOBS_ROOT.iterdir():
            if child.is_dir() and child.name not in _JOBS:
                if now - child.stat().st_mtime > JOB_TTL_SECONDS:
                    shutil.rmtree(child, ignore_errors=True)