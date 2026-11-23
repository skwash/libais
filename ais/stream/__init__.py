# Based on ais_normalize.py from https://github.com/schwehr/noaadata

import collections
import sys
import traceback
import warnings

import ais
from ais import vdm
from ais.stream import checksum

warnings.warn(
  "The stream module is deprecated and will be removed in 1.0",
  FutureWarning,
  stacklevel=2
)


def ErrorPrinter(e,
                 stats,
                 verbose=False,
                 max_errors=None, # In % of total number of input lines
                 **kw):
  if max_errors != None and float(stats["error_num_total"]) / float(stats["line_num"]) * 100.0 > max_errors:
    raise TooManyErrorsError(**stats)
  if verbose:
    sys.stderr.write('%s\n' % e)


# def ErrorRaiser(e, stats, **kw):
#   raise e


class StreamError(Exception):

  description = 'Stream error'

  def __init__(self, **kw):
    self.kw = kw
    self.kw['description'] = self.description

  def __str__(self):
    return '%(description)s: %(line_num)s: %(line)s' % self.kw


class InvalidChecksumError(StreamError):
  description = 'Invalid checksum'


class InvalidChecksumInConstructedError(StreamError):
  description = 'Invalid checksum in constructed one-liner'


class NoStationFoundError(StreamError):
  description = 'No station found'


class TooFewFieldsError(StreamError):
  description = 'Too few fields'

  def __str__(self):
    return '%(description)s, got %(fields)s but needed 6: %(line_num)s: %(line)s' % self.kw


class MissingTimestampsError(StreamError):
  description = 'Timestamps missing'

  def __str__(self):
    return '%(description)s: %(line_num)s: %(line)s, parts: %(parts)s' % self.kw

class DifferingTimestampsError(StreamError):
  description = 'Timestamps not all the same'

  def __str__(self):
    return '%(description)s for %(timestamp)s: %(line_num)s: %(line)s, parts: %(parts)s' % self.kw

class OnlyMessageEndError(StreamError):
  description = 'Do not have the preceding packets for'

  def __str__(self):
    return '%(description)s for %(bufferSlot)s:\n%(line)s\n' % self.kw


class OutOfSequenceError(StreamError):
  description = 'Part out of sequence'

  def __str__(self):
    return '%(description)s (%(problem)s) for %(bufferSlot)s: %(line_num)s: %(line)s' % self.kw


class ExpiredMessageError(StreamError):
  description = 'Incomplete message expired'

  def __str__(self):
    return '%(description)s for %(bufferSlot)s: %(line_num)s' % self.kw


class TooManyIncompleteMessagesError(StreamError):
  description = 'Too many incomplete messages'

  def __str__(self):
    return '%(description)s, dropped %(bufferSlot)s: %(line_num)s' % self.kw


class UnfinishedMessagesError(StreamError):
  description = 'Unfinished messages at end of file'

  def __str__(self):
    return '%(description)s:\n%(buffers)s\n' % self.kw


class TooManyErrorsError(StreamError):
  description = 'Too many errors'

  def __str__(self):
    res = dict(self.kw)
    res['error_lines'] = ""
    if 'error_num' in res:
      res['error_lines'] = "\n" + "\n".join(f"  {error}: {num}" for error, num in res['error_num'].iteritems())
    return '%(description)s: %(error_num_total)s errors in %(line_num)s lines:%(error_lines)s' % res


def parseTagBlock(line):
  if not line.startswith("\\"):
    return {}, line
  tagblock, line = line[1:].split("\\", 1)
  tagblock, checksum = tagblock.rsplit("*", 1)

  tags = {}
  for field in tagblock.split(","):
    key, value = field.split(":")

    if key == 'c':
      key = 'timestamp'
      value = int(value)
      # This can be either seconds or milliseconds...
      if value > 40000000000:
        value = value / 1000.0
    elif key == 'n':
      key = 'line_count'
      value = int(value)
    elif key == 'r':
      key = 'relative_time'
      value = int(value)
    elif key == 'd':
      key = 'destination'
    elif key == 's':
      key = 'station'
    elif key == 't':
      key = 'text'
    elif key == 'g':
      key = 'group'
      value = dict(zip(["sentence", "groupsize", "id"],
                       [int(part) for part in value.split("-")]))

    tags["tagblock_" + key] = value
  return tags, line


