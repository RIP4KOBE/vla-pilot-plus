import sys, os, json, datetime, traceback
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3] / "study_worktree"
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]
os.chdir(ROOT)
from scripts import qd_ed_n32_runner as n
D = Path(__file__).resolve().parent
V = json.loads((D.parent / "root-recovery-release-v2/pre-adoption-validation-v1.json").read_text())
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
identity = n.process_identity(os.getpid())
n.w.atomic_json(D / "controller-start-v1.json", {"at": now(), "identity": identity, "plan": V["plan"], "release": V["release"], "source": V["source"], "status": "RUNNING_RELEASE_REVALIDATION"})
try:
    result = n.launch(V["plan"], V["release"])
    n.w.atomic_json(D / "controller-result-v1.json", {"at": now(), "identity": identity, "result": result})
except BaseException as exc:
    n.w.atomic_json(D / "controller-error-v1.json", {"at": now(), "identity": identity, "error_type": type(exc).__name__, "error": str(exc), "traceback": traceback.format_exc(), "recovery": "Reconcile journal and process identities before any action. Never automatically retry."})
    raise
