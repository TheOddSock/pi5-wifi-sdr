"""Compare a rebuilt module with public hashes of tested load-bearing sections.

Ignores debug paths and the build-id note; no module is installed or executed.
Requires pyelftools==0.33. This is binary comparison, not hardware validation.
"""
import argparse
import hashlib
import io
import json
import struct
from pathlib import Path
from elftools.common.exceptions import ELFError
from elftools.elf.elffile import ELFFile

ROOT = Path(__file__).resolve().parent


def compare(module, baseline):
    issues = []
    sections = {}
    compiler = []
    module_sha = None
    elf_identity = None
    elf_identity_validated = False
    try:
        # One immutable byte generation supplies both ELF checks and its identity.
        raw = module.read_bytes()
        module_sha = hashlib.sha256(raw).hexdigest()
        e = ELFFile(io.BytesIO(raw))
        elf_identity = {'class_bits': e.elfclass, 'little_endian': e.little_endian,
                        'machine': e['e_machine'], 'type': e['e_type']}
        if (e.elfclass != 64 or not e.little_endian or
                e['e_machine'] != 'EM_AARCH64' or e['e_type'] != 'ET_REL'):
            raise ValueError('Required ELF64 little-endian EM_AARCH64 ET_REL module')
        elf_identity_validated = True
        sections = {
            s.name: {'bytes': s['sh_size'], 'sha256': hashlib.sha256(s.data()).hexdigest()}
            for s in e.iter_sections()
            if (s['sh_flags'] & 2 or (s['sh_type'] in ['SHT_RELA', 'SHT_REL'] and
                                    e.get_section(s['sh_info'])['sh_flags'] & 2))
            and s.name not in ['.note.gnu.build-id', '.modinfo']
        }
        if sections != baseline['allocated_and_relocation_sections']:
            issues.append('Load-bearing sections or relocations differ')
        modinfo = e.get_section_by_name('.modinfo')
        if modinfo is None:
            raise ValueError('Missing .modinfo section')
        info = modinfo.data().decode().split('\0')
        for key in ['vermagic', 'srcversion', 'license']:
            if key + '=' + baseline[key] not in info:
                issues.append(key + ' differs')
        fingerprint = bytes.fromhex(baseline['native_contract_fingerprint_hex'])
        if not any(fingerprint in s.data() for s in e.iter_sections() if s['sh_flags'] & 2):
            issues.append('Native contract fingerprint absent')
        comment = e.get_section_by_name('.comment')
        compiler = sorted(set(x for x in comment.data().decode().split('\0') if x)) if comment else []
    except (OSError, ELFError, ValueError, TypeError, KeyError, IndexError, struct.error) as error:
        issues.append('Invalid or unreadable module: ' + str(error))
    return {
        'status': 'pass' if not issues else 'different_build_review_required',
        'issues': issues,
        'module_sha256': module_sha,
        'elf_identity': elf_identity,
        'elf_identity_validated': elf_identity_validated,
        'exact_historical_module_SHA_match': module_sha == baseline['module_sha256'],
        'allocated_sections_and_relocations_checked': len(sections),
        'compiler_comments': compiler,
        'debug_paths_and_build_id_ignored': True,
        'hardware_validation': False,
        'installation_performed': False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('module', type=Path)
    args = parser.parse_args()
    baseline = json.loads((ROOT / 'tested-module-sections.json').read_text())
    result = compare(args.module, baseline)
    print(json.dumps(result, indent=2))
    raise SystemExit(result['status'] != 'pass')


if __name__ == '__main__':
    main()
