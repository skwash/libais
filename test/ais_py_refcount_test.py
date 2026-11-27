"""Test that the C extension does not keep extra references to its results."""

import gc
import sys
import unittest

import ais

# 8:367:33 environmental messages with one sensor report each.
WIND = ('8>k1oFAKpB95?AruFRl7mre0<N00', 0)
CURRENT_2D = ('81mg=5AKpD000000000000000000', 0)
CURRENT_3D = ('81mg=5AKpE000000000000000000', 0)
HORIZONTAL_FLOW = ('81mg=5AKpF000000000000000000', 0)


class Ais8_367_33RefCountTest(unittest.TestCase):

  def assertOnlyOwnedByParent(self, parent, key):
    # Compare with a list that only a dict owns. The temporary references that
    # the subscript and getrefcount add differ between Python versions.
    control = {key: []}
    self.assertEqual(
        sys.getrefcount(control[key]), sys.getrefcount(parent[key]))

  def testReportsList(self):
    for body, pad in (WIND, CURRENT_2D, CURRENT_3D, HORIZONTAL_FLOW):
      msg = ais.decode(body, pad)
      self.assertEqual((367, 33), (msg['dac'], msg['fi']))
      self.assertOnlyOwnedByParent(msg, 'reports')

  def testCurrentsList(self):
    for body, pad in (CURRENT_2D, CURRENT_3D, HORIZONTAL_FLOW):
      msg = ais.decode(body, pad)
      self.assertOnlyOwnedByParent(msg['reports'][0], 'currents')

  def testNoGrowthOverManyDecodes(self):
    for body, pad in (WIND, CURRENT_2D, CURRENT_3D, HORIZONTAL_FLOW):
      for _ in range(100):
        ais.decode(body, pad)
      gc.collect()
      before = sys.getallocatedblocks()
      for _ in range(10000):
        ais.decode(body, pad)
      gc.collect()
      growth = sys.getallocatedblocks() - before
      self.assertLess(growth, 1000, 'Leaked %d blocks for %s' % (growth, body))


if __name__ == '__main__':
  unittest.main()
