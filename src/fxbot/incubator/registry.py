"""Strategy incubator registry: frozen candidates with fingerprints (CLAUDE.md, Strategy incubator).

A candidate is registered once. Registration copies everything it needs into
incubator/candidates/<id>/ and never touches it again:

    code/__init__.py, code/families.py, code/ml_day.py   frozen strategy code
    models/<file>                                        model files (as they are)
    manifest.json                                        id, class, parameters, commit, date,
                                                         SHA-256 of every file above

The candidate runs from that frozen copy, so later edits to
src/fxbot/strategies/ cannot change it. Its fingerprint (SHA-256 of the
manifest) goes into incubator/registry.json, an append-only hash chain: each
entry carries the hash of the one before, so editing or removing an old
entry breaks the chain. verify() re-hashes every file before each use and
raises TamperedError on any difference, a missing file or an extra file.

The registration date is the UTC day the code runs. It cannot be passed in
(tests can inject a clock) and cannot be earlier than any registered date.
A candidate is scored only on days after it (forward-only).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import importlib.util
import io
import json
import pickle
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
INCUBATOR = ROOT / "incubator"
STRATEGY_SRC = ROOT / "src" / "fxbot" / "strategies"
# Strategy modules frozen with every candidate. base.py is not frozen: it defines the action
# types (Enter, ExitPosition) the engine and risk module understand.
FROZEN_MODULES = ("families.py", "ml_day.py")
DEFAULT_SYMBOLS = ("frxEURUSD", "frxGBPUSD", "frxUSDJPY")
DEFAULT_COST_TABLE = "research/phase2/cost_by_hour.json"
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_]{2,60}$")
IGNORED = {"__pycache__"}


class RegistryError(RuntimeError):
    """Registration refused or registry broken."""


class TamperedError(RegistryError):
    """A registered candidate's files or registry entry changed."""


# ----------------------------------------------------------------------------- hashing
def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: Path) -> str:
    return sha256_bytes(p.read_bytes())


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def fingerprint(manifest: dict) -> str:
    """SHA-256 of the manifest. The manifest lists the SHA-256 of every file."""
    return sha256_bytes(canonical(manifest))


def _entry_hash(entry: dict) -> str:
    return sha256_bytes(canonical({k: v for k, v in entry.items() if k != "entry_hash"}))


# ----------------------------------------------------------------------------- hash chains
def read_chain(path: Path) -> list[dict]:
    """Read and check an append-only hash chain (registry.json, exams.json)."""
    if not path.exists():
        return []
    entries = json.loads(path.read_text())
    prev = ""
    for i, e in enumerate(entries):
        if e.get("seq") != i or e.get("prev") != prev or e.get("entry_hash") != _entry_hash(e):
            raise TamperedError(f"{path.name}: entry {i} was edited, removed or reordered")
        prev = e["entry_hash"]
    return entries


def append_chain(path: Path, entry: dict) -> dict:
    entries = read_chain(path)
    e = {**entry, "seq": len(entries), "prev": entries[-1]["entry_hash"] if entries else ""}
    e["entry_hash"] = _entry_hash(e)
    entries.append(e)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(entries, indent=1) + "\n")
    tmp.replace(path)
    return e


# ----------------------------------------------------------------------------- candidates
@dataclass(frozen=True)
class Candidate:
    id: str
    dir: Path
    manifest: dict
    fingerprint: str
    seq: int

    @property
    def registered(self) -> dt.date:
        return dt.date.fromisoformat(self.manifest["registered"])

    @property
    def first_day(self) -> dt.date:
        """First day it is scored on: the day after registration."""
        return self.registered + dt.timedelta(days=1)

    @property
    def start_epoch(self) -> int:
        d = self.first_day
        return int(dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc).timestamp())

    @property
    def timeframe(self) -> str:
        return self.manifest["timeframe"]

    @property
    def warmup_days(self) -> int:
        return int(self.manifest["warmup_days"])

    @property
    def legs(self) -> dict | None:
        return self.manifest.get("legs")

    @property
    def symbols(self) -> tuple[str, ...]:
        """The pairs this candidate trades (the three majors unless the manifest says otherwise)."""
        return tuple(self.manifest.get("symbols") or DEFAULT_SYMBOLS)

    @property
    def cost_table(self) -> str:
        """Commission table (repo-relative path) its replays use."""
        return self.manifest.get("cost_table") or DEFAULT_COST_TABLE


def registry_path(root: Path = INCUBATOR) -> Path:
    return root / "registry.json"


