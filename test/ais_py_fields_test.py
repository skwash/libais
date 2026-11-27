"""Test that the C extension copies each field to the correct key.

The payloads have a distinct value in each field, so a key that is filled
from the wrong field gives a wrong value.
"""

import unittest

import ais


class Ais6FieldsTest(unittest.TestCase):

  def testAis6_1_4Spares(self):
    msg = ais.decode('61mg=5GcNJ;404A;2LW9jLW9jLW9jLW9jLW9jL0000;00005P000240002h',
                     2)
    self.assertEqual((1, 4), (msg['dac'], msg['fi']))
    self.assertEqual(300, msg['ack_dac'])
    self.assertEqual([11, 22, 33, 44], [msg['spare2'], msg['spare3'],
                                        msg['spare4'], msg['spare5']])

  def testAis6_1_5Ack(self):
    msg = ais.decode('61mg=5GcNJ;404Dj5IaJ0000VP1S', 0)
    self.assertEqual((1, 5), (msg['dac'], msg['fi']))
    self.assertEqual(200, msg['ack_dac'])
    self.assertEqual(21, msg['ack_fi'])
    self.assertEqual(1234, msg['seq_num'])
    self.assertIs(True, msg['ai_available'])
    self.assertEqual(5, msg['ai_response'])
    self.assertEqual(77, msg['spare'])
    self.assertEqual(99, msg['spare2'])


class Ais8FieldsTest(unittest.TestCase):

  def testAis8_1_24NextPorts(self):
    msg = ais.decode(
        '81mg=5@0F050ubaQ7abaW<QQPT0V00000000000000000000000000000000', 0)
    self.assertEqual((1, 24), (msg['dac'], msg['fi']))
    self.assertEqual('USBOS', msg['last_port'])
    self.assertEqual(['USNYC', 'CAHAL'], msg['port_list'])

  def testAis8_1_26HeaderOnEveryReport(self):
    msg = ais.decode('81mg=5@0FRRVmD00000000000000', 0)
    report = msg['reports'][0]
    self.assertEqual(
        {'report_type': 2, 'utc_day': 17, 'utc_hr': 9, 'utc_min': 45,
         'site_id': 42},
        {key: report[key] for key in
         ('report_type', 'utc_day', 'utc_hr', 'utc_min', 'site_id')})
    self.assertIn('wind_speed', report)

  def testAis8_1_26AirDraughtKeys(self):
    report = ais.decode('81mg=5@0Fb6@D<00000000000000', 0)['reports'][0]
    self.assertEqual(10, report['report_type'])
    self.assertIn('trend', report)
    self.assertIn('utc_day_forecast', report)
    self.assertFalse([key for key in report if key.startswith('int ')])


class Ais8_367_22Test(unittest.TestCase):

  def testWhaleBuoyCircle(self):
    # !AIVDM,1,1,,B,8h3Ovq1KmPA`08b8007P3ct5uAPmtlAkh000,0*2F
    msg = ais.decode('8h3Ovq1KmPA`08b8007P3ct5uAPmtlAkh000', 0)
    self.assertEqual((367, 22), (msg['dac'], msg['fi']))
    self.assertEqual(3669732, msg['mmsi'])
    self.assertEqual(104, msg['link_id'])
    self.assertEqual(0, msg['notice_type'])
    self.assertEqual((4, 10, 17, 0), (msg['month'], msg['day'], msg['hour'],
                                      msg['minute']))
    self.assertEqual(60, msg['duration_minutes'])
    self.assertEqual(1, len(msg['sub_areas']))
    circle = msg['sub_areas'][0]
    self.assertEqual('circle', circle['sub_area_type_str'])
    self.assertAlmostEqual(-70.1184, circle['x'], places=4)
    self.assertAlmostEqual(42.3113, circle['y'], places=4)
    self.assertEqual(2, circle['precision'])
    self.assertEqual(9260, circle['radius'])

  def testPolylines(self):
    msg = ais.decode(
        '8h3Ovq1KmP@N<95=`2l01=dN<b7pGeP00000LL8PSV8RQ8cTs5H0LTHh477PRpus@000',
        0)
    self.assertEqual(1440, msg['duration_minutes'])
    self.assertEqual(['point', 'polyline', 'polyline'],
                     [area['sub_area_type_str'] for area in msg['sub_areas']])

  def testBadBitCountRaises(self):
    self.assertRaisesRegex(ais.DecodeError, '8:367:22 AIS_ERR_BAD_BIT_COUNT',
                           ais.decode, '8h3Ovq1KmPA`08b8007P3ct5uAP', 0)


class UnknownDacFiTest(unittest.TestCase):

  def testUnknownAis8(self):
    self.assertRaisesRegex(
        ais.DecodeError,
        r'DAC:FI not known\.  8:367:60 AIS_ERR_MSG_SUB_NOT_IMPLEMENTED',
        ais.decode, '81mg=5AKw0000000000000000000', 0)

  def testUnknownAis6(self):
    self.assertRaisesRegex(
        ais.DecodeError,
        r'DAC:FI not known\.  6:669:11 AIS_ERR_MSG_SUB_NOT_IMPLEMENTED',
        ais.decode, '6B?n;be:cbapalgc;i6?Ow4', 2)

  def testSubMessageErrorIsNotUnknown(self):
    with self.assertRaises(ais.DecodeError) as context:
      ais.decode('81mg=5@0EP0000000000', 0)
    self.assertIn('8:1:22 AIS_ERR_BAD_BIT_COUNT', str(context.exception))
    self.assertNotIn('not known', str(context.exception))


if __name__ == '__main__':
  unittest.main()
