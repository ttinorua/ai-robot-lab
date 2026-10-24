import importlib.util
import json
import os
from pathlib import Path
import sys
import threading
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 't-duck-bridge'))
import bridge
from test_bridge import StubSimulation
spec = importlib.util.spec_from_file_location('cloud_start', Path(__file__).with_name('start.py'))
start = importlib.util.module_from_spec(spec); spec.loader.exec_module(start)

class PackagingTests(unittest.TestCase):
    def test_defaults_cannot_fetch_or_start(self):
        with self.assertRaises(ValueError): start.validate_environment({})
    def test_no_implicit_http_or_owner_token(self):
        for env in [{'T_DUCK_SOURCE_USE_APPROVED':'yes'}, {'T_DUCK_SOURCE_USE_APPROVED':'yes','T_DUCK_EDGE_HTTPS':'trusted-provider-edge-only'}]:
            with self.assertRaises(ValueError): start.validate_environment(env)
    def test_valid_explicit_configuration(self):
        env={'T_DUCK_SOURCE_USE_APPROVED':'yes','T_DUCK_EDGE_HTTPS':'trusted-provider-edge-only','T_DUCK_TOKEN':'test-only-token-at-least-24-characters'}
        self.assertEqual(start.validate_environment(env),10000)
        env['PORT']='80'
        with self.assertRaises(ValueError): start.validate_environment(env)
    def test_pinned_sources_match_integration_lock(self):
        for name in ('foundation','rl','runtime'):
            self.assertEqual(start.SOURCES[name][1],bridge.LOCK[name+'_revision'])
    def test_edge_transport_requires_explicit_opt_in(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError): bridge.make_server('127.0.0.1',0,'t'*24,bridge.CommandGate(StubSimulation()),edge_https=True)

class EdgeHTTPTests(unittest.TestCase):
    def setUp(self):
        self.sim=StubSimulation(); self.gate=bridge.CommandGate(self.sim)
        with patch.dict(os.environ,{'T_DUCK_EDGE_HTTPS':'trusted-provider-edge-only'}):
            self.server=bridge.make_server('127.0.0.1',0,'t'*24,self.gate,edge_https=True)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.base='http://127.0.0.1:'+str(self.server.server_address[1])
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join()
    def request(self,path,body=None,token='t'*24,proto='https'):
        r=urllib.request.Request(self.base+path,data=json.dumps(body).encode() if body else None,
            headers={'Authorization':'Bearer '+token,'X-Forwarded-Proto':proto})
        with urllib.request.urlopen(r,timeout=2) as response:return json.load(response)
    def test_no_cleartext_or_unauthenticated_controls(self):
        for token,proto,status in [('t'*24,'http',403),('wrong','https',401)]:
            with self.assertRaises(urllib.error.HTTPError) as error:self.request('/v1/telemetry',token=token,proto=proto)
            self.assertEqual(error.exception.code,status)
        self.assertEqual(self.sim.commands,[])
    def test_health_does_not_change_session_or_simulation(self):
        self.assertEqual(self.request('/healthz',token='',proto=''),{'ready':True})
        self.assertIsNone(self.gate.session);self.assertEqual(self.sim.commands,[])
    def test_edge_session_and_ordered_command(self):
        session=self.request('/v1/session',{'purpose':'companion_control'})['session_id']
        ack=self.request('/v1/commands',{'id':'edge-test','command':'forward','ttl_ms':500,'sequence':1,'session_id':session})
        self.assertTrue(ack['accepted']);self.assertEqual(self.sim.commands[-1][0],'forward')
    def test_overload_closes_instead_of_spawning(self):
        # Reserve all server slots and verify additional traffic cannot mutate state.
        for _ in range(8):self.assertTrue(self.server.slots.acquire(False))
        try:
            with self.assertRaises((OSError,ConnectionError)):self.request('/v1/session',{'purpose':'companion_control'})
            self.assertEqual(self.sim.commands,[])
        finally:
            for _ in range(8):self.server.slots.release()

@unittest.skipUnless(os.environ.get('TC02_FOUNDATION'),'Pinned simulation sources required')
class ActualIdleTests(unittest.TestCase):
    def test_idle_pause_cannot_be_extended_by_telemetry(self):
        clock=[0.]
        sim=bridge.Simulation(os.environ['TC02_FOUNDATION'],os.environ['TC02_RL'],os.environ['TC02_RUNTIME'],clock=lambda:clock[0])
        sim.apply('stand',1000,'stand');sim.tick()
        before=sim.telemetry()['pose']
        clock[0]=61.
        for _ in range(3):sim.telemetry();sim.tick()
        self.assertTrue(sim.paused);self.assertEqual(sim.mode,'rest')
        self.assertEqual(sim.telemetry()['pose'],before)
        self.assertEqual(sim.status,'ready')
        sim.apply('stand',1000,'deliberate-resume');sim.tick()
        self.assertGreater(sim.telemetry()['pose']['frame_id'],before['frame_id'])

if __name__=='__main__':unittest.main()
