import itertools


_marker = object()


def minmax(iterable_or_value, *others, key=None, default=_marker):
  """Returns both the smallest and largest items from an iterable
  or from two or more arguments.

      >>> minmax([3, 1, 5])
      (1, 5)

      >>> minmax(4, 2, 6)
      (2, 6)

  If a *key* function is provided, it will be used to transform the input
  items for comparison.

      >>> minmax([5, 30], key=str)  # '30' sorts before '5'
      (30, 5)

  If a *default* value is provided, it will be returned if there are no
  input items.

      >>> minmax([], default=(0, 0))
      (0, 0)

  Otherwise ``ValueError`` is raised.

  This function makes a single pass over the input elements and takes care to
  minimize the number of comparisons made during processing.

  Note that unlike the builtin ``max`` function, which always returns the first
  item with the maximum value, this function may return another item when there are
  ties.

  This function is based on the
  `recipe <https://code.activestate.com/recipes/577916-fast-minmax-function>`__ by
  Raymond Hettinger.
  """
  iterable = (iterable_or_value, *others) if others else iterable_or_value

  it = iter(iterable)

  try:
    lo = hi = next(it)
  except StopIteration as exc:
    if default is _marker:
      raise ValueError(
        '`minmax()` argument is an empty iterable. '
        'Provide a `default` value to suppress this error.'
      ) from exc
    return default

  # Different branches depending on the presence of key. This saves a lot
  # of unimportant copies which would slow the "key=None" branch
  # significantly down.
  if key is None:
    for x, y in itertools.zip_longest(it, it, fillvalue=lo):
      if y < x:
        if y < lo:
          lo = y
        if hi < x:
          hi = x
      else:
        if x < lo:
          lo = x
        if hi < y:
          hi = y

  else:
    lo_key = hi_key = key(lo)

    for x, y in itertools.zip_longest(it, it, fillvalue=lo):
      x_key, y_key = key(x), key(y)

      if y_key < x_key:
        if y_key < lo_key:
          lo, lo_key = y, y_key
        if hi_key < x_key:
          hi, hi_key = x, x_key
      else:
        if x_key < lo_key:
          lo, lo_key = x, x_key
        if hi_key < y_key:
          hi, hi_key = y, y_key

  return lo, hi
