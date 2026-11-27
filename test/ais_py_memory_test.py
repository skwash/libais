"""Test the C extension when Python cannot allocate memory.

Each test makes one allocation fail at a time, for every allocation that a
decode makes.  The decode must raise MemoryError or return a complete result.
It must not crash, and it must not return a result with an exception set.
"""

import json
import subprocess
import sys
import textwrap
import unittest

import ais
from . import test_data

try:
  import _testcapi
  HAVE_NOMEMORY = hasattr(_testcapi, 'set_nomemory')
except ImportError:
  HAVE_NOMEMORY = False

# Messages with nested lists and dicts that test_data does not have.
EXTRA_CASES = (
    ('8>k1oFAKpB95?AruFRl7mre0<N00', 0),  # 8:367:33 wind.
    ('81mg=5AKpD000000000000000000', 0),  # 8:367:33 Curr2D.
    ('81mg=5AKpE000000000000000000', 0),  # 8:367:33 Curr3D.
    ('81mg=5AKpF000000000000000000', 0),  # 8:367:33 HorzFlow.
    ('81mg=5@0FT000000000000000000', 0),  # 8:1:26 Curr2D.
    ('81mg=5@0FU000000000000000000', 0),  # 8:1:26 Curr3D.
    ('81mg=5@0FV000000000000000000', 0),  # 8:1:26 HorzFlow.
    ('81mg=5@j=h<3h3P0000000000000', 0),  # 8:200:55 persons on board.
)

# The child process runs the sweep, so that a crash fails the test with the
# message that caused it instead of stopping the test run.
CHILD = textwrap.dedent('''
    import json
    import sys

    import _testcapi
    import _ais

    for body, pad in json.loads(sys.argv[1]):
      clean_runs = 0
      start = 0
      while clean_runs < 20 and start < 2000:
        sys.stderr.write('%s %d fail at %d\\n' % (body, pad, start))
        result = None
        failed = False
        try:
          _testcapi.set_nomemory(start, start + 1)
          result = _ais.decode(body, pad)
        except MemoryError:
          failed = True
        finally:
          _testcapi.remove_mem_hooks()
        clean_runs = 0 if failed else clean_runs + 1
        if result is not None:
          repr(result)
        start += 1
''')


def Cases():
  for entry in test_data.top_level:
    body = ''.join(line.split(',')[5] for line in entry['nmea'])
    pad = int(entry['nmea'][-1].split('*')[0][-1])
    yield body, pad
  yield from EXTRA_CASES


@unittest.skipUnless(HAVE_NOMEMORY, 'needs _testcapi.set_nomemory')
class AllocationFailureTest(unittest.TestCase):

  def testEveryAllocationFailure(self):
    proc = subprocess.run(
        [sys.executable, '-X', 'faulthandler', '-c', CHILD,
         json.dumps(list(Cases()))],
        capture_output=True, text=True, timeout=600)
    last_lines = '\n'.join(proc.stderr.splitlines()[-15:])
    self.assertEqual(0, proc.returncode, last_lines)


class DecodeArgumentsTest(unittest.TestCase):

  def testPadDefaultsToZero(self):
    body = '15M67FC000G?ufbE`FepT@3n00Sa'
    self.assertEqual(ais.decode(body, 0), ais.decode(body))

  def testPadOutOfRange(self):
    body = '15M67FC000G?ufbE`FepT@3n00Sa'
    for pad in (-1, 6, 9, 100):
      self.assertRaisesRegex(ais.DecodeError, 'pad must be 0 to 5',
                             ais.decode, body, pad)

  def testWrongArgumentTypes(self):
    self.assertRaises(ais.DecodeError, ais.decode, 15, 0)
    self.assertRaises(ais.DecodeError, ais.decode, '15M67FC000G', 'x')


if __name__ == '__main__':
  unittest.main()
