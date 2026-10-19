"""Frozen map relocation build/readback batches; no database or runtime.

All positive cases rebuild a fresh 16MiB ROM from the same 6MiB base and empty
fixture allocation ledger. This is not a release build or computed-user proof.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from tools.rom_small_cfg_callback_gaps_independent_verifier import read_regular, sha
from tools.fixed_resource_roundtrip import _managed_run, _write, _fixture_inputs
from tools.resource_relocation_build_cli import build_cli as relocation_build_cli
from tools.audit_map_resource_fixed_roundtrip import linked_domain
from tools import verify_map_resource_relocation_audit as relocation
from tools import verify_map_resource_writeback_audit as codec

CONTRACT='tools/data/map-resource-relocation-roundtrip-contract-v1.json'
CONTRACT_SHA='ce9f3b7902991a9ac12a28961e438dee563762a18a799cb6f1fab4c81fdcb991'
SCRIPT='tools/audit_map_resource_relocation_roundtrip.py'
SCHEMA='map-resource-relocation-roundtrip-verification-v1'
CATALOG='artifacts/map-canvases-v1/manifest.json'
LAYOUT='sequel/rom-layout.json'
REGISTRY='sequel/image-resource-regions.json'
START,END,TARGET_SIZE=0x980000,0xA80000,0x1000000
TOOLCHAIN=('tools/build_mod.py','tools/import_map_resource_relocations.py','tools/import_map_resources.py',
           'tools/patch_safety.py','tools/rom_layout.py','tools/image_resource_regions.py',
           'tools/extract_tileset.py','tools/gba_image_export.py')


def _inputs(root):
    raw=read_regular(root/CONTRACT)
    if sha(raw)!=CONTRACT_SHA:raise ValueError('relocation contract identity mismatch')
    contract=json.loads(raw)
    if contract['schema']!='map-resource-relocation-roundtrip-inputs-v1':raise ValueError('contract schema mismatch')
    inputs={n:read_regular(root/n) for n in contract['inputs']}
    for n,b in inputs.items():
        if sha(b)!=contract['inputs'][n]:raise ValueError(f'relocation input identity mismatch: {n}')
    return contract,inputs


def _build_cli(fixture,name,specs,*,with_layout=True):
    return relocation_build_cli(fixture,name,specs,patch_type='map_resource_relocation',
                                layout_path=LAYOUT if with_layout else None)


def _identity(row):return row['resource_type']+':'+row['source_sha256']


def _edit(row,source=None):
    value={'id':_identity(row).replace(':','-'),'resource_type':row['resource_type'],
           'source_sha256':row['source_sha256'],'expected_physical_offsets':row['physical_offsets'],
           'expected_header_pointer_offsets':[a['header_pointer_offset'] for a in row['logical_aliases']]}
    if source is not None:value['content_file']=source
    return value


def _spec(inputs,edits):
    return {'schema':'map-resource-relocation-v1','base_rom_sha256':sha(inputs['rom/base.gba']),
            'source_catalog':CATALOG,'source_catalog_sha256':sha(inputs[CATALOG]),
            'partition':'sequel-image-assets','owner':'sequel_image_assets',
            'region_registry':REGISTRY,'region_registry_sha256':sha(inputs[REGISTRY]),
            'region':'map-resources','region_owner':'map_resources','edits':edits}


def _geometry(inputs):
    layout=json.loads(inputs[LAYOUT]);registry=json.loads(inputs[REGISTRY])
    parent=next(p for p in layout['partitions'] if p['id']=='sequel-image-assets')
    region=next(r for r in registry['regions'] if r['id']=='map-resources')
    if (int(layout['target_rom_size'],0)!=TARGET_SIZE or int(layout['fill_byte'],0)!=255
            or parent['owner']!='sequel_image_assets' or parent['origin']!='expanded_ff'
            or (int(parent['start'],0),int(parent['end'],0))!=(0x800000,0xC00000)
            or registry['parent_partition']!=parent['id'] or registry['parent_owner']!=parent['owner']
            or region['owner']!='map_resources' or region['alignment']!=4
            or (int(region['start'],0),int(region['end'],0))!=(START,END)):
        raise ValueError('frozen relocation ownership/geometry mismatch')


def _readback(case,name,base,resources,replacements):
    actual=read_regular(case/'output.gba');report=json.loads(read_regular(case/'build-report.json'))
    expected=bytearray(base+b'\xff'*(TARGET_SIZE-len(base)))
    cursor=START;ledger=[];allocations={};expected_patches={}
    for key,row in resources.items():
        if key not in replacements:continue
        content=replacements[key];encoded=codec._encode(content)
        if codec._decompress(encoded,0)!=content:raise ValueError('independent relocation codec failed')
        cursor=(cursor+3)&~3;end=cursor+len(encoded)
        if end>END:raise ValueError('independent accepted relocation exceeds region')
        expected[cursor:end]=encoded;allocations[key]=cursor
        common={'resource_type':key[0],'source_sha256':key[1],'replacement_sha256':sha(content),
                'new_pointer':f'0x{0x08000000+cursor:08X}'}
        expected_patches[cursor]={**common,'length':len(encoded),'patch_class':'allocation',
                                  'asset_type':'map_resource_relocation',
                                  'allocation_partition':'sequel-image-assets','allocation_owner':'sequel_image_assets',
                                  'allocation_region':'map-resources','allocation_region_owner':'map_resources',
                                  'before_hex':(b'\xff'*len(encoded)).hex(),'after_hex':encoded.hex()}
        headers=[]
        for alias in row['logical_aliases']:
            offset=alias['header_pointer_offset'];headers.append(offset)
            pointer=(0x08000000+cursor).to_bytes(4,'little');expected[offset:offset+4]=pointer
            expected_patches[offset]={**common,'length':4,'patch_class':'game_effective',
                                      'asset_type':'map_resource_relocation_pointer','map_id':alias['map_id'],
                                      'before_hex':base[offset:offset+4].hex(),'after_hex':pointer.hex()}
        ledger.append({'resource_id':_identity(row),'start':cursor,'end':end,'encoded_sha256':sha(encoded),
                       'replacement_sha256':sha(content),'header_pointer_offsets':headers})
        cursor=end
    if actual!=bytes(expected):raise ValueError('output differs from independently rebuilt ROM')
    applied=report['applied_patches']
    if len(applied)!=len(expected_patches) or len({p['offset'] for p in applied})!=len(expected_patches):
        raise ValueError('allocation/pointer ledger denominator mismatch')
    for patch in applied:
        witness=expected_patches.get(patch['offset'])
        if witness is None or any(patch.get(k)!=v for k,v in witness.items()):
            raise ValueError('allocation/pointer ledger identity mismatch')
    if (report['patch_class_counts']!={'allocation':len(ledger),'game_effective':len(applied)-len(ledger),
                                      'audit':0,'diagnostic':0}
            or report['output_rom']['size']!=len(actual)
            or report['output_rom']['sha1']!=hashlib.sha1(actual).hexdigest()):
        raise ValueError('allocation/pointer ledger report summary mismatch')
    physical=logical=0
    for key,row in resources.items():
        for offset in row['physical_offsets']:
            if codec._read_record(actual,offset)!=codec._read_record(base,offset):
                raise ValueError('old physical source changed during relocation')
            physical+=1
        content=replacements.get(key,row['source_content'])
        for alias in row['logical_aliases']:
            p=alias['header_pointer_offset'];offset=int.from_bytes(actual[p:p+4],'little')-0x08000000
            target=allocations.get(key,alias['physical_offset'])
            if offset!=target or codec._decompress(actual,offset)!=content:
                raise ValueError('logical header alias relocation/readback mismatch')
            logical+=1
    if (physical,logical)!=(217,249):raise ValueError('readback denominator mismatch')
    item={'case':name,'resources_relocated':len(ledger),'pointers_redirected':len(applied)-len(ledger),
          'output_size':len(actual),'output_sha256':sha(actual),'allocation_end':cursor,
          'allocation_span_bytes':cursor-START,'remaining_region_bytes':END-cursor,'allocation_ledger':ledger,
          'whole_rom_exact':True,'all_249_logical_references_redecoded':True,'all_217_old_sources_unchanged':True,
          'allocation_ledger_exact':True,'outside_declared_writes_unchanged':True}
    _write(case/'readback.json',item)
    return item


def run_roundtrip(root,run):
    root=Path(root).resolve(strict=True);contract,inputs=_inputs(root);run=_managed_run(root,run)
    _geometry(inputs)
    legacy=relocation.verify_audit(root,root/'artifacts/map-resource-relocation-v1')
    if legacy['errors'] or (legacy['verified_resources'],legacy['verified_pointers'])!=(166,249):
        raise ValueError(f'legacy relocation rejected: {legacy}')
    base=inputs['rom/base.gba'];catalog=json.loads(inputs[CATALOG]);resources=relocation._read_resources(base,catalog)
    contents={k:r['source_content'] for k,r in resources.items()}
    for row in resources.values():
        for offset in row['physical_offsets']:
            if codec._decompress(base,offset)!=row['source_content']:raise ValueError('raw independent source codec mismatch')
    if linked_domain(catalog,contents):raise ValueError('base linked map domain invalid')
    capacity=codec._expected_payload(root)
    overflow={(r['resource_type'],r['resource_sha256']) for r in capacity['resources'] if not r['mutation_fit_all_aliases']}
    if len(overflow)!=96:raise ValueError('overflow subset denominator mismatch')
    work=run/'roundtrip';work.mkdir(mode=0o700,exist_ok=False);fixture=work/'fixture';fixture.mkdir()
    _fixture_inputs(fixture,inputs,(*TOOLCHAIN,'rom/base.gba',CATALOG,LAYOUT,REGISTRY))
    mutations={}
    edits=[]
    for index,(key,row) in enumerate(resources.items()):
        b=bytearray(row['source_content']);b[2 if key[0]=='bg_palette' else 0]^=1;mutations[key]=bytes(b)
        source=f'edits/resource-{index:03d}.bin';p=fixture/source;p.parent.mkdir(exist_ok=True);p.write_bytes(b)
        edits.append(_edit(row,source))
    if linked_domain(catalog,contents,mutations):raise ValueError('simultaneous fixed mutations violate linked domain')
    accepted=[];rejected=[]
    def positive(name,spec,replacements):
        done,case=_build_cli(fixture,name,[spec])
        if done.returncode!=0:raise ValueError(f'{name} build failed: {done.stderr}')
        item=_readback(case,name,base,resources,replacements);accepted.append(item)
        if read_regular(fixture/'rom/base.gba')!=base:raise ValueError('immutable base changed')
        return item
    preserved=positive('preserve-all',_spec(inputs,[_edit(r) for r in resources.values()]),contents)
    if preserved['output_sha256']!=legacy['rebuilt_output_rom_sha256']:raise ValueError('preservation differs from legacy proof')
    positive('mutate-all',_spec(inputs,edits),mutations)
    subset={k:v for k,v in mutations.items() if k in overflow}
    subset_edits=[e for e in edits if (e['resource_type'],e['source_sha256']) in overflow]
    positive('mutate-overflow-subset',_spec(inputs,subset_edits),subset)
    graphics_key=next(k for k in resources if k[0]=='tile_graphics');graphics=resources[graphics_key]
    growth=graphics['source_content']+bytes(32);source='edits/graphics-append-one-tile.bin';(fixture/source).write_bytes(growth)
    if linked_domain(catalog,contents,{graphics_key:growth}):raise ValueError('one-tile growth violates linked domain')
    positive('graphics-append-one-tile',_spec(inputs,[_edit(graphics,source)]),{graphics_key:growth})
    def negative(name,specs,reason,*,with_layout=True):
        done,case=_build_cli(fixture,name,specs,with_layout=with_layout)
        present=(case/'output.gba').exists();reported=(case/'build-report.json').exists()
        last=done.stderr.strip().splitlines()[-1] if done.stderr.strip() else ''
        if done.returncode==0 or present or reported or reason not in last:
            raise ValueError(f'{name} was not atomically rejected: {last}')
        if read_regular(fixture/'rom/base.gba')!=base:raise ValueError('rejection modified immutable base')
        item={'case':name,'rejection_reason':last.removeprefix('ValueError: '),'build_exit_code':done.returncode,
              'output_rom_present':present,'output_report_present':reported}
        _write(case/'readback.json',item);rejected.append(item)
    layout_key=next(k for k in resources if k[0]=='primary_layout');row=resources[layout_key]
    bad=bytearray(row['source_content']);bad[:2]=b'\xff\xff';source='edits/invalid-layout.bin';(fixture/source).write_bytes(bad)
    if not linked_domain(catalog,contents,{layout_key:bytes(bad)}):raise ValueError('negative layout domain witness missing')
    negative('reject-linked-domain',[_spec(inputs,[_edit(row,source)])],'metatile index')
    wrong=_spec(inputs,[_edit(graphics)]);wrong['region_owner']='foreign'
    negative('reject-foreign-owner',[wrong],'owner mismatch')
    pattern=inputs['tools/data/map-relocation-overflow-pattern-v1.bin']
    over=graphics['source_content']+pattern*64;source='edits/overflow-graphics.bin';(fixture/source).write_bytes(over)
    if linked_domain(catalog,contents,{graphics_key:over}) or len(codec._encode(over))<=END-START:
        raise ValueError('negative growth capacity witness missing')
    negative('reject-region-capacity',[_spec(inputs,[_edit(graphics,source)])],'region capacity exceeded')
    mutation_source=next(e['content_file'] for e in edits if (e['resource_type'],e['source_sha256'])==graphics_key)
    negative('reject-conflicting-allocations',[_spec(inputs,[_edit(graphics)]),_spec(inputs,[_edit(graphics,mutation_source)])],
             'conflicting patch overlap')
    negative('reject-missing-layout',[_spec(inputs,[_edit(graphics)])],'requires an explicit ROM layout',with_layout=False)
    for n,digest in contract['inputs'].items():
        if sha(read_regular(root/n))!=digest:raise ValueError(f'input identity drift during builds: {n}')
    ids=[_identity(r) for r in resources.values()];overflow_ids=[_identity(r) for k,r in resources.items() if k in overflow]
    result={'schema':SCHEMA,'verified':True,'scope':contract['scope'],'contract_sha256':CONTRACT_SHA,
            'input_sha256':contract['inputs'],'implementation_sha256':sha(read_regular(root/SCRIPT)),
            'resource_ids_total':ids,'resource_ids_checked':ids,'overflow_resource_ids_total':overflow_ids,
            'overflow_resource_ids_checked':overflow_ids,'accepted':accepted,'rejected':rejected,
            'summary':{'resources':166,'physical_sources':217,'logical_references':249,'actual_build_cli_cases':9,
                       'accepted_batches':4,'rejected_cases':5,'fixed_slot_overflow_resources_rescued':96},
            'parent_allocation_ledger':[],'fixture_only_empty_parent_ledger':True,'build_environment_isolated':True,
            'aligned_u32_source_pointer_scan_words':len(base)//4,'computed_or_unaligned_consumers_exhausted':False,
            'arbitrary_edits_or_subsets_complete':False,'editor_db_connected':False,'runtime_executed':False,
            'full_graphics_release_gate_complete':False,'physical_gba_verified':False,
            'provider':{'python':sys.version,'platform':platform.system()}}
    _write(work/'result.json',result)
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--run',type=Path,required=True);args=parser.parse_args(argv)
    try:result=run_roundtrip(args.root,args.run)
    except (ValueError,OSError,KeyError,StopIteration,subprocess.TimeoutExpired) as error:
        print(json.dumps({'schema':SCHEMA,'verified':False,'errors':[str(error)]}));return 1
    print(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True));return 0


if __name__=='__main__':raise SystemExit(main())
