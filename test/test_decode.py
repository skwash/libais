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

  def testTidalWindow6_1_32ThreeWindows(self):
    # IMO SN.1/Circ.289 Table 3.1 with three 88-bit windows.  361 bits.
    msg = ais.decode(
        '65MGukQGGcuD062usw<M2K`t37`N5`kgrt`9hHtD:g9J1VwTMhW8pQjT;HLBP', 5)
    self.assertEqual(11, msg['utc_month'])
    self.assertEqual(27, msg['utc_day'])
    expected = [
        (-70.125, 42.5, 6, 15, 8, 30, 45, 2.5),
        (-70.25, 42.625, 10, 5, 11, 50, 180, 1.2),
        (-70.375, 42.75, 14, 20, 16, 45, 270, 3.7),
    ]
    self.assertEqual(len(expected), len(msg['windows']))
    for window, values in zip(msg['windows'], expected):
      x, y, from_hour, from_min, to_hour, to_min, cur_dir, cur_speed = values
      self.assertAlmostEqual(x, window['x'])
      self.assertAlmostEqual(y, window['y'])
      self.assertEqual(from_hour, window['from_utc_hour'])
      self.assertEqual(from_min, window['from_utc_min'])
      self.assertEqual(to_hour, window['to_utc_hour'])
      self.assertEqual(to_min, window['to_utc_min'])
      self.assertEqual(cur_dir, window['cur_dir'])
      self.assertAlmostEqual(cur_speed, window['cur_speed'], places=5)

  def testTidalWindow6_1_32Rejects350Bits(self):
    self.assertRaisesRegex(
        ais.DecodeError, 'AIS_ERR_BAD_BIT_COUNT', ais.decode,
        '65MGukQGGcuD062usw<M2K`t37`N5`kgrt`9hHtD:e0kOj>pCTL@qB5d>9@', 4)


if __name__=='__main__':
  unittest.main()
