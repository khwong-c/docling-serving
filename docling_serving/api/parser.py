from .models.response import JobSummary, ConversionStatus
from ..workers.work_queue import Job, JobStatus

status_map = {
    JobStatus.QUEUED: ConversionStatus.PENDING,
    JobStatus.PROCESSING: ConversionStatus.STARTED,
    JobStatus.COMPLETED: ConversionStatus.SUCCESS,
    JobStatus.FAILED: ConversionStatus.FAILURE,
}


def create_summary_from_job(job: Job) -> JobSummary:
    return JobSummary(
        id=job.id,
        status=status_map[job.status],
    )
