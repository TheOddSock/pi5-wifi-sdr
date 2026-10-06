"""Build isolated 16/32-slot sparse firmware and ELF-derived driver contract.

This is offline preparation, not heap/stack admission or deployment. Each new
geometry has a new ABI and fingerprint. Historical eight-slot files stay intact.
"""
from pathlib import Path
import argparse, hashlib, io, json, re, struct, subprocess, sys, zlib
ROOT=Path(__file__).resolve().parent
import types
import capstone
from elftools.elf.elffile import ELFFile
def tool(n):
    p=native.BIN/n
    return p if p.exists() else native.BIN/(n+'.exe')
native=types.SimpleNamespace(HEAP_LITERAL=0x1EEF68,CRC_ADDRESS=0x213BA8)
def checked(path,expected):
    b=Path(path).read_bytes()
    if hashlib.sha256(b).hexdigest()!=expected:raise ValueError('Base image identity differs')
    return b
native.checked=checked
native.IMAGE_SHA='a8793f02aed5730fc8020e93e49911e6183458497e0b26be633a2e35d337ab8a'
def thumb_bl(site,target):
    d=target-(site+4)
    if site&1 or target&1 or d&1 or not -(1<<24)<=d<(1<<24):raise ValueError('Thumb BL placement')
    v=d&((1<<25)-1);s=v>>24&1;j1=1^((v>>23&1)^s);j2=1^((v>>22&1)^s)
    return struct.pack('<HH',0xf000|s<<10|(v>>12&0x3ff),0xd000|j1<<13|j2<<11|(v>>1&0x7ff))
native.thumb_bl=thumb_bl
SOURCE=ROOT/'source'
OUT=ROOT/'output'
BASE=0x198000;APPEND=0x213cb0
HOOKS=[(0x1d2d12,'fff7b6ff','progress_api_entry'),
       (0x1cf982,'a3f82e2b','progress_arm_entry'),
       (0x1cf988,'38f6c8ff','ring_delay_entry'),
       (0x1d2d76,'0b2e24d9','ring_export_entry')]
def sha(b):return hashlib.sha256(b).hexdigest()
def contract_header_bytes(header):
    """Emit the recorded ASCII/CRLF contract independently of the host OS."""
    return header.replace('\r\n','\n').replace('\n','\r\n').encode('ascii')

def bind(p):return dict(path=p.absolute().as_posix(),sha256=sha(p.read_bytes()))
def symbols(elf):return {s.name:int(s['st_value']) for s in elf.get_section_by_name('.symtab').iter_symbols() if s.name}
def spans(elf,section):
    a,z=section['sh_addr'],section['sh_addr']+section['sh_size']
    m=sorted({(s['st_value'],s.name[:2]) for s in elf.get_section_by_name('.symtab').iter_symbols()
              if s.name.startswith(('$t','$d')) and a<=s['st_value']<z})
    assert m and m[0][0]==a;m.append((z,'$d'))
    return [(x,y) for (x,k),(y,_) in zip(m,m[1:]) if k=='$t']

