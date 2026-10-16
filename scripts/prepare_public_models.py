"""Download pinned public assets and verify bytes before evaluation.

Weights stay external. PaliGemma tokenizer requires the user's own HF access.
The DINO source patch preserves accepted bytes (whitespace/comments only).
"""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.steering_runtime import digest, atomic_json


def manifest():
    return json.loads((ROOT/'scripts/public_model_sources.json').read_text())


def checked(path, row):
    if not path.is_file() or path.stat().st_size != row['bytes'] or digest(path)!=row['sha256']:
        raise ValueError(f'Asset identity mismatch: {path}')


def download_file(url, path, sha256):
    if path.exists():
        if digest(path)!=sha256:raise ValueError(f'Existing file differs: {path}')
        return
    path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent,delete=False) as f:
        temp=Path(f.name)
        try:
            with urllib.request.urlopen(url,timeout=180) as response:
                shutil.copyfileobj(response,f,4*1024*1024)
            f.close()
            if digest(temp)!=sha256:raise ValueError(f'Download hash mismatch: {url}')
            temp.replace(path)
        finally:temp.unlink(missing_ok=True)


def install_dino(torch_home, recipe):
    dest=torch_home/'hub/facebookresearch_dinov2_main'
    expected=[r for r in json.loads((ROOT/'scripts/steering_model_assets_manifest.json').read_text())['files']
              if r['root']=='torch_home']
    patch=ROOT/'scripts'/recipe['patch']
    if digest(patch)!=recipe['patch_sha256']:raise ValueError('DINO compatibility patch hash mismatch')
    if not dest.exists():
        torch_home.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=torch_home) as temporary:
            temporary=Path(temporary); archive=temporary/'source.zip';tree=temporary/'tree';tree.mkdir()
            download_file(recipe['archive_url'],archive,recipe['archive_sha256'])
            with zipfile.ZipFile(archive) as z:
                for row in expected:
                    prefix='hub/facebookresearch_dinov2_main/'
                    if not row['path'].startswith(prefix):continue
                    name=row['path'][len(prefix):]
                    target=tree/name;target.parent.mkdir(parents=True,exist_ok=True)
                    target.write_bytes(z.read('dinov2-'+recipe['revision']+'/'+name))
            subprocess.run(['patch','--batch','--fuzz=0','-p1','-i',str(patch)],cwd=tree,check=True)
            for row in expected:
                prefix='hub/facebookresearch_dinov2_main/'
                if row['path'].startswith(prefix):checked(tree/row['path'][len(prefix):],row)
            dest.parent.mkdir(parents=True,exist_ok=True);tree.rename(dest)
    weight=recipe['weight']
    download_file(weight['url'],torch_home/'hub/checkpoints/dinov2_vitb14_pretrain.pth',weight['sha256'])
    for row in expected:checked(torch_home/row['path'],row)


def download(args):
    recipe=manifest();root=args.directory.expanduser().resolve();root.mkdir(parents=True,exist_ok=True)
    keys=('rdt_checkpoint','text_encoder','vision_encoder') if args.model=='rdt' else ('pi05_checkpoint','pi05_tokenizer')
    from huggingface_hub import snapshot_download
    for key in keys:
        entry=recipe['huggingface'][key]
        for row in entry['files']:
            target=root/key/row['path']
            if target.exists():checked(target,row)
        print(f"{key}: {entry['repo']} @ {entry['revision']}",flush=True)
        snapshot_download(entry['repo'],revision=entry['revision'],local_dir=root/key,
                          allow_patterns=[r['path'] for r in entry['files']])
        for row in entry['files']:checked(root/key/row['path'],row)
    install_dino(root/'torch_home',recipe['dino'])
    atomic_json(root/f'{args.model}-download-receipt.json',dict(model=args.model,directory=str(root),
        manifest_sha256=digest(ROOT/'scripts/public_model_sources.json'),verified=True))


def configure_pi05(args):
    from scripts.pi05_runtime import verify_assets
    from scripts.prepare_steering_assets import verify_libero, write_json
    if args.gpu < 0 or args.egl_device_id < 0:
        raise ValueError('GPU and EGL indices must be nonnegative')
    root=args.directory.expanduser().resolve();libero=(ROOT/'third_party/libero_pro').resolve()
    local=dict(gpu=args.gpu,egl_device_id=args.egl_device_id,allocator_limit_gib=96,
        pi05_checkpoint=str(root/'pi05_checkpoint'),pi05_tokenizer=str(root/'pi05_tokenizer'),
        torch_home=str(root/'torch_home'),libero_root=str(libero),libero_config=str(ROOT/'.libero_config'))
    verify_libero(libero);verify_assets(local)
    benchmark=libero/'libero/libero'
    paths={key:str(benchmark/suffix) for key,suffix in [('benchmark_root',''),('assets','assets'),('bddl_files','bddl_files'),('init_states','init_files')]}
    paths['datasets']=str(libero/'libero/datasets')
    write_json(ROOT/'.libero_config/config.yaml',paths)
    write_json(args.output,local)
    print(json.dumps(local,indent=2))


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    d=sub.add_parser('download');d.add_argument('--model',choices=('rdt','pi05'),required=True);d.add_argument('--directory',type=Path,required=True)
    c=sub.add_parser('configure-pi05');c.add_argument('--directory',type=Path,required=True);c.add_argument('--gpu',type=int,required=True);c.add_argument('--egl-device-id',type=int,required=True);c.add_argument('--output',type=Path,default=ROOT/'configs/local.yaml')
    args=p.parse_args()
    if args.command=='download':download(args)
    else:configure_pi05(args)

if __name__=='__main__':main()
