"""Host regressions against a fake Frida target, temporary runtime and ephemeral port."""
from pathlib import Path
import json
import select
import socket
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
HARNESS = r'''
from pathlib import Path
import importlib.util,json,sys
spec=importlib.util.spec_from_file_location('host',sys.argv[1]);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
root=Path(sys.argv[2]);(root/'src').mkdir(parents=True,exist_ok=True);(root/'src/bridge.js').write_text('');(root/'src/story.js').write_text('');(root/'profile.json').write_text('{}')
m.ROOT=root;m.GAME=root/'fake.exe';m.GAME.write_text('fake');m.RUNTIME=root/'runtime'
m.process_path=lambda pid:m.GAME.resolve();m.verify_game=lambda:{}
m.target_exited=lambda pid:(root/'target-exited').exists()
def trace(op):
 with (root/'calls.jsonl').open('a') as f:f.write(json.dumps(op)+'\n')
def released():return {'ok':True,'result':{'selection_released':True,'controlled':False,'auto_collect':False,'held_os_inputs':0,'native_selection':0}}
class Exports:
 def request(self,r):
  trace(r)
  if r['op']=='detach':
   if (root/'block-transport').exists():raise m.frida.TransportError('isolated transport failure')
   if (root/'block-release').exists():return {'ok':False,'error':'Native selection release not confirmed'}
   return released()
  if r['op']=='buy':
   if (root/'lose-purchase-reply').exists():raise m.frida.RPCException('isolated lost purchase reply')
   return {'ok':True,'result':{'status':'Committed','spent':25,'purchase_id':r['id']}}
  return {'ok':True,'result':{'game':'PVZ-Scared','controlled':r['op']=='attach'}}
 def dispose(self):
  trace({'op':'dispose'})
  if (root/'block-dispose').exists():return {'ok':False,'error':'Native selection release not confirmed'}
  return released()
class Script:
 exports_sync=Exports()
 def on(self,*a):pass
 def load(self):pass
class Session:
 def create_script(self,*a):return Script()
 def on(self,*a):pass
 def detach(self):trace({'op':'session.detach'})
m.frida.attach=lambda pid:Session()
sys.argv=['host','--pid','1','--port',sys.argv[3]];m.main()
'''


def wait_for(predicate, seconds=5):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.03)
    raise AssertionError('Timed out waiting for isolated host state')


class HostTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='pvzh-host-test-')
        self.base = Path(self.temp.name)
        self.target = self.base / 'target'
        self.target.mkdir()
        (self.base / 'harness.py').write_text(HARNESS, encoding='utf8')
        self.peers = []
        with socket.socket() as reserve:
            reserve.bind(('127.0.0.1', 0))
            self.port = reserve.getsockname()[1]
        self.process = subprocess.Popen(
            [sys.executable, '-u', str(self.base/'harness.py'), str(ROOT/'scripts/run_bridge.py'),
             str(self.target), str(self.port)], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding='utf8')
        self.config_path = self.target/'runtime/connection.json'
        wait_for(self.config_path.exists)
        self.config = json.loads(self.config_path.read_text())

    def tearDown(self):
        for reader, peer in self.peers:
            reader.close()
            peer.close()
        for name in ('block-release', 'block-dispose', 'block-transport'):
            (self.target/name).unlink(missing_ok=True)
        (self.target/'runtime/stop.request').touch()
        try:
            self.stdout, self.stderr = self.process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()  # Only this test's fake child, never the game/maintained host.
            self.process.communicate()
            raise
        finally:
            self.temp.cleanup()

    def connect(self):
        peer = socket.create_connection(('127.0.0.1', self.port), timeout=3)
        reader = peer.makefile('rb')
        self.peers.append((reader, peer))
        return peer, reader

    def close_peer(self, peer, reader):
        reader.close()
        peer.close()
        self.peers.remove((reader, peer))

    def send(self, peer, reader, op, request_id='request', **extra):
        peer.sendall((json.dumps({'id':request_id,'token':self.config['token'],'op':op,**extra})+'\n').encode())
        return json.loads(reader.readline())

    def calls(self):
        file = self.target/'calls.jsonl'
        return [json.loads(line) for line in file.read_text().splitlines()] if file.exists() else []

    def state_is(self, state):
        return self.config_path.exists() and json.loads(self.config_path.read_text())['state'] == state

    def assert_locked(self):
        code = "import msvcrt,sys; f=open(sys.argv[1],'r+b'); msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)"
        attempt = subprocess.run([sys.executable,'-c',code,str(self.target/'runtime/controller.lock')],capture_output=True)
        self.assertNotEqual(attempt.returncode, 0, 'Controller lock was released prematurely')

    def test_nonobject_and_malformed_json_do_not_kill_host(self):
        peer, reader = self.connect()
        for payload in (b'[]', b'null', b'true', b'42', b'"text"', b'{broken'):
            with self.subTest(payload=payload):
                peer.sendall(payload+b'\n')
                reply = json.loads(reader.readline())
                self.assertFalse(reply['ok'])
                self.assertIsNone(reply['id'])
        self.assertTrue(self.send(peer, reader, 'observe')['ok'])
        self.assertIsNone(self.process.poll())

    def test_authentication_and_request_receipts_still_work(self):
        peer, reader = self.connect()
        self.assertFalse(self.send(peer, reader, 'attach', token='invalid')['ok'])
        first = self.send(peer, reader, 'attach', request_id='same')
        self.assertEqual(first, self.send(peer, reader, 'attach', request_id='same'))
        self.assertFalse(self.send(peer, reader, 'observe', request_id='same')['ok'])
        self.assertEqual(sum(c['op']=='attach' for c in self.calls()), 1)

    def test_invalid_request_ids_cannot_escape_into_error_replies(self):
        peer, reader = self.connect()
        for raw_id in ('1e309', 'NaN', 'Infinity', '-Infinity', '[NaN]', '{"nested":1e309}',
                       'null', 'true', '12', '""', json.dumps('x'*129)):
            with self.subTest(raw_id=raw_id):
                peer.sendall(('{"id":'+raw_id+'}\n').encode())
                reply = json.loads(reader.readline())
                self.assertFalse(reply['ok'])
                self.assertIsNone(reply['id'])
        self.assertTrue(self.send(peer, reader, 'observe')['ok'])
        self.assertIsNone(self.process.poll())

    def test_disconnect_blocks_next_controller_until_release_recovers(self):
        peer, reader = self.connect()
        self.send(peer, reader, 'attach')
        (self.target/'block-release').touch()
        self.close_peer(peer, reader)
        wait_for(lambda:self.state_is('release_blocked'))
        self.assert_locked()
        second, second_reader = self.connect()
        second.sendall((json.dumps({'id':'next','token':self.config['token'],'op':'attach'})+'\n').encode())
        self.assertFalse(select.select([second],[],[],.15)[0])
        self.assertEqual(sum(c['op']=='attach' for c in self.calls()), 1)
        (self.target/'block-release').unlink()
        self.assertTrue(json.loads(second_reader.readline())['ok'])
        self.assertEqual(sum(c['op']=='attach' for c in self.calls()), 2)

    def test_stop_does_not_bypass_failed_disconnect_release(self):
        peer, reader = self.connect()
        self.send(peer, reader, 'attach')
        (self.target/'block-release').touch()
        self.close_peer(peer, reader)
        wait_for(lambda:self.state_is('release_blocked'))
        (self.target/'runtime/stop.request').touch()
        self.assertIsNone(self.process.poll())
        self.assert_locked()
        self.assertFalse(any(c['op']=='dispose' for c in self.calls()))
        (self.target/'block-release').unlink()
        self.process.wait(timeout=4)
        self.assertEqual(self.process.returncode, 0)

    def test_transport_error_cannot_retire_ownership(self):
        peer, reader = self.connect()
        self.send(peer, reader, 'attach')
        (self.target/'block-transport').touch()
        self.close_peer(peer, reader)
        wait_for(lambda:self.state_is('release_blocked'))
        self.assert_locked()
        self.assertIsNone(self.process.poll())
        self.assertFalse(any(c['op']=='session.detach' for c in self.calls()))
        (self.target/'block-transport').unlink()
        wait_for(lambda:self.state_is('ready'))

    def test_dispose_failure_keeps_host_and_lock_until_game_exit(self):
        (self.target/'block-dispose').touch()
        (self.target/'runtime/stop.request').touch()
        wait_for(lambda:self.state_is('release_blocked'))
        self.assert_locked()
        self.assertFalse(any(c['op']=='session.detach' for c in self.calls()))
        (self.target/'target-exited').touch()
        self.process.wait(timeout=4)
        self.assertEqual(self.process.returncode, 0)
        self.assertFalse(self.config_path.exists())
        self.assertTrue(any(c['op']=='session.detach' for c in self.calls()))

    def test_purchase_pending_receipt_survives_lost_native_reply(self):
        peer, reader = self.connect()
        (self.target/'lose-purchase-reply').touch()
        result=self.send(peer,reader,'buy',request_id='purchase-once',product_id='native-product')
        self.assertFalse(result['ok'])
        receipt=self.send(peer,reader,'purchase_receipt',request_id='receipt',purchase_id='purchase-once')['result']
        self.assertEqual(receipt['status'],'unknown')
        journal=json.loads((self.target/'runtime/purchases.json').read_text())
        self.assertEqual(journal['purchase-once']['status'],'unknown')
        self.assertEqual(sum(c['op']=='buy' for c in self.calls()),1)

    def test_purchase_journal_prevents_replay_after_host_restart(self):
        peer, reader = self.connect()
        first=self.send(peer,reader,'buy',request_id='purchase-once',product_id='native-product')
        self.close_peer(peer,reader)
        (self.target/'runtime/stop.request').touch()
        self.process.communicate(timeout=5)
        self.assertEqual(self.process.returncode,0)
        (self.target/'runtime/stop.request').unlink()
        self.process=subprocess.Popen([sys.executable,'-u',str(self.base/'harness.py'),str(ROOT/'scripts/run_bridge.py'),str(self.target),str(self.port)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf8')
        wait_for(self.config_path.exists)
        self.config=json.loads(self.config_path.read_text())
        peer,reader=self.connect()
        replay=self.send(peer,reader,'buy',request_id='purchase-once',product_id='native-product')
        self.assertEqual(replay,first)
        self.assertEqual(sum(c['op']=='buy' for c in self.calls()),1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
