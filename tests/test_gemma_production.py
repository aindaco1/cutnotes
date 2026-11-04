import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from cutnotes_core import cli, gemma_model as gm, pipeline
from cutnotes_core.contracts import CutNotesError
from cutnotes_core.gemma_formatting import messages_for, write_new
from cutnotes_core.source_decisions import parse_body_contract


class GemmaProductionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)/'model'
        self.data = b'pinned model fixture'
        self.manifest = {**gm.MANIFEST, 'bytes':len(self.data), 'files':[
            {'name':'model.bin','bytes':len(self.data),'sha256':hashlib.sha256(self.data).hexdigest()}]}
        for patch in [mock.patch.object(gm,'MANIFEST',self.manifest),
                      mock.patch.object(gm,'model_directory',return_value=self.root),
                      mock.patch.object(gm,'runtime_issue',return_value=None)]:
            patch.start(); self.addCleanup(patch.stop)

    def response(self, data, status=200, headers=None):
        response=io.BytesIO(data); response.status=status; response.headers=headers or {}
        return response

    def test_download_verifies_and_installs_without_upload(self):
        with mock.patch.object(gm.urllib.request,'urlopen',return_value=self.response(self.data)) as request:
            result=gm.download_model(accept_license=True)
        self.assertEqual(result['state'],'ready')
        self.assertEqual((self.root/'model.bin').read_bytes(),self.data)
        self.assertIsNone(request.call_args.args[0].data)
        self.assertIn(gm.MANIFEST['revision'],request.call_args.args[0].full_url)

    def test_resume_requests_exact_remaining_range(self):
        staging=self.root.with_name('.model.download'); staging.mkdir()
        (staging/'model.bin').write_bytes(self.data[:5])
        headers={'Content-Range':f'bytes 5-{len(self.data)-1}/{len(self.data)}'}
        with mock.patch.object(gm.urllib.request,'urlopen',return_value=self.response(self.data[5:],206,headers)) as request:
            gm.download_model(accept_license=True)
        self.assertEqual(request.call_args.args[0].get_header('Range'),'bytes=5-')
        self.assertEqual((self.root/'model.bin').read_bytes(),self.data)

    def test_server_ignoring_range_restarts_instead_of_appending(self):
        staging=self.root.with_name('.model.download'); staging.mkdir()
        (staging/'model.bin').write_bytes(b'old')
        with mock.patch.object(gm.urllib.request,'urlopen',return_value=self.response(self.data)):
            gm.download_model(accept_license=True)
        self.assertEqual((self.root/'model.bin').read_bytes(),self.data)

    def test_wrong_range_and_corrupt_content_never_install(self):
        for response in [self.response(self.data,206,{'Content-Range':'bytes 9-22/23'}), self.response(b'x'*len(self.data))]:
            with mock.patch.object(gm.urllib.request,'urlopen',return_value=response):
                with self.assertRaises(CutNotesError):gm.download_model(accept_license=True)
            self.assertFalse(self.root.exists())

    def test_interrupted_download_is_resumable(self):
        with mock.patch.object(gm.urllib.request,'urlopen',return_value=self.response(self.data[:5])):
            with self.assertRaises(CutNotesError):gm.download_model(accept_license=True)
        self.assertEqual(gm.model_status()['state'],'partial')
        self.assertEqual(gm.model_status()['downloaded_bytes'],5)

    def test_license_and_disk_checks_precede_network(self):
        with mock.patch.object(gm.urllib.request,'urlopen') as network:
            with self.assertRaises(CutNotesError):gm.download_model(accept_license=False)
            with mock.patch.object(gm.shutil,'disk_usage',return_value=mock.Mock(free=0)):
                with self.assertRaises(CutNotesError):gm.download_model(accept_license=True)
        network.assert_not_called()

    def test_symlink_cannot_escape_staging(self):
        staging=self.root.with_name('.model.download'); staging.mkdir()
        victim=Path(self.temporary.name)/'source'; victim.write_bytes(b'keep')
        (staging/'model.bin').symlink_to(victim)
        with self.assertRaises(CutNotesError):gm.download_model(accept_license=True)
        self.assertEqual(victim.read_bytes(),b'keep')

    def test_import_preserves_source_and_detects_later_corruption(self):
        source=Path(self.temporary.name)/'source';source.mkdir()
        (source/'model.bin').write_bytes(self.data)
        gm.import_model(source)
        self.assertEqual(list(p.name for p in source.iterdir()),['model.bin'])
        (self.root/'model.bin').write_bytes(b'x'*len(self.data))
        with self.assertRaises(CutNotesError):gm.validate_model()

    def test_receipt_does_not_bypass_full_format_verification(self):
        self.root.mkdir(); path=self.root/'model.bin';path.write_bytes(b'x'*len(self.data))
        (self.root/gm.RECEIPT).write_text(json.dumps({'revision':gm.MANIFEST['revision'],'files':gm.fingerprint(self.root)}))
        with self.assertRaises(CutNotesError):gm.require_ready()

    def test_formatter_defaults_and_model_contract_are_explicit(self):
        parser=cli.build_parser()
        self.assertEqual(parser.parse_args(['format','source.txt','--title','Title']).formatter,'gemma')
        self.assertEqual(parser.parse_args(['model','download','--kind','formatting','--json','--progress-fd','3']).kind,'formatting')
        with mock.patch('sys.stdout',new_callable=io.StringIO) as output:
            cli.run_model_status(parser.parse_args(['model','status','--kind','formatting','--json']))
        self.assertEqual(json.loads(output.getvalue())['schema_version'],'cutnotes.model.v1')

    def test_output_never_overwrites_source_or_existing_notes(self):
        path=Path(self.temporary.name)/'notes.md';path.write_text('original')
        with self.assertRaises(FileExistsError):write_new(path,'replacement')
        self.assertEqual(path.read_text(),'original')

    def test_recipe_uses_synthetic_examples_and_source_owned_times(self):
        messages,evidence=messages_for('At 1:20, the door is loud. Actually only the last slam bothers me.')
        self.assertEqual(len(messages),10)
        self.assertNotIn('1:20',messages[-1]['content'])
        self.assertIn('{T001}',messages[-1]['content'])
        with self.assertRaises(ValueError):parse_body_contract('{"timed":{"T002":"Invented"},"general":[]}',evidence)
        with self.assertRaises(ValueError):parse_body_contract('{"timed":{"T001":"Move it to 05:10"},"general":[]}',evidence)

    def test_missing_gemma_never_invokes_codex(self):
        args=cli.build_parser().parse_args(['import','input.wav','--title','Review'])
        with mock.patch.object(pipeline,'require_tool',return_value='/ffmpeg') as tool, mock.patch.object(pipeline,'find_local_engine',return_value='/local'), mock.patch.object(pipeline,'validate_model'), mock.patch.object(pipeline,'require_ready',side_effect=gm.failure('missing')):
            with self.assertRaises(CutNotesError):pipeline._required_pipeline_tools(args)
        tool.assert_called_once_with('CUTNOTES_FFMPEG','ffmpeg')
