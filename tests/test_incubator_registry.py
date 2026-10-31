"""Incubator registry: registered candidates can never be edited, re-registered or backdated."""

import datetime as dt
import json

import pytest

from fxbot.incubator import registry as reg

UTC = dt.timezone.utc
F1 = {"box_start": 0, "cutoff": 10, "sl_frac": 1.0, "tp_mult": 2.5}
ML_MODEL = "research/phase4/a1_ml_day/models/round5_full.pkl"


def _reg(root, cid="f1_test", day=dt.datetime(2026, 11, 1, 9, tzinfo=UTC)):
    return reg.register(cid, "families", "LondonBreakout", F1, root=root, now=day, require_clean=False)


def test_register_writes_manifest_fingerprint_and_chain(tmp_path):
    c = _reg(tmp_path)
    m = json.loads((c.dir / "manifest.json").read_text())
    assert m["registered"] == "2026-11-01" and m["first_scored_day"] == "2026-11-02"
    assert m["params"] == F1 and m["class"] == "LondonBreakout" and len(m["source_commit"]) >= 7
    assert set(m["files"]) == {"code/__init__.py", "code/families.py", "code/ml_day.py"}
    assert reg.fingerprint(m) == c.fingerprint
    entries = reg.read_chain(reg.registry_path(tmp_path))
    assert entries[0]["id"] == "f1_test" and entries[0]["fingerprint"] == c.fingerprint
    assert reg.verify_all(tmp_path) == {"f1_test": "ok"}


def test_same_id_can_never_be_registered_again(tmp_path):
    _reg(tmp_path)
    with pytest.raises(reg.RegistryError, match="already registered"):
        _reg(tmp_path, day=dt.datetime(2026, 11, 2, tzinfo=UTC))


def test_no_backdating(tmp_path):
    _reg(tmp_path, "f1_a", dt.datetime(2026, 11, 5, tzinfo=UTC))
    with pytest.raises(reg.RegistryError, match="backdating"):
        _reg(tmp_path, "f1_b", dt.datetime(2026, 11, 4, tzinfo=UTC))


def test_register_has_no_date_argument():
    import inspect
    assert "registered" not in inspect.signature(reg.register).parameters


@pytest.mark.parametrize("change", ["code", "manifest", "extra", "missing", "params"])
def test_any_edit_is_detected(tmp_path, change):
    c = _reg(tmp_path)
    if change == "code":
        p = c.dir / "code" / "families.py"
        p.write_text(p.read_text() + "\n# tweak\n")
    elif change == "manifest":
        m = json.loads((c.dir / "manifest.json").read_text())
        m["notes"] = "edited"
        (c.dir / "manifest.json").write_text(json.dumps(m))
    elif change == "params":
        m = json.loads((c.dir / "manifest.json").read_text())
        m["params"]["tp_mult"] = 3.0
        (c.dir / "manifest.json").write_text(json.dumps(m, indent=1, sort_keys=True) + "\n")
    elif change == "extra":
        (c.dir / "code" / "helper.py").write_text("x = 1\n")
    else:
        (c.dir / "code" / "ml_day.py").unlink()
    c2 = reg.candidates(tmp_path)[0]
    with pytest.raises(reg.TamperedError):
        reg.verify(c2)
    with pytest.raises(reg.TamperedError):
        reg.load_strategy(c2)
    assert reg.verify_all(tmp_path)["f1_test"] != "ok"


def test_registry_chain_cannot_be_edited_or_trimmed(tmp_path):
    _reg(tmp_path, "f1_a")
    _reg(tmp_path, "f1_b")
    path = reg.registry_path(tmp_path)
    entries = json.loads(path.read_text())
    edited = [dict(entries[0], fingerprint="0" * 64), entries[1]]
    path.write_text(json.dumps(edited))
    with pytest.raises(reg.TamperedError):
        reg.candidates(tmp_path)
    path.write_text(json.dumps(entries[1:]))           # first entry removed
    with pytest.raises(reg.TamperedError):
        reg.candidates(tmp_path)


def test_runs_from_frozen_copy_not_from_src(tmp_path):
    c = _reg(tmp_path)
    s = reg.load_strategy(c)
    import sys
    assert str(c.dir) in sys.modules[type(s).__module__].__file__
    assert type(s).__module__ != "fxbot.strategies.families"
    assert s.params == {**s.defaults, **F1}


def test_ml_model_copied_hashed_and_loaded_frozen(tmp_path):
    params = {"model": "gb", "feats": "own", "pool": "all", "margin": 0.08, "model_file": ML_MODEL}
    c = reg.register("a1_test", "ml_day", "MLDay", params, [ML_MODEL], root=tmp_path,
                     now=dt.datetime(2026, 11, 1, tzinfo=UTC), require_clean=False)
    assert c.manifest["params"]["model_file"] == "models/round5_full.pkl"
    assert c.manifest["files"]["models/round5_full.pkl"] == reg.sha256_file(reg.ROOT / ML_MODEL)
    s = reg.load_strategy(c)
    assert s.frozen.kind == "gb" and type(s.frozen).__module__.startswith("_fxinc_a1_test")
    with pytest.raises(Exception):
        s.frozen.fit()
    (c.dir / "models" / "round5_full.pkl").write_bytes(b"x")
    with pytest.raises(reg.TamperedError):
        reg.verify(c)


def test_broken_candidate_is_not_registered(tmp_path):
    with pytest.raises(AttributeError):
        reg.register("bad_one", "families", "NoSuchClass", {}, root=tmp_path,
                     now=dt.datetime(2026, 11, 1, tzinfo=UTC), require_clean=False)
    assert not reg.registry_path(tmp_path).exists()
    assert not (tmp_path / "candidates" / "bad_one").exists()


def test_real_registry_is_intact():
    """The committed incubator: chain intact and every candidate exactly as registered."""
    if not reg.registry_path().exists():
        pytest.skip("no candidates registered yet")
    status = reg.verify_all()
    assert status and all(v == "ok" for v in status.values()), status
