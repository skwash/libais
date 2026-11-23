"""Manage a stream of NMEA TAG block messages.

The TAG (Transport, Annotate, and Group) Block messages are defined in NMEA 4.0
section 7.

Some providers violate the NMEA standard by using lower case letters in NMEA
checksums.  This module forces checksums to always be upper case.

TODO(schwehr): Catch a wider variety of incomplete groups.
TODO(schwehr): Compute running stats in the queue.
"""

import collections
import hashlib
import logging
import queue as Queue
import re

import ais
from ais import nmea
from ais import nmea_messages
from ais import util
from ais import vdm

logger = logging.getLogger('libais')

# Added a decimal value to time beyond the normal TAG BLOCK spec.
TAG_BLOCK_RE = re.compile(r"""
(\\
(?P<metadata>(
  (
    c:(?P<time>\d{10,15}(\.\d*)?) |  # Receiver Unix time in seconds or millisec
    d:(?P<dest>[^*,\\]{1,15}) |  # Destination
    g:(?P<group>(?P<sentence_num>\d)-(?P<sentence_tot>\d)-(?P<group_id>\d+)) |
    n:(?P<line_num>\d+) |  # Line count
    q:(?P<quality>\w) |  # Orbcomm specific character code
    r:(?P<rel_time>\d+) | # Relative time
    s:(?P<rcvr>[^$*,!\\]{1,15}) |  # Source / station
    t:(?P<text>[^$*,!\\]+) |  # Text string
    T:(?P<text_date>[^$*,!\\]+)  # Orbcomm human readable date
  )[,]?
)+([*](?P<tag_checksum>[0-9A-Fa-f]{2}))?)
\\)(?P<payload>.*)
""", re.VERBOSE)

NUMERIC_FIELDS = (
  'dest',
  'group',
  'group_id',
  'line_num',
  'rel_time',
  'sentence_num',
  'sentence_tot',
  'time'
)


def Parse(data):
  """Unpack a TAG Block line or return None.

  Makes sure that the line matches the regex and the checksum matches.

  Args:
    data: Line of text or a dict from at TAG_BLOCK_RE.

  Returns:
    A NMEA TAG Block dict or None if the line would not parse or has
    an invalid checksum.
  """
  if isinstance(data, str):
    try:
      result = TAG_BLOCK_RE.search(data).groupdict()
    except AttributeError:
      return
  elif isinstance(data, dict):
    result = data
  else:
    return

  result.update({k: util.MaybeToNumber(v)
                 for k, v in result.items() if k in NUMERIC_FIELDS})

  actual = nmea.Checksum(result['metadata'])
  expected = result['tag_checksum'].upper()
  if actual != expected:
    return

  return result


