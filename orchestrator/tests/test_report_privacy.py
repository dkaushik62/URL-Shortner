from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

import pytest

from scripts.sanitize_test_reports import private_path_text, sanitize_junit


ROOT = Path(__file__).resolve().parents[2]


def test_report_redacts_identifiers_without_changing_test_evidence(tmp_path):
    report = tmp_path / "junit.xml"
    root = ET.Element("testsuites")
    suite = ET.SubElement(root, "testsuite", tests="3", failures="1", errors="0",
                          skipped="1", time="0.125", timestamp="2026-10-15T00:00:00",
                          hostname="private-test-host")
    case = ET.SubElement(suite, "testcase", name=r"test_behavior[C:\outside.txt]", classname="tests.example", time="0.1")
    failure = ET.SubElement(case, "failure", message="AssertionError: expected 410, got 200")
    failure.text = str(ROOT / "orchestrator/tests/example.py") + ":12: expected 410, got 200"
    skipped = ET.SubElement(case, "skipped", message=r"Access denied: 'C:\Users\Jane Doe\Temp\fixture'")
    skipped.text = r"D:\old-checkout\tests\example.py:17: Symlink permission unavailable"
    report.write_bytes(ET.tostring(root))

    assert sanitize_junit(report)
    cleaned = ET.parse(report).getroot()
    assert cleaned.find("testsuite").attrib == {key: value for key, value in suite.attrib.items() if key != "hostname"}
    assert cleaned.find(".//testcase").attrib == case.attrib
    assert cleaned.find(".//failure").attrib == failure.attrib
    text = report.read_text()
    for private in ("private-test-host", "Jane Doe", str(ROOT), "D:\\old-checkout"):
        assert private not in text
    assert "expected 410, got 200" in text
    assert "Symlink permission unavailable" in text
    before = report.read_bytes()
    assert not sanitize_junit(report)
    assert report.read_bytes() == before


@pytest.mark.parametrize("value", [
    r"C:\Users\Jane Doe\AppData\Temp\test.py:7: skipped",
    r"C:\\Users\\Jane Doe\\AppData\\Temp\\test.py:7: skipped",
    "/Users/private-person/tmp/test.py:7: skipped",
    "/home/private-person/tmp/test.py:7: skipped",
])
def test_report_redacts_foreign_user_paths(value):
    cleaned = private_path_text(value, ROOT)
    assert "Jane Doe" not in cleaned
    assert "private-person" not in cleaned
    assert "skipped" in cleaned


def test_invalid_xml_is_not_overwritten(tmp_path):
    report = tmp_path / "broken.xml"
    original = b"<testsuites><incomplete"
    report.write_bytes(original)
    with pytest.raises(ET.ParseError):
        sanitize_junit(report)
    assert report.read_bytes() == original


def test_real_local_paths_are_redacted_inside_test_parameters(tmp_path):
    report = tmp_path / "parameters.xml"
    root = ET.Element("testsuite", tests="1")
    ET.SubElement(root, "testcase", name="test_file[" + str(ROOT / "fixture.txt") + "]")
    report.write_bytes(ET.tostring(root))
    assert sanitize_junit(report)
    assert str(ROOT) not in report.read_text()
    assert "test_file[" in ET.parse(report).getroot().find("testcase").attrib["name"]


def test_pytest_sanitizes_failed_and_skipped_reports_automatically(tmp_path):
    (tmp_path / "conftest.py").write_text(
        "import sys\nsys.path.insert(0, " + repr(str(ROOT)) + ")\n"
        "from orchestrator.tests.conftest import pytest_sessionfinish\n", encoding="utf-8")
    (tmp_path / "test_fixture.py").write_text(
        "import pytest\n"
        "def test_failure():\n    assert 410 == 200, 'expected status regression'\n"
        "def test_skip():\n    pytest.skip('fixture skip reason')\n", encoding="utf-8")
    report = tmp_path / "junit.xml"
    process = subprocess.run([sys.executable, "-m", "pytest", "-q", "--junitxml", str(report), str(tmp_path)],
                             cwd=tmp_path, capture_output=True, text=True, timeout=60)
    assert process.returncode == 1, process.stdout + process.stderr
    suite = ET.parse(report).getroot().find("testsuite")
    assert suite.attrib["tests"] == "2"
    assert suite.attrib["failures"] == "1"
    assert suite.attrib["skipped"] == "1"
    assert "hostname" not in suite.attrib
    text = report.read_text()
    assert str(tmp_path) not in text
    assert "expected status regression" in text
    assert "fixture skip reason" in text