def exams_path(root: Path = INCUBATOR) -> Path:
    return root / "exams.json"


def candidates(root: Path = INCUBATOR) -> list[Candidate]:
    """Every registered candidate, in registration order (checks the chain, not the files)."""
    out = []
    for e in read_chain(registry_path(root)):
        d = root / "candidates" / e["id"]
        mpath = d / "manifest.json"
        manifest = json.loads(mpath.read_text()) if mpath.exists() else {}
        out.append(Candidate(e["id"], d, manifest, e["fingerprint"], e["seq"]))
    return out


def verify(c: Candidate) -> None:
    """Raise TamperedError unless the candidate's files are exactly as registered."""
    mpath = c.dir / "manifest.json"
    if not mpath.exists():
        raise TamperedError(f"{c.id}: manifest.json is missing")
    manifest = json.loads(mpath.read_text())
    if fingerprint(manifest) != c.fingerprint:
        raise TamperedError(f"{c.id}: manifest.json changed (fingerprint mismatch)")
    files = manifest["files"]
    present = {p.relative_to(c.dir).as_posix() for p in c.dir.rglob("*")
               if p.is_file() and not IGNORED & set(p.relative_to(c.dir).parts)}
    present.discard("manifest.json")
    if present != set(files):
        extra, missing = sorted(present - set(files)), sorted(set(files) - present)
        raise TamperedError(f"{c.id}: files added {extra} or missing {missing}")
    for rel, digest in files.items():
        if sha256_file(c.dir / rel) != digest:
            raise TamperedError(f"{c.id}: {rel} changed (SHA-256 mismatch)")


def verify_all(root: Path = INCUBATOR) -> dict[str, str]:
    """{id: "ok" or the problem}. A broken registry chain raises."""
    out = {}
    for c in candidates(root):
        try:
            verify(c)
            out[c.id] = "ok"
        except TamperedError as err:
            out[c.id] = str(err)
    return out


# ----------------------------------------------------------------------------- loading
class _FrozenUnpickler(pickle.Unpickler):
    def __init__(self, f, package: str):
        super().__init__(f)
        self.package = package

    def find_class(self, module, name):
        if module.startswith("fxbot.strategies.") and module.rsplit(".", 1)[1] + ".py" in FROZEN_MODULES:
            module = f"{self.package}.{module.rsplit('.', 1)[1]}"
        return super().find_class(module, name)


class _PickleShim:
    """Stands in for the pickle module inside a frozen ml_day: saved models load against the
    candidate's frozen classes, not today's src/fxbot/strategies/."""

    def __init__(self, package: str):
        self.package = package

    def loads(self, data: bytes):
        return _FrozenUnpickler(io.BytesIO(data), self.package).load()

    def dumps(self, obj):
        raise RuntimeError("frozen candidates never save models")


def _package_name(c: Candidate) -> str:
    return f"_fxinc_{c.id}_{c.fingerprint[:12]}"


def _import_frozen(c: Candidate):
    pkg = _package_name(c)
    if pkg in sys.modules:
        return sys.modules[pkg]
    code = c.dir / "code"
    spec = importlib.util.spec_from_file_location(pkg, code / "__init__.py",
                                                  submodule_search_locations=[str(code)])
    mod = importlib.util.module_from_spec(spec)
    sys.modules[pkg] = mod
    spec.loader.exec_module(mod)
    for name in FROZEN_MODULES:
        sub = importlib.import_module(f"{pkg}.{name[:-3]}")
        if hasattr(sub, "pickle"):
            sub.pickle = _PickleShim(pkg)
    return mod


def load_strategy(c: Candidate, check: bool = True):
    """A fresh instance of the candidate's frozen strategy (verified first)."""
    if check:
        verify(c)
    _import_frozen(c)
    m = c.manifest
    mod = importlib.import_module(f"{_package_name(c)}.{m['module']}")
    cls = getattr(mod, m["class"])
    params = dict(m["params"])
    if params.get("model_file"):
        params["model_file"] = str(c.dir / params["model_file"])
    return cls(**params)


# ----------------------------------------------------------------------------- registration
def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


def _freeze_source(text: str) -> str:
    # The frozen modules import each other from the candidate's own copy.
    return re.sub(r"^from fxbot\.strategies\.(families|ml_day) import", r"from .\1 import", text, flags=re.M)


