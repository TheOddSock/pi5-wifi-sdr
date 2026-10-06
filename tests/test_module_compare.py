"""Small malformed/incorrect-architecture ELF refusals; no module is loaded.

These tests require the source comparator's optional pyelftools dependency.
"""
import importlib.util
import struct
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("public_module_compare", ROOT / "src/device/driver/compare_module.py")
module = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(module)
except ModuleNotFoundError as error:
    if error.name == "elftools" or error.name.startswith("elftools."):
        raise unittest.SkipTest("source module comparison requires pyelftools==0.33")
    raise


def ELF_header(elfclass=64, little=True, machine=183, kind=1):
    ident = b"\x7fELF" + bytes([2 if elfclass == 64 else 1, 1 if little else 2, 1, 0]) + b"\0" * 8
    order = "<" if little else ">"
    if elfclass == 64:
        return struct.pack(order + "16sHHIQQQIHHHHHH", ident, kind, machine, 1,
                           0, 0, 0, 0, 64, 0, 0, 64, 0, 0)
    return struct.pack(order + "16sHHIIIIIHHHHHH", ident, kind, machine, 1,
                       0, 0, 0, 0, 52, 0, 0, 40, 0, 0)


class MemoryModule:
    def __init__(self, data):
        self.data = data

    def read_bytes(self):
        return self.data


class ModuleCompareTests(unittest.TestCase):
    baseline = {"allocated_and_relocation_sections": {}, "module_sha256": "0" * 64}

    def test_incompatible_ELF_header_refused_before_section_comparison(self):
        for change in ({"machine": 62}, {"kind": 2}, {"elfclass": 32}, {"little": False}):
            with self.subTest(change=change):
                result = module.compare(MemoryModule(ELF_header(**change)), self.baseline)
                self.assertNotEqual(result["status"], "pass")
                self.assertEqual(result["allocated_sections_and_relocations_checked"], 0)
                self.assertTrue(any("ELF64 little-endian EM_AARCH64 ET_REL" in x for x in result["issues"]))

    def test_malformed_ELF_has_a_graceful_failure_result(self):
        for raw in (b"not ELF", ELF_header()[:31], ELF_header()):
            with self.subTest(length=len(raw)):
                result = module.compare(MemoryModule(raw), self.baseline)
                self.assertNotEqual(result["status"], "pass")
                self.assertTrue(any("Invalid or unreadable module" in x for x in result["issues"]))


if __name__ == "__main__":
    unittest.main()
