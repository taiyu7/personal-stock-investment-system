import multiprocessing
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from personal_stock_investment_system.research.batch_job import run_video_batch_job, terminate_video_batch_process


def _run_empty_batch() -> None:
    context = multiprocessing.get_context("spawn")
    output = context.Queue()
    process = context.Process(
        target=run_video_batch_job,
        args=((), (), (), None, Path("unused.db"), output),
    )
    process.start()
    message = output.get(timeout=15)
    process.join(timeout=15)
    assert process.exitcode == 0
    assert message[0] == "aggregate"
    completed = output.get(timeout=5)
    assert completed[0] == "done"
    assert completed[1].items == ()
    output.close()


def _wait_forever() -> None:
    import time

    while True:
        time.sleep(1)


def _stop_running_process() -> None:
    context = multiprocessing.get_context("spawn")
    process = context.Process(target=_wait_forever)
    process.start()
    assert process.is_alive()
    terminate_video_batch_process(process)
    assert not process.is_alive()


def test_batch_worker_can_run_outside_streamlit():
    _run_empty_batch()


def test_batch_worker_can_be_forcibly_stopped():
    _stop_running_process()


if __name__ == "__main__":
    _run_empty_batch()
    _stop_running_process()
    print("batch job process checks passed")
