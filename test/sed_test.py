import subprocess
import tempfile
import os
import sys

data = """hi there this
is a large file
with lots of lines
KEYWORD
\0 and some control chars \a in second half\0\0\0 and possibly no endlines"""

data_path = os.path.join(os.path.dirname(__file__), "data", "sed_data.txt")

def test_sed_trim_front():
    out = subprocess.run("sed -n /KEYWORD/q;p".split(),stdin=open(data_path),stdout=subprocess.PIPE)
    expected = b'hi there this\nis a large file\nwith lots of lines\n'
    assert out.stdout == expected, out.stdout

def test_sed_trim_back():
    out = subprocess.run("sed -n '/KEYWORD/,$p' | tail -n +2", shell=True,stdin=open(data_path),stdout=subprocess.PIPE)
    expected = b'\x00 and some control chars \x07 in second half\x00\x00\x00 and possibly no endlines'
    assert out.stdout == expected, out.stdout

if __name__ == "__main__":
    test_sed_trim_back()
