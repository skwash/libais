"""Test that the C extension fills every slot of the lists that it returns.

A list slot that the extension leaves empty holds NULL, and Python crashes
when it reads that slot.
"""

import unittest

import ais

# 8:1:26 environmental messages with one sensor report each.
CURRENT_2D = ('81mg=5@0FT000000000000000000', 0)
CURRENT_3D = ('81mg=5@0FU000000000000000000', 0)
HORIZONTAL_FLOW = ('81mg=5@0FV000000000000000000', 0)
# A Curr2D report followed by a Curr3D report.
TWO_CURRENT_REPORTS = ('81mg=5@0FT000000000000000000D000000000000000000', 2)

# 8:200:55 with 3 crew, 120 passengers and 7 other persons.
PERSONS_ON_BOARD = ('81mg=5@j=h<3h3P0000000000000', 0)
# 8:200:50 is not a defined RIS message.
RIS_FI_50 = ('81mg=5@j<P000000000000000000', 0)


class Ais8_1_26CurrentsTest(unittest.TestCase):

  def testCurrentListLengths(self):
    for (body, pad), field, count in (
        (CURRENT_2D, 'speed', 3), (CURRENT_3D, 'north', 2),
        (HORIZONTAL_FLOW, 'bearing', 2)):
      msg = ais.decode(body, pad)
      self.assertNotIn('currents', msg)
      currents = msg['reports'][0]['currents']
      self.assertEqual(count, len(currents))
      for current in currents:
        self.assertIn(field, current)
      repr(msg)

  def testEachReportKeepsItsCurrents(self):
    msg = ais.decode(*TWO_CURRENT_REPORTS)
    self.assertEqual(3, len(msg['reports'][0]['currents']))
    self.assertEqual(2, len(msg['reports'][1]['currents']))
    self.assertIn('speed', msg['reports'][0]['currents'][0])
    self.assertIn('north', msg['reports'][1]['currents'][0])


class Ais8_200_55Test(unittest.TestCase):

  def testDecode(self):
    msg = ais.decode(*PERSONS_ON_BOARD)
    self.assertEqual((200, 55), (msg['dac'], msg['fi']))
    self.assertEqual(3, msg['crew'])
    self.assertEqual(120, msg['passengers'])
    self.assertEqual(7, msg['yet_more_personnel'])
    self.assertEqual([0, 0, 0], msg['spare2'])

  def testFi50IsNotDecodedAsFi55(self):
    self.assertRaises(ais.DecodeError, ais.decode, *RIS_FI_50)


if __name__ == '__main__':
  unittest.main()
