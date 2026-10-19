"""Background adapter discovery and updates confined to the sidebar fragment."""

from concurrent.futures import Future
import os
from threading import Event
import unittest
from unittest.mock import Mock, patch

from streamlit.runtime.scriptrunner_utils.script_requests import RerunData
from streamlit.testing.v1 import AppTest

from utils.ui import sidebar


SCRIPT = '''
import streamlit as st
from utils.ui.sidebar import _render_local_server
st.session_state.full_runs = st.session_state.get('full_runs', 0) + 1
with st.sidebar:
    _render_local_server()
st.markdown('Video view stays put')
'''


class NetworkAdapterLoadingTest(unittest.TestCase):
    def setUp(self):
        sidebar._get_network_addresses.clear()
        self.addCleanup(sidebar._get_network_addresses.clear)
        environment = patch.dict(os.environ)
        environment.start()
        self.addCleanup(environment.stop)
        os.environ.pop(sidebar.LAN_CHILD, None)

    def test_discovery_returns_before_query_finishes_and_reuses_one_worker(self):
        started, release = Event(), Event()
        options = [('192.168.1.20', 'Wi-Fi')]

        def slow_query():
            started.set()
            release.wait(5)
            return options

        with patch.object(sidebar, 'network_addresses', side_effect=slow_query) as query:
            try:
                future = sidebar._get_network_addresses()
                self.assertTrue(started.wait(2))
                self.assertFalse(future.done())
                self.assertIs(sidebar._get_network_addresses(), future)
                query.assert_called_once_with()
            finally:
                release.set()
            self.assertEqual(future.result(timeout=2), options)

    def test_completion_and_adapter_selection_do_not_rerun_the_video_view(self):
        future = Future()
        server = Mock(running=False, firewall_requested=False)
        with patch.object(sidebar, '_get_network_addresses', return_value=future), \
                patch.object(sidebar, '_get_local_server', return_value=server):
            app = AppTest.from_string(SCRIPT, default_timeout=5).run()
            self.assertEqual(list(app.exception), [])
            self.assertEqual(app.session_state.full_runs, 1)
            self.assertTrue(any('Loading network adapters' in item.value for item in app.caption))
            self.assertEqual(len(app.selectbox), 0)

            future.set_result([('192.168.1.20', 'Wi-Fi'), ('192.168.1.21', 'Ethernet')])
            # AppTest has no browser timer. Send the same fragment-only rerun
            # that Streamlit's auto-rerun timer sends after discovery completes.
            fragment_ids = list(app._fragment_storage._fragments)

            def fragment_rerun(**kwargs):
                return RerunData(**kwargs, fragment_id_queue=fragment_ids)

            with patch('streamlit.testing.v1.local_script_runner.RerunData',
                       side_effect=fragment_rerun):
                app.run()
                self.assertEqual(list(app.exception), [])
                self.assertEqual(app.session_state.full_runs, 1)
                self.assertEqual(app.selectbox(key='local_server_address').options,
                                 ['Wi-Fi', 'Ethernet'])
                app.selectbox(key='local_server_address').select('192.168.1.21').run()
                self.assertEqual(list(app.exception), [])
                self.assertEqual(app.session_state.local_server_address, '192.168.1.21')
                self.assertEqual(app.session_state.full_runs, 1)
            server.start.assert_not_called()

    def test_failed_discovery_is_displayed_in_the_network_section(self):
        future = Future()
        future.set_exception(OSError('Network unavailable'))
        with patch.object(sidebar, '_get_network_addresses', return_value=future):
            app = AppTest.from_string(SCRIPT, default_timeout=5).run()
        self.assertEqual(list(app.exception), [])
        self.assertEqual(app.error[0].value, 'Could not load network adapters: Network unavailable')
        self.assertEqual(app.session_state.full_runs, 1)

    def test_lan_client_does_not_start_adapter_discovery(self):
        with patch.dict(os.environ, {sidebar.LAN_CHILD: '1'}), \
                patch.object(sidebar, '_get_network_addresses') as discover:
            app = AppTest.from_string(SCRIPT, default_timeout=5).run()
        self.assertEqual(list(app.exception), [])
        discover.assert_not_called()


if __name__ == '__main__':
    unittest.main()
