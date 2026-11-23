import re

known_bad = {
    'addressed',
    'app_id',
    'data',
    'eta',  # TODO(schwehr): Fix this.
    'radio',
    'regional',
    'reserved',
    'structured',
}

precision = 5.0

def TextToNumber(text):
  try:
    return float(text)
  except (TypeError, ValueError):
    return text


def IsNumber(value):
  if isinstance(value, float):
    return True
  if isinstance(value, int):
    return True
  return False


def DictDiff(a, b):
  """Compares two dictionaries. Intended to be used in a test to
  compare the actual return value from some function with a
  known-good value.

  Returns a dictionary with the following keys:

    removed: Dict of all key/value pairs in a but not in b.

    added: Dict of all key/value pairs in b but not in a.

    changed: Dict with all keys with different values in a and b.
    Values are pairs of the values from a and b.
  """

  def Compare(x, y):
    if x == y:
      return True
    x = TextToNumber(x)
    y = TextToNumber(y)
    if isinstance(x, str) and isinstance(y, str):
      # Collapse strings to just lower case a-z to avoid simple mismatches.
      new_x = re.sub(r'[^a-z]', r'', str(x).lower())
      new_y = re.sub(r'[^a-z]', r'', str(y).lower())
      if new_x == new_y:
        return True
    if IsNumber(x) and IsNumber(y):
      if abs(float(x) - float(y)) < precision:
        return True
    return False

  # TODO(redhog): Use sets and make this easier to follow.
  return {
      'removed': {key: a[key] for key in a
                  if key not in b and key not in known_bad},
      'changed': {key: (a[key], b[key]) for key in a
                  if key in b
                  and key not in known_bad
                  and not Compare(a[key], b[key])},
      'added': {key: b[key] for key in b
                if key not in a and key not in known_bad}
  }


# Bodies and fill bits of multi-line AIS messages that decode.
TWO_PART_MMSI = 367436030
TWO_PART_BODIES = (
    ('55NJPwP00001L@K?77@DhhU>0@5HU>222222220O18@374B<08CCm2EPH0kk', 0),
    ('UQCU8888880', 2))

OTHER_TWO_PART_MMSI = 366963230
OTHER_TWO_PART_BODIES = (
    ('55Mub7P00001L@;SO7TI8DDltqB222222222220O0000067<0620@jhQDTVG', 0),
    ('30H88888880', 2))

THREE_PART_BODIES = (
    ('81mg=5@0EP:4R40807P>0<D1>MNt00000f>FNVfnw7>6>FNU=?B5PD5HDPD8', 0),
    ('1Dd2J09jL08JArJH5P=E<D9@<5P<9>0`bMl42Q0d2Pc2T59CPCE@@?C54PD?', 0),
    ('d0@d0IqhH:Pah:U54PD?75D85Bf00', 0))


def VdmSentence(tot, num, seq, chan, body, fill, talker='AI'):
  """Build a VDM sentence with a valid checksum."""
  sentence = f'!{talker}VDM,{tot},{num},{seq},{chan},{body},{fill}*'
  checksum = 0
  for char in sentence[1:-1]:
    checksum ^= ord(char)
  return f'{sentence}{checksum:02X}'


def MultiPartLines(bodies, seq, chan, talker='AI'):
  """Build the VDM sentences for all parts of a message."""
  return [VdmSentence(len(bodies), num, seq, chan, body, fill, talker)
          for num, (body, fill) in enumerate(bodies, 1)]
