# pathglob

A small glob style path matching kernel written with the Python standard
library only. A pattern supports the separator, the single star, the double
star, the question mark, character classes with ranges and complement, and
backslash escapes; several patterns can be applied to a list of paths at once,
in order and without repetitions. The kernel lives in `pathglob/core.py`.

## Running the tests

From the project root:

    python3 -m unittest discover -s tests -v
