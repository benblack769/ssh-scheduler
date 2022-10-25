'''
utility script used by better_basic_run
'''
import sys
import shutil

CHUNK_SIZE = 2**20
keyword = sys.argv[1]

line = sys.stdin.readline()
found_line = False
while line:
    if keyword in line:
        chunk = sys.stdin.read(CHUNK_SIZE)
        while chunk:
            chunk = sys.stdin.read(CHUNK_SIZE)
        break
    sys.stdout.write(line)
    sys.stdout.flush()
    
    line = sys.stdin.readline()
