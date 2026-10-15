"""Only synthetic byte streams and one four-byte owned physical fixture."""
import hashlib
import io
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import witness_reader_v1 as w

HERE=Path(__file__).resolve().parent
PAYLOAD_PATH=HERE/'synthetic-index.bin'
M=1024**2
OLD_READER='38920670ae27e3d5cd468f16ee679d72db83dc2ae1715fa303a08f3c20fe823c'
OLD_BOUNDARY='04ace3fea4d5d0c191dc210ba012da9bdc9daf7eaa2d6aecbf70a9186c6ea33b'


def record(role,name,size=0,blob=None):
    return {'role':role,'path':str(HERE/name),'bytes':size,
            'sha256':hashlib.sha256(blob if blob is not None else b'').hexdigest()}


def controls():
    return [record(role,'synthetic-'+role+'.json') for role in sorted(w.CONTROLS)]


def ref(row):return {k:row[k] for k in ('path','sha256')}


class IndexCapTests(unittest.TestCase):
    def test_exact_reverse_bytes_and_boundary_copy(self):
        text=(HERE/'witness_reader_v1.py').read_text()
        self.assertEqual(text.count("'index_file':20*MiB"),1)
        self.assertEqual(text.count("else 'index_file' if role=='index' else 'metadata_file'"),2)
        reverse=text.replace("'metadata_file':16*MiB,'index_file':20*MiB,'metadata_total'", "'metadata_file':16*MiB,'metadata_total'")
        reverse=reverse.replace("else 'index_file' if role=='index' else 'metadata_file'", "else 'metadata_file'")
        self.assertEqual(hashlib.sha256(reverse.encode()).hexdigest(),OLD_READER)
        self.assertEqual(hashlib.sha256((HERE/'cpu_boundary_v1.py').read_bytes()).hexdigest(),OLD_BOUNDARY)
        self.assertEqual(w.CAPS['index_file'],20*M)
        self.assertEqual(w.CAPS['metadata_file'],16*M)
        self.assertEqual(w.CAPS['metadata_total'],128*M)

    def physical_stream(self,size,delta=0,wrong_hash=False):
        data=b'x'*size
        row=record('index',PAYLOAD_PATH.name,size,data)
        if wrong_hash:row['sha256']='0'*64
        reader=w.Reader(controls()+[row])
        raw=data+(b'!' if delta>0 else b'')
        if delta<0:raw=raw[:delta]
        requested=[]
        class BoundedStream(io.BytesIO):
            def read(self,n=-1):
                requested.append(n)
                if n<0:raise AssertionError('unbounded read')
                return super().read(n)
        oldstat=Path.stat
        oldopen=Path.open
        def fake_stat(p,*args,**kwargs):
            if p==PAYLOAD_PATH:return SimpleNamespace(st_size=size,st_mode=0o100600)
            return oldstat(p,*args,**kwargs)
        def fake_open(p,*args,**kwargs):
            if p==PAYLOAD_PATH:
                self.assertEqual(args,('rb',))
                return BoundedStream(raw)
            return oldopen(p,*args,**kwargs)
        with patch.object(Path,'stat',fake_stat),patch.object(Path,'open',fake_open):
            if delta or wrong_hash:
                with self.assertRaisesRegex(w.ExtractionError,'input bytes/hash changed'):
                    reader.blob(ref(row),'index')
                self.assertEqual(reader.cache,{})
            else:
                actual=reader.blob(ref(row),'index')
                self.assertEqual(actual,data)
                self.assertIs(reader.blob(ref(row),'index'),actual)
        self.assertEqual(requested,[size+1])
        self.assertEqual(reader.progress['metadata_bytes'],len(raw))
        self.assertEqual(reader.progress['container_bytes'],0)

    def test_index_above_old_ceiling_physical_branch(self):self.physical_stream(16*M+1)
    def test_index_exact_new_ceiling_physical_branch(self):self.physical_stream(20*M)
    def test_hash_mismatch_rejected(self):self.physical_stream(16*M+1,wrong_hash=True)
    def test_short_read_rejected(self):self.physical_stream(16*M+1,delta=-1)
    def test_excess_read_sentinel_rejected(self):self.physical_stream(20*M,delta=1)

    def test_index_above_twenty_rejected_before_loader_or_open(self):
        seen=[]
        row=record('index',PAYLOAD_PATH.name,20*M+1)
        with patch.object(Path,'open',side_effect=AssertionError('payload must not open')):
            with self.assertRaisesRegex(w.ExtractionError,'per-file cap'):
                w.Reader(controls()+[row],loader=lambda r:seen.append(r))
        self.assertEqual(seen,[])

    def test_all_nonindex_metadata_still_sixteen(self):
        for role in sorted(w.CONTROLS|{'receipt','audit'}):
            with self.subTest(role=role):
                rows=controls()
                row=record(role,'synthetic-big-'+role,16*M+1)
                rows=[r for r in rows if r['role']!=role]+[row]
                with self.assertRaisesRegex(w.ExtractionError,'per-file cap'):
                    w.Reader(rows,loader=lambda _:self.fail('payload read'))

    def test_nonindex_exact_sixteen_declaration_accepted(self):
        row=record('audit','synthetic-audit',16*M)
        self.assertIn(row['path'],w.Reader(controls()+[row]).rows)

    def test_manifest_limit_still_sixteen(self):
        w.Reader(controls(),input_manifest_bytes=16*M)
        with self.assertRaisesRegex(w.ExtractionError,'input manifest bytes'):
            w.Reader(controls(),input_manifest_bytes=16*M+1)

    def test_aggregate_exact128_and_plusone_manifest(self):
        rows=controls()+[record('index','synthetic-index-%d'%i,20*M) for i in range(6)]
        rows.append(record('audit','synthetic-audit',8*M))
        w.Reader(rows)
        with self.assertRaisesRegex(w.ExtractionError,'declared aggregate bytes'):
            w.Reader(rows,input_manifest_bytes=1)

    def test_aggregate128_plusone_index(self):
        rows=controls()+[record('index','synthetic-index-%d'%i,20*M) for i in range(6)]
        rows.append(record('index','synthetic-index-last',8*M+1))
        with self.assertRaisesRegex(w.ExtractionError,'declared aggregate bytes'):
            w.Reader(rows)

    def test_stat_size_drift_stops_before_open(self):
        row=record('index',PAYLOAD_PATH.name,5,b'abcd!')
        reader=w.Reader(controls()+[row])
        with patch.object(Path,'open',side_effect=AssertionError('no read on stat mismatch')):
            with self.assertRaisesRegex(w.ExtractionError,'input file changed'):
                reader.blob(ref(row),'index')

    def test_role_cannot_relabel_declared_index(self):
        row=record('index',PAYLOAD_PATH.name,4,b'abcd')
        reader=w.Reader(controls()+[row])
        with patch.object(Path,'open',side_effect=AssertionError('no role-mismatch read')):
            with self.assertRaisesRegex(w.ExtractionError,'reference role/hash'):
                reader.blob(ref(row),'audit')

    def test_real_small_physical_read_hash_and_cache(self):
        row=record('index',PAYLOAD_PATH.name,4,b'abcd')
        reader=w.Reader(controls()+[row])
        self.assertEqual(reader.blob(ref(row),'index'),b'abcd')
        self.assertEqual(reader.blob(ref(row),'index'),b'abcd')
        self.assertEqual(reader.progress['metadata_bytes'],4)
        wrong={**row,'sha256':'0'*64}
        with self.assertRaisesRegex(w.ExtractionError,'input bytes/hash changed'):
            w.Reader(controls()+[wrong]).blob(ref(wrong),'index')
