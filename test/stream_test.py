"""Tests for ais.stream."""

import unittest
import warnings

from ais import nmea

from . import testutils

with warnings.catch_warnings():
  warnings.simplefilter('ignore', FutureWarning)
  from ais import stream

TIME = 1429287224


def UscgLines(bodies, seq, chan, station='r003669945', time=TIME):
  return [line + f',{station},{time}'
          for line in testutils.MultiPartLines(bodies, seq, chan)]


def TagLines(bodies, seq, chan, station='rSTA', time=TIME):
  tag = f'\\s:{station},c:{time}*'
  tag += nmea.Checksum(tag + '00')
  return [f'{tag}\\{line}'
          for line in testutils.MultiPartLines(bodies, seq, chan)]


class StreamTestCase(unittest.TestCase):

  def setUp(self):
    self.errors = []

  def ErrorCallback(self, error, stats, **kw):
    self.errors.append(error)

  def Normalize(self, lines, **kw):
    return list(stream.normalize(lines, errorcb=self.ErrorCallback, **kw))

  def Decode(self, lines, **kw):
    return list(stream.decode(lines, errorcb=self.ErrorCallback, **kw))

  def ErrorTypes(self):
    return [type(error) for error in self.errors]


class NormalizeTest(StreamTestCase):

  def testTextPassesThrough(self):
    self.assertEqual(self.Normalize(['hello\n']), [({}, 'hello\n', 'hello\n')])
    self.assertEqual(self.errors, [])

  def testSingleLine(self):
    line = '!SAVDM,1,1,,B,K8VSqb9LdU28WP8<,0*17,rMySat,1218999946'
    self.assertEqual(self.Normalize([line]), [({}, line + '\n', line)])
    self.assertEqual(self.errors, [])

  def testTwoLineUscg(self):
    lines = UscgLines(testutils.TWO_PART_BODIES, 7, 'A')
    body = ''.join(body for body, _ in testutils.TWO_PART_BODIES)
    expected = (testutils.VdmSentence(1, 1, 7, 'A', body, 2) +
                f',r003669945,{TIME}\n')
    self.assertEqual(self.Normalize(lines), [({}, expected, ''.join(lines))])
    self.assertEqual(self.errors, [])

  def testThreeLineTagBlock(self):
    lines = TagLines(testutils.THREE_PART_BODIES, '', 'B')
    result = self.Normalize(lines)
    self.assertEqual(len(result), 1)
    tagblock, line, _ = result[0]
    self.assertEqual(tagblock['tagblock_station'], 'rSTA')
    self.assertEqual(tagblock['tagblock_timestamp'], TIME)
    body = ''.join(body for body, _ in testutils.THREE_PART_BODIES)
    self.assertEqual(line.split(',')[:6], ['!AIVDM', '1', '1', '', 'B', body])
    self.assertEqual(self.errors, [])

  def testMissingMiddlePartIsNotJoined(self):
    first, _, last = UscgLines(testutils.THREE_PART_BODIES, 5, 'A')
    self.assertEqual(self.Normalize([first, last]), [])
    self.assertEqual(self.ErrorTypes(), [stream.OutOfSequenceError])
    self.assertIn('expected sentence 2, got 3', str(self.errors[0]))

  def testOutOfOrderPartsAreNotJoined(self):
    first, middle, last = UscgLines(testutils.THREE_PART_BODIES, 5, 'A')
    self.assertEqual(self.Normalize([first, last, middle]), [])
    self.assertEqual(
        self.ErrorTypes(),
        [stream.OutOfSequenceError, stream.OnlyMessageEndError])

  def testDuplicateMiddlePartIsNotJoined(self):
    first, middle, last = TagLines(testutils.THREE_PART_BODIES, 5, 'A')
    self.assertEqual(self.Normalize([first, middle, middle, middle, last]), [])
    self.assertEqual(
        self.ErrorTypes(),
        [stream.OutOfSequenceError] + [stream.OnlyMessageEndError] * 2)

  def testSentenceTotalMismatch(self):
    first = UscgLines(testutils.THREE_PART_BODIES, 5, 'A')[0]
    last = UscgLines(testutils.TWO_PART_BODIES, 5, 'A')[1]
    self.assertEqual(self.Normalize([first, last]), [])
    self.assertEqual(self.ErrorTypes(), [stream.OutOfSequenceError])
    self.assertIn('does not match', str(self.errors[0]))

  def testSentenceNumberOutOfRange(self):
    body, fill = testutils.TWO_PART_BODIES[1]
    lines = [testutils.VdmSentence(tot, num, 3, 'B', body, fill) + ',rSTA,1'
             for tot, num in ((2, 0), (2, 3), (1, 2))]
    self.assertEqual(self.Normalize(lines), [])
    self.assertEqual(self.ErrorTypes(), [stream.OutOfSequenceError] * 3)

  def testOrphanParts(self):
    _, middle, last = UscgLines(testutils.THREE_PART_BODIES, 5, 'A')
    self.assertEqual(self.Normalize([middle, last]), [])
    self.assertEqual(self.ErrorTypes(), [stream.OnlyMessageEndError] * 2)

  def testNewFirstPartRestartsMessage(self):
    first, last = UscgLines(testutils.TWO_PART_BODIES, 5, 'A')
    result = self.Normalize([first, first, last])
    self.assertEqual(len(result), 1)
    self.assertEqual(result[0][2], first + last)
    self.assertEqual(self.errors, [])

  def testTwoChannelsWithTheSameSequenceId(self):
    a_first, a_last = UscgLines(testutils.TWO_PART_BODIES, 7, 'A')
    b_first, b_last = UscgLines(testutils.OTHER_TWO_PART_BODIES, 7, 'B')
    result = self.Normalize([a_first, b_first, a_last, b_last])
    self.assertEqual([line.split(',')[4] for _, line, _ in result], ['A', 'B'])
    self.assertEqual(self.errors, [])

  def testIncompleteMessagesExpire(self):
    first, last = UscgLines(testutils.TWO_PART_BODIES, 7, 'A')
    result = self.Normalize([first] + ['text\n'] * 4 + [last], max_age_lines=5)
    self.assertEqual([line[:6] for _, line, _ in result],
                     ['text\n'] * 4 + ['!AIVDM'])
    self.assertEqual(self.errors, [])

    result = self.Normalize([first] + ['text\n'] * 5 + [last], max_age_lines=5)
    self.assertEqual([line for _, line, _ in result], ['text\n'] * 5)
    self.assertEqual(
        self.ErrorTypes(),
        [stream.ExpiredMessageError, stream.OnlyMessageEndError])

  def testIncompleteMessagesHaveALimit(self):
    lines = [UscgLines(testutils.TWO_PART_BODIES, 7, 'A', station=f'r{i}')[0]
             for i in range(5000)]
    self.assertEqual(self.Normalize(lines), [])
    self.assertEqual(self.ErrorTypes()[:-1],
                     [stream.TooManyIncompleteMessagesError] * 4000)
    unfinished = self.errors[-1]
    self.assertIsInstance(unfinished, stream.UnfinishedMessagesError)
    self.assertEqual(len(unfinished.kw['buffers']), 1000)

  def testMaxGroups(self):
    lines = [TagLines(testutils.TWO_PART_BODIES, 7, 'A', station=f'r{i}')[0]
             for i in range(100)]
    self.assertEqual(self.Normalize(lines, max_groups=10), [])
    buffers = self.errors[-1].kw['buffers']
    self.assertEqual([slot[0] for slot in buffers],
                     [f'r{i}' for i in range(90, 100)])

  def testDifferingTimestamps(self):
    first = UscgLines(testutils.TWO_PART_BODIES, 7, 'A', time=TIME)[0]
    last = UscgLines(testutils.TWO_PART_BODIES, 7, 'A', time=TIME + 10)[1]
    self.assertEqual(self.Normalize([first, last]), [])
    self.assertEqual(self.ErrorTypes(), [stream.DifferingTimestampsError])

  def testNoStation(self):
    first = testutils.MultiPartLines(testutils.TWO_PART_BODIES, 7, 'A')[0]
    self.assertEqual(self.Normalize([first]), [])
    self.assertEqual(self.ErrorTypes(), [stream.NoStationFoundError])

  def testInvalidChecksum(self):
    line = '!AIVDM,1,1,,B,K8VSqb9LdU28WP8<,0*00,rMySat,1218999946'
    self.assertEqual(self.Normalize([line]), [])
    self.assertEqual(self.ErrorTypes(), [stream.InvalidChecksumError])

  def testStats(self):
    stats = {}
    first, _, last = UscgLines(testutils.THREE_PART_BODIES, 5, 'A')
    self.Normalize(['text\n', first, last], stats=stats)
    self.assertEqual(stats['line_num'], 3)
    self.assertEqual(stats['error_num_total'], 1)
    self.assertEqual(stats['error_num'], {'Part out of sequence': 1})


