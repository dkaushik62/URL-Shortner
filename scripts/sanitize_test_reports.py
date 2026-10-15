"""Remove machine identifiers from publishable JUnit XML, preserving test evidence."""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import tempfile
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]


def private_path_text(value: str, repository: Path, *, redact_other_paths: bool = True) -> str:
    # Match native, slash-normalized and repr-escaped paths, including spaces.
    roots = [
        (repository.resolve(), "[repository]"),
        (Path(tempfile.gettempdir()).resolve(), "[temporary]"),
        (Path.home().resolve(), "[user-home]"),
    ]
    for root, label in sorted(roots, key=lambda item: len(str(item[0])), reverse=True):
        parts = re.split(r"[\\/]+", str(root).rstrip("\\/"))
        pattern = r"[\\/]+".join(re.escape(part) for part in parts)
        value = re.sub(pattern + r"(?=[\\/\s:'\"<>)\]]|$)", lambda _: label, value,
                       flags=re.IGNORECASE if re.match(r"^[A-Za-z]:", str(root)) else 0)
    # Older reports may have been produced on a different machine/OS.
    value = re.sub(r"(?i)(?<![\w/\\])(?:[A-Z]:[\\/]+Users[\\/]+|/(?:Users|home)/)[^\\/\r\n<>\"']+",
                   "[user-home]", value)
    if redact_other_paths:
        value = re.sub(r"(?<![\w:/\\])(?:[A-Za-z]:[\\/]+|/(?:tmp|private/tmp|var/tmp)/)[^\s<>\"']+",
                       "[local-path]", value)
    return value


def sanitize_junit(path: Path, repository: Path = ROOT) -> bool:
    original = path.read_bytes()
    root = ET.fromstring(original)
    changed = False
    for node in root.iter():
        if "hostname" in node.attrib:
            del node.attrib["hostname"]
            changed = True
        for name, value in list(node.attrib.items()):
            # Preserve synthetic path parameters, but redact actual machine
            # roots/usernames even when they occur inside a test identifier.
            identity = name == "name" and node.tag in {"testcase", "testsuite"}
            cleaned = private_path_text(value, repository, redact_other_paths=not identity)
            if cleaned != value:
                node.attrib[name] = cleaned
                changed = True
        for field in ("text", "tail"):
            value = getattr(node, field)
            if value:
                cleaned = private_path_text(value, repository)
                if cleaned != value:
                    setattr(node, field, cleaned)
                    changed = True
    if changed:
        path.write_bytes(ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n")
    return changed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reports", nargs="+", type=Path)
    args = parser.parse_args()
    for path in args.reports:
        changed = sanitize_junit(path)
        print(f"{path.name}: {'sanitized' if changed else 'already clean'}")


if __name__ == "__main__":
    main()