def main():
    p=argparse.ArgumentParser(description='Offline BCM43455c0 ABI36 append build; no hardware/deployment')
    p.add_argument('--image',type=Path,required=True);p.add_argument('--toolchain-bin',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);a=p.parse_args();slots=32;version=36
    out=a.out.resolve()
    if out.exists():raise ValueError('Preserve old output; supply a fresh directory')
    native.BIN=a.toolchain_bin.resolve();native.IMAGE=a.image.resolve()
    original=checked(native.IMAGE,native.IMAGE_SHA)
    if len(original)!=507048:raise ValueError('Base image length')
    out.mkdir(parents=True);commands=[]
    def run(argv):
        argv=[str(x) for x in argv];r=subprocess.run(argv,cwd=ROOT,capture_output=True,text=True,timeout=60)
        commands.append(dict(argv=argv,returncode=r.returncode,stdout=r.stdout,stderr=r.stderr))
        assert not r.returncode,r.stdout+r.stderr;return r.stdout
    gcc=tool('arm-none-eabi-gcc')
    flags=['-mcpu=cortex-r4','-mthumb','-mfloat-abi=soft','-std=c11','-Os','-g3','-Wall','-Wextra','-Werror',
           '-ffreestanding','-fno-builtin','-fno-common','-fno-stack-protector','-fno-unwind-tables',
           '-fno-asynchronous-unwind-tables','-fstack-usage','-ffunction-sections','-fdata-sections',f'-DRING_SLOTS={slots}']
    objects=[]
    for name,stem in [('core/hooks.S','core-hooks'),('core/speed.S','core-speed'),('core/target.c','core-target'),
                      ('average.S','average'),('phase_hooks.S','phase-hooks'),('phase.c','phase')]:
        obj=out/(stem+'.o');objects.append(obj)
        run([gcc,*flags,'-c',(SOURCE/name).absolute(),'-o',obj.absolute()])
    elfpath=out/'sparse-ring.elf'
    run([gcc,'-mcpu=cortex-r4','-mthumb','-mfloat-abi=soft','-nostdlib',
         '-Wl,-T,'+str((SOURCE/'patch.ld').absolute()),
         '-Wl,-Map,'+str((out/'sparse-ring.map').absolute()),'-Wl,--emit-relocs','-Wl,--gc-sections',
         *[o.absolute() for o in objects],'-o',elfpath.absolute()])
    elf=ELFFile(io.BytesIO(elfpath.read_bytes()));syms=symbols(elf);end=syms['__progress_end']
    run([tool('arm-none-eabi-objcopy'),'-O','binary',elfpath.absolute(),(out/'sparse-ring-append.bin').absolute()])
    append=(out/'sparse-ring-append.bin').read_bytes();assert end%8==0 and end<0x260000
    assert len(append)<=end-APPEND
    image=bytearray(original)+bytes(APPEND-BASE-len(original))+append
    image+=bytes(end-BASE-len(image));patches=[];allowed={}
    cs=capstone.Cs(capstone.CS_ARCH_ARM,capstone.CS_MODE_THUMB);cs.detail=True
    for address,old,name in HOOKS:
        assert original[address-BASE:address-BASE+4]==bytes.fromhex(old)
        patch=native.thumb_bl(address,syms[name]&~1);ins=next(cs.disasm(patch,address))
        assert ins.mnemonic=='bl' and ins.operands[0].imm==(syms[name]&~1)
        allowed[address]=patch;patches.append(dict(address=address,original_hex=old,new_hex=patch.hex(),symbol=name,target=syms[name]&~1))
    allowed[native.HEAP_LITERAL]=struct.pack('<I',end)
    for address,body in allowed.items():image[address-BASE:address-BASE+4]=body
    allowed[native.CRC_ADDRESS]=struct.pack('<I',zlib.crc32(image[:native.CRC_ADDRESS-BASE]))
    image[native.CRC_ADDRESS-BASE:native.CRC_ADDRESS-BASE+4]=allowed[native.CRC_ADDRESS]
    permit={address-BASE+i for address in allowed for i in range(4)}
    assert len(image)==end-BASE and all(x==y or i in permit for i,(x,y) in enumerate(zip(original,image)))
    assert struct.unpack_from('<I',image,native.HEAP_LITERAL-BASE)[0]==end
    code=[];ranges=[]
    for section_name in ['.text','.sparse_text']:
        sec=elf.get_section_by_name(section_name);assert sec is not None
        for lo,hi in spans(elf,sec):
            ins=list(cs.disasm(image[lo-BASE:hi-BASE],lo));assert sum(i.size for i in ins)==hi-lo
            code.extend(ins);ranges.append((lo,hi))
    dis=run([tool('arm-none-eabi-objdump'),'-d','-z',elfpath.absolute()])
    (out/'sparse-ring-disassembly.txt').write_text(dis)
    gb=[]
    for line in dis.splitlines():
        m=re.match(r'\s*([0-9a-f]+):\s*((?:[0-9a-f]{4}(?:\s+|$)){1,2})',line)
        if m and any(lo<=int(m[1],16)<hi for lo,hi in ranges):gb.append((int(m[1],16),2*len(m[2].split())))
    assert sorted(gb)==sorted((i.address,i.size) for i in code)
    def function(name):
        s=next(s for s in elf.get_section_by_name('.symtab').iter_symbols() if s.name==name)
        lo=s['st_value']&~1;return [i for i in code if lo<=i.address<lo+s['st_size']]
    for name in ['sparse_read','sparse_read_fnv']:
        f=function(name);assert sum(i.mnemonic=='shadd16' for i in f)==5
        assert sum(i.mnemonic.startswith('ldr') and len(i.operands)>1 and i.operands[1].type==capstone.arm.ARM_OP_MEM and i.operands[1].mem.disp==0x134 for i in f)==6
        assert sum(i.mnemonic.startswith('str') and len(i.operands)>1 and i.operands[1].type==capstone.arm.ARM_OP_MEM and i.operands[1].mem.disp==0x130 for i in f)==2
        assert not any(i.mnemonic in ['bl','blx'] for i in f)
    live=function('sparse_read_fnv');pure=function('sparse_read')
    assert sum(i.mnemonic.startswith('eor') for i in live)==sum(i.mnemonic.startswith('mul') for i in live)==1
    assert not any(i.mnemonic.startswith(('eor','mul')) for i in pure)
    consume=function('consume');assert sum(i.mnemonic=='bl' and i.operands[0].imm==(syms['sparse_read_fnv']&~1) for i in consume)==1
    assert not any(i.mnemonic=='bl' and i.operands[0].imm==(syms['sparse_read']&~1) for i in consume)
    assert 'block_hash' not in syms and 'selected_read' not in syms
    assert sum(i.mnemonic=='bl' and i.operands[0].imm==(syms['sparse_read']&~1) for i in code)==1
    assert sum(i.mnemonic=='bl' and i.operands[0].imm==(syms['sparse_delay']&~1) for i in code)==1
    assert sum(i.mnemonic=='bl' and i.operands[0].imm==(syms['sparse_rate_matches']&~1) for i in code)==1
    section_sizes={n:elf.get_section_by_name(n)['sh_size'] for n in ['.progress_workspace','.reader_workspace','.sparse_phase_workspace']}
    record_bytes=640+4128*slots
    assert section_sizes=={'.progress_workspace':7064,'.reader_workspace':record_bytes+192,'.sparse_phase_workspace':72}
    for n in section_sizes:
        s=elf.get_section_by_name(n);assert not any(s.data())
        assert image[s['sh_addr']-BASE:s['sh_addr']-BASE+s['sh_size']]==s.data()
    symtab=elf.get_section_by_name('.symtab')
    def sizeof(n):return next(s['st_size'] for s in symtab.iter_symbols() if s.name==n)
    assert sizeof('samples')==record_bytes and sizeof('work')==7064
    assert all(sizeof(n)==64 for n in ['context','lease','deadman'])
    sample_base=syms['samples'];sample_end=sample_base+record_bytes;append_start=syms['__sparse_append_start']
    assert sample_base+128+slots*4128+512==sample_end and sample_end<=append_start
    assert sorted((syms[n],syms[n]+sizeof(n)) for n in ['context','lease','deadman','samples'])[0][0]==elf.get_section_by_name('.reader_workspace')['sh_addr']
    fingerprint=bytes(image[APPEND-BASE:APPEND-BASE+32]);target=out/'sparse-ring.bin';target.write_bytes(image)
    addresses={n:syms[n] for n in ['work','context','lease','deadman','samples','state']}
    contract=dict(status='offline_ELF_bound_sparse_ring_geometry_matching_driver_contract_memory_unadmitted',
        slots=slots,abi_version=version,sample_magic=0x5354524d,record_bytes=record_bytes,frame_bytes=4176,
        slot_bytes=4128,slot_words=1024,slot_metadata_bytes=32,reference_words=128,
        text_address=APPEND,fingerprint_hex=fingerprint.hex(),fingerprint_sha256=sha(fingerprint),
        image_sha256=sha(image),image_bytes=len(image),reserved_end=end,addresses=addresses,
        slots_address=sample_base+128,reference_address=sample_base+128+slots*4128,
        phase=dict(magic=0x53504831,version=1,bytes=64,reply_offset=7680),
        sample_header_bytes=128,reply_bytes=8192,reply_offsets=dict(progress=256,context=7360,watchdog=7424,sample_header=7488,lease=7616,phase=7680),
        lifetime_sequence_wrap_excluded=True,publisher_modulo=slots,reader_overrun_lag_maximum=slots,
        raw_completion_margin=64,raw_stride=16,filter_offsets=[0,1,2,8,9,10],active_batch_cap=128,full_iteration_ticks_maximum=32768,
        native_pair_baseline=0x19e26666,native_pair_requested=0x1ad39999,
        memory_admitted=False,actual_geometry_receipt=None,existing8slot_driver_reuse=False,
        unchanged_driver_guards=['one owner','idle work before lease','full32 text fingerprint','one payload metadata bracket','publisher FNV','sequence monotonic','STOP readback','lease token ordering','128 pure stopped-tail equality'])
    (out/'driver-contract.json').write_text(json.dumps(contract,indent=2)+'\n')
    defines={'PI5_LEASE':syms['lease'],'PI5_STREAM_SLOTS':sample_base+128,
        'PI5_STREAM_REFERENCE':contract['reference_address'],'PI5_OWNED_TEXT':APPEND,'PI5_OWNED_WORK':syms['work'],
        'PI5_OWNED_RECORD':sample_base,'PI5_OWNED_WORDS':sample_base+160,'PI5_OWNED_LEASE':syms['lease'],
        'PI5_STREAM_ABI_VERSION':version,'PI5_STREAM_RECORD_BYTES':record_bytes,'PI5_STREAM_SLOT_COUNT':slots}
    header='/* Generated from actual ELF; offline, not memory admission. */\n'+''.join(f'#define {k} 0x{v:x}u\n' for k,v in defines.items())
    header+='static const u8 pi5_owned_fingerprint[32]={'+','.join(f'0x{x:02x}' for x in fingerprint)+'};\n'
    (out/'pi5_owned_contract.h').write_bytes(contract_header_bytes(header))
    expected='b4b1196c961533ac42b9604c945f3932097dfba80347857e431c03a5c6759f20'
    report={'status':'exact_tested_image_rebuilt' if sha(image)==expected else 'different_toolchain_image_review_required',
            'image_sha256':sha(image),'expected_tested_image_sha256':expected,'image_bytes':len(image),
            'compiler':run([gcc,'--version']).splitlines()[0],'GNU_Capstone_boundaries':len(code),
            'record_bytes':record_bytes,'slots':slots,'ABI':version,'ROM_blob_required':False,
            'hardware_access':False,'installation_performed':False}
    (out/'build-receipt.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    if sha(image)!=expected:raise SystemExit(2)
if __name__=='__main__':main()
