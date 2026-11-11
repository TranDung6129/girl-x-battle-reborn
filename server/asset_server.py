"""Serve preserved lazy assets using the client's basename.MD5 convention."""
import hashlib
import re
from pathlib import Path


class AssetIndex:
    def __init__(self, root: Path):
        self.root = root.resolve(strict=True)
        if not self.root.is_dir():
            raise ValueError('asset root must be an extracted res/web directory')
        self.by_name = {}
        self.digests = {}
        for path in self.root.rglob('*'):
            if path.is_file() and path.resolve().is_relative_to(self.root):
                self.by_name.setdefault(path.name, []).append(path)

    def find(self, request_name: str) -> Path | None:
        match = re.fullmatch(r'([^/\\]+)\.([0-9a-f]{32})', request_name)
        if not match:
            return None
        name, expected = match.groups()
        for path in self.by_name.get(name, []):
            # Check again before serving in case an operator replaced a file
            # or changed it to a symlink after startup.
            resolved = path.resolve()
            if not resolved.is_relative_to(self.root) or not resolved.is_file():
                continue
            stat = resolved.stat()
            key = (str(resolved), stat.st_mtime_ns, stat.st_size)
            digest = self.digests.get(key)
            if digest is None:
                with resolved.open('rb') as stream:
                    hasher = hashlib.md5()
                    for block in iter(lambda: stream.read(1024 * 1024), b''):
                        hasher.update(block)
                    digest = hasher.hexdigest()
                self.digests[key] = digest
            if digest == expected:
                return resolved
        return None
