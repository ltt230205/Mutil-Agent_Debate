import json

from src.utils.checkpoint import open_resumable_jsonl, write_checkpoint


def test_resumable_jsonl_tracks_completed_records(tmp_path) -> None:
    path = tmp_path / "records.jsonl"
    record = {"seed": 42, "sample_id": "x", "method": "single_direct"}

    handle, completed = open_resumable_jsonl(path, overwrite=False, resume=True)
    assert completed == set()
    with handle:
        write_checkpoint(handle, record)

    handle, completed = open_resumable_jsonl(path, overwrite=False, resume=True)
    with handle:
        pass
    assert completed == {(42, "x", "single_direct")}
    assert json.loads(path.read_text(encoding="utf-8").strip()) == record
