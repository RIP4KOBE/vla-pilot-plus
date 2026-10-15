def require(condition, reason):
    if not condition:
        raise ValueError(reason)

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def canonical_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()

def read_ref(reference):
    require(isinstance(reference, dict) and set(reference) == {"path", "sha256"}, "invalid file reference")
    path = Path(reference["path"])
    require(path.is_absolute() and path.is_file() and not path.is_symlink()
            and sha(path) == reference["sha256"], "file reference hash/path differs")
    return json.loads(path.read_text())

def validate_context():
    return "new"
