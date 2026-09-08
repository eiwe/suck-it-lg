import copy
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('lgprivacy', Path(__file__).resolve().parents[1] / 'lgprivacy.py')
lg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lg)


class SafetyTests(unittest.TestCase):
    def consent(self):
        return {'eulaStatus': {'networkAllowed': True, 'futureAllowed': False, 'country': 'EXAMPLE'},
                'eulaInfo': {'version': 'example', 'eulaList': [{'id': 'EXAMPLE', 'accepted': True, 'metadata': {'keep': 1}}]},
                'eulaInfoNetwork': {'eulaList': [{'id': 'EXAMPLE2', 'accepted': False}]}}

    def test_decline_preserves_metadata_and_original(self):
        original = self.consent()
        before = copy.deepcopy(original)
        result = lg.decline_consents(original)
        self.assertEqual(before, original)
        self.assertEqual(result['eulaInfo']['eulaList'][0]['metadata'], {'keep': 1})
        self.assertEqual(result['eulaStatus']['country'], 'EXAMPLE')
        self.assertTrue(lg.consents_declined(result))
        self.assertFalse(lg.consents_declined(original))

    def test_empty_or_malformed_consent_cannot_pass(self):
        for data in ({}, {'eulaStatus': {}}, {'eulaStatus': {'networkAllowed': 'false'}}):
            self.assertFalse(lg.consents_declined(data))
        data = self.consent()
        del data['eulaInfo']['eulaList'][0]['accepted']
        self.assertFalse(lg.consents_declined(data))

    def test_rejects_addresses_that_could_break_access_or_inject_shell(self):
        for value in ('127.0.0.1', '0.0.0.0', '1.1.1.1', '::1', '192.168.1.1;reboot', '192.168.1.1/24', 'example.com'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                lg.private_ipv4(value)
        self.assertEqual(lg.private_ipv4('192.168.50.10'), '192.168.50.10')

    def test_preflight_aborts_on_ssh_return_address_mismatch(self):
        with patch.object(lg, 'inspect', return_value={'uid': 0, 'ssh_client_ip': '192.168.50.11'}):
            with self.assertRaisesRegex(RuntimeError, 'lock you out'):
                lg.preflight({'admin_ipv4': '192.168.50.10'})

    def test_firewall_render_has_no_session_address(self):
        files = lg.render_files({'admin_ipv4': '192.168.50.10'}, False)
        firewall = files['/var/lib/webosbrew/init.d/00-network-privacy']
        self.assertIn('-d 192.168.50.10 -p tcp --sport 22', firewall)
        self.assertNotIn('@ADMIN_IPV4@', firewall)
        self.assertNotIn('/var/lib/webosbrew/init.d/20-disable-lg-channels', files)


if __name__ == '__main__':
    unittest.main()