def register(cid: str, module: str, class_name: str, params: dict, model_files: list[Path] = (),
             notes: str = "", origin: dict | None = None, *, root: Path = INCUBATOR,
             now: dt.datetime | None = None, require_clean: bool = True,
             symbols=DEFAULT_SYMBOLS, cost_table: str = DEFAULT_COST_TABLE) -> Candidate:
    """Register a new candidate. Refuses an existing id, a date earlier than the last
    registration, unknown classes, unknown symbols, a commission table without every symbol,
    and (by default) uncommitted strategy code or models."""
    from fxbot import symbols as symbols_mod
    from fxbot.backtest.fills import CommissionTable
    symbols = symbols_mod.check(symbols)
    table_path = ROOT / cost_table
    if not table_path.exists():
        raise RegistryError(f"commission table {cost_table} does not exist")
    missing = [s for s in symbols if s not in CommissionTable(table_path).base]
    if missing:
        raise RegistryError(f"commission table {cost_table} has no base rate for {missing}")
    now = now or dt.datetime.now(dt.timezone.utc)
    registered = now.astimezone(dt.timezone.utc).date()
    if not ID_RE.match(cid):
        raise RegistryError(f"id {cid!r}: use 3-61 lowercase letters, digits and _")
    entries = read_chain(registry_path(root))
    if any(e["id"] == cid for e in entries) or (root / "candidates" / cid).exists():
        raise RegistryError(f"{cid} is already registered; registered candidates are never edited. "
                            "Register a changed idea under a new id.")
    if entries and registered < max(dt.date.fromisoformat(e["registered"]) for e in entries):
        raise RegistryError("registration date earlier than an existing registration (no backdating)")
    if module + ".py" not in FROZEN_MODULES:
        raise RegistryError(f"module must be one of {FROZEN_MODULES}")
    model_files = [Path(p) if Path(p).is_absolute() else ROOT / p for p in model_files]
    sources = [STRATEGY_SRC / n for n in FROZEN_MODULES]
    if require_clean:
        rel = [str(p.relative_to(ROOT)) for p in sources + model_files]
        if _git("status", "--porcelain", "--", *rel):
            raise RegistryError("commit the strategy code and model files before registering")
    try:
        commit = _git("rev-parse", "HEAD")
    except (subprocess.CalledProcessError, FileNotFoundError):
        commit = "unknown"

    final = root / "candidates" / cid
    tmp = root / "candidates" / f".{cid}.tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    (tmp / "code").mkdir(parents=True)
    (tmp / "code" / "__init__.py").write_text(f'"""Frozen strategy code of incubator candidate {cid}."""\n')
    source_sha = {}
    for src in sources:
        source_sha[src.name] = sha256_file(src)
        (tmp / "code" / src.name).write_text(_freeze_source(src.read_text()))
    params = dict(params)
    if model_files:
        (tmp / "models").mkdir()
        for mf in model_files:
            shutil.copy2(mf, tmp / "models" / mf.name)
        if "model_file" in params:
            params["model_file"] = f"models/{Path(params['model_file']).name}"
            if not (tmp / params["model_file"]).exists():
                raise RegistryError("params model_file must be one of model_files")
    files = {p.relative_to(tmp).as_posix(): sha256_file(p) for p in sorted(tmp.rglob("*")) if p.is_file()}

    try:
        # Instantiate from the frozen copy once, so a broken candidate is never registered.
        probe = Candidate(cid, tmp, {"module": module, "class": class_name, "params": params},
                          "probe" + sha256_bytes(canonical(files))[:8], -1)
        strat = load_strategy(probe, check=False)
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    manifest = {
        "id": cid,
        "registered": registered.isoformat(),
        "registered_at": now.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "first_scored_day": (registered + dt.timedelta(days=1)).isoformat(),
        "module": module,
        "class": class_name,
        "strategy_name": strat.name,
        "timeframe": strat.timeframe,
        "warmup_days": int(getattr(strat, "warmup_days", 120)),
        "legs": getattr(strat, "LEGS", None),
        "symbols": list(symbols),
        "cost_table": cost_table,
        "params": params,
        "source_commit": commit,
        "source_sha256": source_sha,
        "model_source": {mf.name: str(mf.relative_to(ROOT)) if mf.is_relative_to(ROOT) else mf.name
                         for mf in model_files},
        "origin": origin or {},
        "notes": notes,
        "files": files,
    }
    (tmp / "manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    fp = fingerprint(json.loads((tmp / "manifest.json").read_text()))
    tmp.rename(final)
    e = append_chain(registry_path(root), {"id": cid, "registered": manifest["registered"], "fingerprint": fp})
    c = Candidate(cid, final, manifest, fp, e["seq"])
    verify(c)
    return c