def add_error_to_stats(e, stats):
  if "error_num_total" not in stats:
    stats["error_num_total"] = 0
  stats["error_num_total"] += 1
  if "error_num" not in stats:
     stats["error_num"] = {}
  name = getattr(e, "description", getattr(e, "message", str(type(e))))
  if name not in stats["error_num"]:
     stats["error_num"][name] = 0
  stats["error_num"][name] += 1


def normalize(nmea=sys.stdin,
              uscg=True,
              validate_checksum=True,
              allow_unknown=False,
              window=2,
              ignore_tagblock_station=False,
              treat_ab_equal=False,
              pass_invalid_checksums=False,
              allow_missing_timestamps=False,
              errorcb=ErrorPrinter,
              stats=None,
              max_groups=1000,
              max_age_lines=10000,
              **kw):
  """Assemble multi-line messages

  The parts of a multi-line message must come in order with the same
  sentence total.  A part that breaks these rules causes the incomplete
  message to be dropped and reported.

  Args:
    nmea: iterator of lines to read
    window: number of seconds to allow the later parts of a multiline message to span
    max_groups: maximum number of incomplete messages to keep
    max_age_lines: number of input lines after its first part that an
      incomplete message can wait for its other parts
  """

  # Partial messages by station, oldest first, so that they can be reassembled.
  buffers = collections.OrderedDict()
  if stats is None: stats={}
  stats['line_num'] = stats.pop('line_num', 0)
  stats['error_num_total'] = stats.pop('error_num_total', 0)
  stats['invalid_checksums'] = stats.pop('invalid_checksums', 0)

  def report_error(e):
    add_error_to_stats(e, stats)
    errorcb(e, stats, **kw)

  if not uscg:
    report_error('Need to make a faster version that does not worry about the extra args and stations dict')
    assert False

  for idx, origline in enumerate(nmea):
    while buffers:
      oldSlot, oldParts = next(iter(buffers.items()))
      if idx - oldParts[0]['index'] <= max_age_lines:
        break
      del buffers[oldSlot]
      report_error(ExpiredMessageError(line_num=stats["line_num"],
                                       bufferSlot=oldSlot, parts=oldParts))

    try:
      tagblock, line = parseTagBlock(origline)

      line = line.strip() + '\n'  # Get rid of DOS issues.
      stats["line_num"] += 1
      if len(line) < 7 or line[3:6] not in ('VDM', 'VDO'):
        yield tagblock, line, origline
        continue

      if validate_checksum and not checksum.isChecksumValid(line):
        stats["invalid_checksums"] += 1
        report_error(InvalidChecksumError(line_num=stats["line_num"], line=line.strip()))
        if not pass_invalid_checksums:
          continue

      fields = line.split(',')

      if len(fields) < 6:
        report_error(TooFewFieldsError(line_num=stats["line_num"],
                                  line=line.strip(),
                                  fields=len(fields)))
        continue

      # Total NMEA lines that compose this message [1..9].
      totNumSentences = int(fields[1])
      sentenceNum = int(fields[2])  # Message sequence number 1..9 (packetNum)
      if 1 == totNumSentences:
        problem = vdm.CheckNextPart(sentenceNum, 1)
        if problem:
          report_error(OutOfSequenceError(line_num=stats["line_num"],
                                          line=line.strip(),
                                          bufferSlot=None,
                                          problem=problem))
          continue
        # A single line needs no work, so pass it along.
        yield tagblock, line, origline
        continue

      payload = fields[5]  # AIS binary data encoded in whacky ways
      timestamp = fields[-1].strip()   # Seconds since Epoch UTC.  Always the last field

      station = None  # USCG Receive Stations        # if None==station:
      for i in range(len(fields)-1, 5, -1):
        if len(fields[i]) and fields[i][0] in ('r', 'b'):
          station = fields[i]
          break  # Found it so ditch the for loop.

      if ignore_tagblock_station:
        tagblock_station = None
      else:
        tagblock_station = tagblock.get('tagblock_station', None)

      if station is None and allow_unknown:
        station = 'UNKNOWN'

      if station is None and tagblock_station is None:
        report_error(NoStationFoundError(line_num=stats["line_num"], line=line.strip()))
        continue

      bufferSlot = (tagblock_station, station, fields[3])  # seqId and Channel make a unique stream

      if not treat_ab_equal:
        bufferSlot += (fields[4],)  # channel id

      parts = buffers.get(bufferSlot)
      if sentenceNum == 1 or parts is None:
        problem = vdm.CheckNextPart(sentenceNum, totNumSentences)
      else:
        problem = vdm.CheckNextPart(sentenceNum, totNumSentences,
                                    len(parts), parts[0]['total'])
      if problem:
        if parts is None and 1 < sentenceNum <= totNumSentences:
          report_error(OnlyMessageEndError(line=line, bufferSlot=bufferSlot))
        else:
          buffers.pop(bufferSlot, None)
          report_error(OutOfSequenceError(line_num=stats["line_num"],
                                          line=line.strip(),
                                          bufferSlot=bufferSlot,
                                          problem=problem))
        continue

      newPacket = {"payload": payload,
                   "timestamp": timestamp,
                   "tagblock": tagblock,
                   "origline": origline,
                   "index": idx,
                   "total": totNumSentences}
      if sentenceNum == 1:
        if parts is not None:
          del buffers[bufferSlot]  # Overwrite any partials
        elif len(buffers) >= max_groups:
          oldSlot, oldParts = buffers.popitem(last=False)
          report_error(TooManyIncompleteMessagesError(line_num=stats["line_num"],
                                                      bufferSlot=oldSlot,
                                                      parts=oldParts))
        buffers[bufferSlot] = [newPacket]
        continue

      parts.append(newPacket)
      if totNumSentences == sentenceNum:
        # Finished a message
        del buffers[bufferSlot]  # Clear out the used packets to save memory.

        # Sanity check
        ok = True
        ts1 = None
        for part in parts:
          try:
            ts1 = float(part['timestamp'])
            ts2 = float(timestamp)
          except ValueError:
            try:
              ts1 = float(part['tagblock']['tagblock_timestamp'])
              ts2 = float(tagblock['tagblock_timestamp'])
            except:
              if allow_missing_timestamps:
                ts1 = 0
                ts2 = 0
              else:
                report_error(MissingTimestampsError(line_num=stats["line_num"],
                                                    line=line.strip(),
                                                    timestamp=timestamp, parts=parts))
                ok = False
                break
          if ts1 > ts2+window or ts1 < ts2-window:
            report_error(DifferingTimestampsError(line_num=stats["line_num"],
                                                  line=line.strip(),
                                                  timestamp=timestamp, parts=parts))
            ok = False
            break
        if not ok:
          continue

        payload = ''.join([p['payload'] for p in parts])
        tagblock = {}
        for p in reversed(parts):
          tagblock.update(p['tagblock'])

        # Try to mirror the packet as much as possible... same seqId and channel.
        checksumed_str = ','.join((fields[0], '1,1', fields[3], fields[4],
                                   payload, fields[6].split('*')[0]+'*'))
        if ts1 == 0:
            # allowed missing timestamp and it is missing
            if len(fields[7:-1]) == 0:
              out_str = checksumed_str + checksum.checksumStr(checksumed_str)
            else:
              out_str = checksumed_str + checksum.checksumStr(checksumed_str) +',' + ','.join(fields[7:-1])
        else:
          out_str = checksumed_str + checksum.checksumStr(checksumed_str) +',' + ','.join(fields[7:])

        if not checksum.isChecksumValid(out_str):
          report_error(InvalidChecksumInConstructedError(line_num=stats["line_num"], line=line.strip()))

        out_str = out_str.strip()+'\n'  # FIX: Why do I have to do this last strip?
        origstr = ''.join([p['origline'] for p in parts])

        yield tagblock, out_str, origstr

        continue
    except TooManyErrorsError:
      raise
    except Exception as inst:
      report_error(inst)

  if buffers:
    report_error(UnfinishedMessagesError(buffers=dict(buffers)))


def decode(nmea=sys.stdin,
           errorcb=ErrorPrinter,
           keep_nmea=False,
           stats=None,
           **kw):
  """Decodes a stream of AIS messages. Takes the same arguments as normalize."""

  if stats is None: stats={}

  def report_error(e):
    add_error_to_stats(e, stats)
    errorcb(e, stats, **kw)

  for tagblock, line, origline in normalize(nmea=nmea, errorcb=errorcb, stats=stats, **kw):
    try:
      body = ''.join(line.split(',')[5])
      pad = int(line.split('*')[0][-1])
      res = ais.decode(body, pad)
      res.update(tagblock)
      if keep_nmea:
        res['nmea'] = origline
      yield res
    except TooManyErrorsError:
      raise
    except Exception as e:
      report_error(e)
