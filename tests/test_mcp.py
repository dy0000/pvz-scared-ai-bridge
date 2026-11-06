"""MCP malformed-input regressions use only stdio; no game/bridge connection."""
from pathlib import Path
import json
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


class McpTests(unittest.TestCase):
    def exchange(self, lines):
        process = subprocess.run(
            [sys.executable,'-X','utf8',str(ROOT/'scripts/run_mcp.py')],
            input='\n'.join(lines)+'\n',capture_output=True,text=True,encoding='utf8',timeout=5)
        self.assertEqual(process.returncode, 0, process.stderr)
        def reject_constant(value):
            raise AssertionError('Non-finite number in MCP response: '+value)
        return [json.loads(line,parse_constant=reject_constant) for line in process.stdout.splitlines()]

    def assert_survives(self, malformed, code, error_id=None):
        replies = self.exchange([malformed, '{"jsonrpc":"2.0","id":99,"method":"ping"}'])
        self.assertEqual(len(replies), 2)
        self.assertEqual(replies[0]['id'], error_id)
        self.assertEqual(replies[0]['error']['code'], code)
        self.assertEqual(replies[1], {'jsonrpc':'2.0','id':99,'result':{}})

    def test_nonobjects_return_invalid_request_and_allow_next_ping(self):
        for payload in ('[]', 'null', 'true', '42', '"text"'):
            with self.subTest(payload=payload):
                self.assert_survives(payload, -32600)

    def test_parse_errors_allow_next_ping(self):
        for payload in ('{broken', '[', '['*1500):
            with self.subTest(payload=payload):
                self.assert_survives(payload, -32700)

    def test_invalid_ids_return_null_without_terminating(self):
        for raw_id in ('NaN', 'Infinity', '-Infinity', '1e309', '[NaN]', '{"nested":1e309}', 'null', 'true'):
            with self.subTest(raw_id=raw_id):
                self.assert_survives('{"jsonrpc":"2.0","id":'+raw_id+',"method":"ping"}', -32600)

    def test_invalid_envelopes_do_not_dispatch(self):
        for fields in ('"method":3', '"method":"tools/call","params":null', '"method":"ping","params":[]'):
            with self.subTest(fields=fields):
                self.assert_survives('{"jsonrpc":"2.0","id":5,'+fields+'}', -32600, 5)

    def test_outbound_serialization_error_still_returns_safe_error(self):
        self.assert_survives('{"jsonrpc":"2.0","id":"init","method":"initialize",'
                             '"params":{"protocolVersion":NaN}}', -32603, 'init')

    def test_valid_handshake_notifications_and_tools_list(self):
        replies = self.exchange([
            '{"jsonrpc":"2.0","id":"init","method":"initialize","params":{"protocolVersion":"2024-11-05"}}',
            '{"jsonrpc":"2.0","method":"notifications/initialized"}',
            '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"pvzh_take_control"}}',
            '{"jsonrpc":"2.0","id":0,"method":"tools/list"}',
            '{"jsonrpc":"2.0","id":1.5,"method":"ping"}'
        ])
        self.assertEqual(len(replies), 3)
        self.assertEqual(replies[0]['id'], 'init')
        self.assertEqual(replies[0]['result']['protocolVersion'], '2024-11-05')
        self.assertEqual(replies[1]['id'], 0)
        self.assertEqual(len(replies[1]['result']['tools']), 32)
        self.assertEqual(replies[2]['id'], 1.5)
        self.assertEqual(replies[2]['result'], {})

    def test_string_ids_are_safe_to_write_to_utf8_stdio(self):
        ids = ['normal', '中文', '\ud800']
        replies = self.exchange([json.dumps({'jsonrpc':'2.0','id':value,'method':'ping'}) for value in ids])
        self.assertEqual([reply['id'] for reply in replies], ids)
        self.assertTrue(all(reply['result'] == {} for reply in replies))


if __name__ == '__main__':
    unittest.main(verbosity=2)