class DecodeTest(StreamTestCase):

  def testSingleLine(self):
    line = '!SAVDM,1,1,,B,K8VSqb9LdU28WP8<,0*17,rMySat,1218999946'
    msgs = self.Decode([line], keep_nmea=True)
    self.assertEqual(len(msgs), 1)
    self.assertEqual(msgs[0]['id'], 27)
    self.assertEqual(msgs[0]['mmsi'], 577305000)
    self.assertEqual(msgs[0]['nmea'], line)
    self.assertEqual(self.errors, [])

  def testMultiLine(self):
    lines = (TagLines(testutils.TWO_PART_BODIES, 1, 'A') +
             UscgLines(testutils.THREE_PART_BODIES, 2, 'B'))
    msgs = self.Decode(lines)
    self.assertEqual([msg['id'] for msg in msgs], [5, 8])
    self.assertEqual(msgs[0]['mmsi'], testutils.TWO_PART_MMSI)
    self.assertEqual(msgs[0]['tagblock_station'], 'rSTA')
    self.assertEqual(self.errors, [])

  def testBadPartsAreNotDecoded(self):
    first, _, last = UscgLines(testutils.THREE_PART_BODIES, 5, 'A')
    self.assertEqual(self.Decode([first, last]), [])
    self.assertEqual(self.ErrorTypes(), [stream.OutOfSequenceError])


if __name__ == '__main__':
  unittest.main()
