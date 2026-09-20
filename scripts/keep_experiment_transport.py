#!/usr/bin/env python3
"""Finite local transport companion for one explicitly launched experiment.

Reuses healthy processes. Exits when this experiment completes or is stopped.
No cron, login item, scheduler, account changes, API keys, or payload logging.
"""
from __future__ import annotations

import argparse
import fcntl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import select
import shlex
import socket
import subprocess
import sys
import threading
import time

REPO = Path(__file__).resolve().parents[1]
ALLOWED = {"api.openai.com", "generativelanguage.googleapis.com"}
FORWARD = "127.0.0.1:17897:127.0.0.1:17896"


def connect_target(authority):
    host, separator, port = str(authority).rpartition(":")
    if not separator or host.lower() not in ALLOWED or port != "443":
        raise ValueError("only the two authorized API domains on TLS port 443 are allowed")
    return host.lower(), 443


class APIProxy(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # Do not log requests, headers, scene data, or credentials.

    def do_CONNECT(self):
        try:
            target = connect_target(self.path)
        except ValueError:
            self.send_error(403)
            return
        try:
            upstream = socket.create_connection(target, timeout=20)
        except OSError:
            self.send_error(502)
            return
        with upstream:
            self.send_response(200, "Connection established")
            self.end_headers()
            self.wfile.flush()
            # TLS remains end-to-end between the provider and experiment client.
            self.connection.settimeout(30)
            upstream.settimeout(30)
            try:
                while True:
                    readable, _, _ = select.select([self.connection, upstream], [], [], 900)
                    if not readable:
                        return
                    for stream in readable:
                        data = stream.recv(65536)
                        if not data:
                            return
                        (upstream if stream is self.connection else self.connection).sendall(data)
            except (OSError, ValueError):
                return


def listening(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=2):
            return True
    except OSError:
        return False


def matching_tunnel(host, endpoint):
    rows = subprocess.check_output(["ps", "-axo", "pid=,args="], text=True).splitlines()
    for row in rows:
        try:
            pid, command = row.strip().split(None, 1)
            parts = shlex.split(command)
            if Path(parts[0]).name == "ssh" and "-R" in parts and "-N" in parts:
                if parts[parts.index("-R") + 1] == FORWARD and parts[-1] in {host, endpoint}:
                    return int(pid)
        except (ValueError, IndexError):
            continue
    return None


def publish(path, value):
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("w") as stream:
        json.dump(value, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def launch(command, log_path):
    with log_path.open("ab") as log:
        child = subprocess.Popen(command, cwd=REPO, stdout=log, stderr=subprocess.STDOUT,
                                 start_new_session=True)
    threading.Thread(target=child.wait, daemon=True).start()
    return child.pid


def remote_probe(args):
    # Run a finite, read-mostly check over the existing SSH account. Restart only
    # the lightweight supervisor after exact process-identity/liveness checks.
    source = r'''
import json, pathlib, subprocess
root=pathlib.Path(ROOT)
out=pathlib.Path(OUTPUT)
repo=pathlib.Path(REPO_PATH)
path=out/"supervisor_status.json"
s=json.loads(path.read_text()) if path.is_file() else {}
stopped=(out/"stop.request").exists() or (out/"supervisor.stop.request").exists()
if stopped:
    s["state"]="STOPPED_BY_USER"
if s.get("state") not in {"COMPLETE","STOPPED_BY_USER"}:
    proc=pathlib.Path("/proc")/str(s.get("pid",-1))
    parts=(proc/"cmdline").read_bytes().split(b"\0") if (proc/"cmdline").is_file() else []
    alive=b"--supervise-existing" in parts and any(pathlib.Path(p.decode()).name=="run_full_experiment.py" for p in parts if p)
    if not alive:
        with (out/"supervisor.log").open("ab") as log:
            child=subprocess.Popen([PYTHON,"-u",str(repo/"scripts/run_full_experiment.py"),
                "--supervise-existing","--root",str(root),"--output",str(out)],cwd=repo,
                stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        s={"state":"SUPERVISOR_RECOVERING","pid":child.pid}
print(json.dumps({k:s.get(k) for k in ("state","pid","completed_contexts","planned_contexts","error")}))
'''
    values = {"ROOT": args.remote_root, "OUTPUT": args.remote_output,
              "REPO_PATH": args.remote_repo, "PYTHON": args.remote_python}
    prefix = "\n".join(f"{key}={value!r}" for key, value in values.items()) + "\n"
    remote = shlex.quote(args.remote_python) + " -c " + shlex.quote(prefix + source)
    result = subprocess.run(["ssh", "-T", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15",
                             "-o", "ServerAliveInterval=10", "-o", "ServerAliveCountMax=2",
                             args.host, remote], capture_output=True, text=True, timeout=50)
    if result.returncode:
        raise ConnectionError(f"SSH experiment check exited {result.returncode}")
    return json.loads(result.stdout)


def run(args):
    state = Path(args.state_dir).resolve()
    state.mkdir(parents=True, exist_ok=True)
    settings = subprocess.check_output(["ssh", "-G", args.host], text=True, stderr=subprocess.DEVNULL)
    endpoint = next(row.split(None, 1)[1] for row in settings.splitlines() if row.startswith("hostname "))
    with (state / "transport.lock").open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        while not (state / "stop.request").exists():
            actions = []
            try:
                if not listening(17896):
                    pid = launch([sys.executable, str(Path(__file__).resolve()), "--proxy-server"], state / "proxy.log")
                    actions.append({"restarted": "allowlisted_api_proxy", "pid": pid})
                tunnel = matching_tunnel(args.host, endpoint)
                if tunnel is None:
                    tunnel = launch(["/usr/bin/ssh", "-N", "-T", "-o", "BatchMode=yes",
                        "-o", "ExitOnForwardFailure=yes", "-o", "ServerAliveInterval=20",
                        "-o", "ServerAliveCountMax=3", "-o", "TCPKeepAlive=yes",
                        "-R", FORWARD, args.host], state / "tunnel.log")
                    actions.append({"restarted": "api_ssh_forward", "pid": tunnel})
                remote = remote_probe(args)
                result = {"state": "RUNNING", "remote": remote, "tunnel_pid": tunnel, "actions": actions}
                done = remote.get("state") in {"COMPLETE", "STOPPED_BY_USER"}
                if done:
                    result["state"] = remote["state"]
            except Exception as error:
                result = {"state": "TRANSPORT_RECONNECTING", "error": f"{type(error).__name__}: {error}",
                          "actions": actions}
                done = False
            publish(state / "status.json", {**result, "pid": os.getpid(), "updated_at": time.time(),
                    "finite_experiment": True, "scheduled_task": False, "authorized_domains": sorted(ALLOWED),
                    "remote_output": args.remote_output})
            if done:
                return  # Existing transport remains available; no broad cleanup.
            time.sleep(30)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proxy-server", action="store_true")
    parser.add_argument("--host", default="hgpu1")
    parser.add_argument("--remote-root", default="/shared/hengyil6/vls/self_improve")
    parser.add_argument("--remote-output", default="/shared/hengyil6/vls/self_improve/fixed_budget_50/formal_experiment")
    parser.add_argument("--remote-repo", default="/root/vla-pilot-plus")
    parser.add_argument("--remote-python", default="/shared/hengyil6/vls/envs/vla-pilot/bin/python")
    parser.add_argument("--state-dir", type=Path, default=REPO / "outputs/experiment_transport")
    options = parser.parse_args()
    if options.proxy_server:
        ThreadingHTTPServer(("127.0.0.1", 17896), APIProxy).serve_forever()
    else:
        run(options)