class TagQueue(Queue.Queue):
  """Aggregate TAG Block group messages into logical units.

  This queue tracks message lines with the "g" group TAG and finds matching
  lines.  It will pass single line messages straight through.

  A group is keyed by its source ("s" field) and its group id, because each
  source counts its group ids independently.  Often only the first part of a
  group has an "s" field.  A later part without one matches the single
  incomplete group with the same id.  If more than one group can match, the
  queue drops the part.

  Each part of a group must have the next sentence number and the same total
  as the first part.  If not, the queue drops the group.  The queue also drops
  incomplete groups that are too old or too many.  Age is a count of the lines
  given to put, because the "c" time field is optional.

  Attributes:
    groups: OrderedDict of incomplete groups, oldest first.  The key is
      (source, group_id) and the source is None if the first part has no "s"
      field.
    stats: dict of counters for the groups and lines that the queue dropped.
  """

  DEFAULT_MAX_AGE_LINES = 1000
  DEFAULT_MAX_GROUPS = 500

  STAT_KEYS = (
      'ambiguous_lines',  # Part that matches more than one group.
      'evicted_by_age',
      'evicted_by_cap',
      'orphan_lines',  # Part that has no first part.
      'out_of_sequence',  # Group dropped for a bad sentence number or total.
      'restarted',  # Incomplete group replaced by a new first part.
  )

  def __init__(self, max_age_lines=DEFAULT_MAX_AGE_LINES,
               max_groups=DEFAULT_MAX_GROUPS):
    """Create an empty queue.

    Args:
      max_age_lines: int or None, The number of lines after its first part
        that the queue keeps an incomplete group.  None removes the limit.
      max_groups: int or None, The maximum number of incomplete groups.  When
        a new group starts at the limit, the queue drops the oldest group.
        None removes the limit.

    Raises:
      ValueError: If a limit is not None or a positive int.
    """
    for name, value in (('max_age_lines', max_age_lines),
                        ('max_groups', max_groups)):
      if value is not None and (not isinstance(value, int) or value < 1):
        raise ValueError(
            '%s must be None or a positive int: %r' % (name, value))
    self.max_age_lines = max_age_lines
    self.max_groups = max_groups
    self.groups = collections.OrderedDict()
    self.stats = dict.fromkeys(self.STAT_KEYS, 0)
    self.line_num = 0
    # line_num can come from the caller, so it is not a reliable clock.
    self._line_count = 0
    self._first_line_counts = {}
    self._keys_by_id = {}
    Queue.Queue.__init__(self)

  def put(self, line, line_num=None):
    if line_num is not None:
      self.line_num = line_num
    else:
      self.line_num += 1

    self._line_count += 1
    self._EvictOld()

    line = line.rstrip()
    match = Parse(line)

    if not match:
      Queue.Queue.put(self, {
          'line_nums': [self.line_num],
          'lines': [line],
      })
      return

    time = util.MaybeToNumber(match['time'])

    if not match['group']:
      msg = {
          'line_nums': [self.line_num],
          'lines': [line],
          'matches': [match],
          'times': [time],
      }
      decoded = DecodeTagSingle(msg)
      if decoded:
        msg['decoded'] = decoded
      else:
        logger.info('Unable to decode. Passing without decoded block.')
        decoded = nmea_messages.DecodeLine(match['payload'])
        if decoded:
          msg['decoded'] = decoded
        else:
          logger.info('No NMEA match for line: %d, %s', self.line_num, line)
      Queue.Queue.put(self, msg)
      return

    sentence_num = int(match['sentence_num'])
    sentence_total = int(match['sentence_tot'])
    group_id = int(match['group_id'])
    source = match['rcvr']

    if sentence_num == 1 and sentence_total >= 1:
      key = (source, group_id)
      if key in self.groups:
        self._DropGroup(key, 'restarted')
      entry = {
          'line_nums': [self.line_num],
          'lines': [line],
          'matches': [match],
          'times': [time],
      }
      if sentence_total == 1:
        self._Emit(entry)
      else:
        self._AddGroup(key, entry)
      return

    key = self._FindGroup(source, group_id, line)
    if key is None:
      return

    entry = self.groups[key]
    expected_total = int(entry['matches'][0]['sentence_tot'])
    expected_num = len(entry['lines']) + 1
    if sentence_total != expected_total or sentence_num != expected_num:
      logger.error('Out of sequence group part: expected %d-%d, got %d-%d '
                   'in line %d, %s', expected_num, expected_total,
                   sentence_num, sentence_total, self.line_num, line)
      self._DropGroup(key, 'out_of_sequence')
      return

    entry['line_nums'].append(self.line_num)
    entry['lines'].append(line)
    entry['matches'].append(match)
    entry['times'].append(time)

    if sentence_num != sentence_total:
      # Found the middle part of a message.
      return

    # Found the final message in a group.
    self._RemoveGroup(key)
    self._Emit(entry)

  def _Emit(self, entry):
    decoded = DecodeTagMultiple(entry)
    if decoded:
      entry['decoded'] = decoded
    else:
      logger.info('Unable to process: %s', entry)
    Queue.Queue.put(self, entry)

  def _FindGroup(self, source, group_id, line):
    """Find the key of the incomplete group for a later part, or None."""
    if source is not None and (source, group_id) in self.groups:
      return (source, group_id)
    candidates = [key for key in self._keys_by_id.get(group_id, ())
                  if source is None or key[0] is None]
    if len(candidates) == 1:
      return candidates[0]
    if candidates:
      logger.error('More than one group matches line %d.  Dropping: %s',
                   self.line_num, line)
      self.stats['ambiguous_lines'] += 1
    else:
      logger.error('group_id not in groups: %d', group_id)
      self.stats['orphan_lines'] += 1
    return None

  def _AddGroup(self, key, entry):
    if self.max_groups is not None:
      while len(self.groups) >= self.max_groups:
        self._DropGroup(next(iter(self.groups)), 'evicted_by_cap')
    self.groups[key] = entry
    self._first_line_counts[key] = self._line_count
    self._keys_by_id.setdefault(key[1], set()).add(key)

  def _RemoveGroup(self, key):
    entry = self.groups.pop(key)
    del self._first_line_counts[key]
    keys = self._keys_by_id[key[1]]
    keys.discard(key)
    if not keys:
      del self._keys_by_id[key[1]]
    return entry

  def _DropGroup(self, key, reason):
    entry = self._RemoveGroup(key)
    self.stats[reason] += 1
    logger.info('Dropped incomplete group %s (%s): %s',
                key, reason, entry['lines'])

  def _EvictOld(self):
    if self.max_age_lines is None:
      return
    oldest_allowed = self._line_count - self.max_age_lines
    # Groups are in the order of their first line, so the oldest is first.
    while self.groups:
      key = next(iter(self.groups))
      if self._first_line_counts[key] >= oldest_allowed:
        break
      self._DropGroup(key, 'evicted_by_age')


def DecodeTagSingle(tag_block_message):
  """Decode the payload of one (but NOT more) NMEA TAG block.

  Args:
    tag_block_message: dict, A dictionary with a matches entry.

  Returns:
    A message dictionary compatible with vdm.BareQueue.
  """
  line = tag_block_message['matches'][0]['payload']
  match = vdm.Parse(line)
  if not match:
    logger.info('Single line NMEA TAG block decode failed for: %s',
                 tag_block_message)
    return

  sentence_total = int(match['sen_tot'])
  if sentence_total != 1:
    logger.error('Multi-line message? %s', tag_block_message)
    return

  body = match['body']
  fill_bits = int(match['fill_bits'])
  try:
    decoded = ais.decode(body, fill_bits)
  except ais.DecodeError as error:
    logger.error('Unable to decode: %s', error)
    return

  decoded['md5'] = hashlib.md5(body.encode('utf-8')).hexdigest()
  return decoded


def DecodeTagMultiple(tag_block_message):
  """Decode a TAG block message that spans multiple lines."""
  payloads = [msg['payload'] for msg in tag_block_message['matches']]

  q = vdm.BareQueue()
  for line in vdm.VdmLines(payloads):
    q.put(line)
  if q.qsize() != 1:
    logger.info('Error: Should get just one message decoded from this: %s',
                 tag_block_message)
    return
  msg = q.get()
  return msg['decoded']
