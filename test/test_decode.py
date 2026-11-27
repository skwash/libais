#!/usr/bin/env python

"""Test the top level decoders with a single message each."""

import ais
import unittest
from . import test_data
import sys

class AisTopLevelDecoders(unittest.TestCase):

  def setUp(self):
    self.maxDiff = None

  def testAll(self):
    """Decode one of each top level message"""
    # TODO: message 20
    for entry in test_data.top_level:
      body = ''.join([line.split(',')[5] for line in entry['nmea']])
      pad = int(entry['nmea'][-1].split('*')[0][-1])
      msg = ais.decode(body, pad)
      expected = entry['result']
      if msg.keys() != expected.keys():
        sys.stderr.write('key mismatch: %s\n' % set(msg).symmetric_difference(set(expected)))
      self.assertDictEqual(
          expected, msg,
          'Mismatch for id:%d\n%s\n%s\n  From: %s' % (
              msg['id'], msg, expected, entry['nmea']))


class Ais6Decoders(unittest.TestCase):

  def testDecodeUnknownMessage6(self):
    # !AIVDM,1,1,,B,6B?n;be:cbapalgc;i6?Ow4,2*4A'
    # TODO(schwehr): Expose the C++ Python exception to Python.
    self.assertRaisesRegex(ais.DecodeError, '6:669:11',
                           ais.decode, '6B?n;be:cbapalgc;i6?Ow4', 2)


class HandBuiltPayloadDecoders(unittest.TestCase):
  """Hand-built payloads where each field has a distinct value."""

  def testText8_1_0SpareAfterText(self):
    # ITU-R M.1371-4 Annex 5 Table 25.  The first 2 bits of the text are 11.
    msg = ais.decode('85M:Ih00@<lfH2kSm4h', 2)
    self.assertEqual('9 KNOTS', msg['text'])
    self.assertEqual(1234, msg['msg_seq'])
    self.assertEqual(0, msg['spare2'])

  def testVtsTargets8_1_17(self):
    # IMO SN.1/Circ.289 Tables 6.1 and 6.2.
    msg = ais.decode('803OtPh0DIL@?7;?@2K`t=wGU1se38d48?7;<2Hq:>0gN4d77P', 4)
    self.assertEqual(
        [{'type': 2, 'id': 'WDC1234', 'spare': 0, 'x': -70.25, 'y': 42.5,
          'cog': 123, 'timestamp': 45, 'sog': 12},
         {'type': 2, 'id': 'KABC123', 'spare': 0, 'x': -69.5, 'y': 41.75,
          'cog': 300, 'timestamp': 7, 'sog': 30}],
        msg['targets'])

  def testVtsTargets8_1_17NoTargets(self):
    self.assertRaisesRegex(ais.DecodeError, 'AIS_ERR_BAD_BIT_COUNT',
                           ais.decode, '803OtPh0D@', 4)

  def testWmoWeather8_1_21(self):
    # IMO SN.1/Circ.289 Table 10.2.
    msg = ais.decode(
        '85MA;ih0EIES<rVnnhTTW6j0kFRapI8FD0CIHD?C7QGp8BQi6lS9;368U<QR', 0)
    self.assertAlmostEqual(-70.5, msg['x'])
    self.assertAlmostEqual(42.25, msg['y'])
    self.assertEqual(11, msg['utc_month'])
    self.assertEqual(27, msg['utc_day'])
    self.assertEqual(13, msg['utc_hour'])
    self.assertEqual(40, msg['utc_min'])
    self.assertEqual(90, msg['cog'])
    self.assertEqual(95, msg['heading'])
    self.assertEqual(90, msg['bearing_ice_edge'])

  def testRisEta8_200_21(self):
    # ES-RIS Edition 2023/1 Annex 11 Table 11-4.
    msg = ais.decode('832S7Thj5@000005AHTG37;?@ht<g737W;FueeBL@0', 4)
    self.assertEqual('LOCK1', msg['terminal'])
    self.assertEqual(13, msg['eta_hour'])
    self.assertEqual(45, msg['eta_minute'])
    self.assertEqual(2, msg['tugboats'])
    self.assertAlmostEqual(12.5, msg['air_draught'], places=5)
    self.assertEqual(0, msg['spare2'])

  def testRisRta8_200_22(self):
    # ES-RIS Edition 2023/1 Annex 11 Table 11-8.
    msg = ais.decode('801tPehj5P000005AHTG37;?@ht<g737W;Fuee@', 2)
    self.assertEqual('LOCK1', msg['terminal'])
    self.assertEqual(13, msg['rta_hour'])
    self.assertEqual(45, msg['rta_minute'])
    self.assertEqual(1, msg['lock_status'])
    self.assertEqual(0, msg['spare2'])


if __name__=='__main__':
  unittest.main()
