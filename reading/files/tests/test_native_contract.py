"""Exercise the actual pure contract emitter without compiler/build imports."""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class NativeContractTests(unittest.TestCase):
    def test_production_emitter_matches_pinned_contract_for_LF_and_CRLF(self):
        builder = ROOT / "src/device/native/build.py"
        tree = ast.parse(builder.read_bytes(), filename=str(builder))
        helper = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                      and node.name == "contract_header_bytes")
        # Execute the production function itself, without importing Capstone or
        # pyelftools and without invoking the native build's main().
        namespace = {}
        module = ast.Module(body=[helper], type_ignores=[])
        exec(compile(module, str(builder), "exec"), namespace)
        emit = namespace["contract_header_bytes"]
        pinned = (ROOT / "src/device/driver/additions/brcmfmac/pi5_owned_contract.h").read_bytes()
        self.assertEqual(pinned.count(b"\r\n"), 13)
        for text in (pinned.decode("ascii"), pinned.decode("ascii").replace("\r\n", "\n")):
            with self.subTest(newline="CRLF" if "\r\n" in text else "LF"):
                self.assertEqual(emit(text), pinned)
        # Guard the integration point as well: a dead helper must not conceal a
        # regression back to platform-default text output in the build path.
        writes = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Attribute)
                  and isinstance(node.func.value, ast.BinOp)
                  and isinstance(node.func.value.right, ast.Constant)
                  and node.func.value.right.value == "pi5_owned_contract.h"]
        self.assertEqual(len(writes), 1)
        self.assertEqual(writes[0].func.attr, "write_bytes")
        self.assertEqual(ast.dump(writes[0].args[0]),
                         ast.dump(ast.parse("contract_header_bytes(header)", mode="eval").body))


if __name__ == "__main__":
    unittest.main()
