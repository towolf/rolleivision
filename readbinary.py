import sys

def compare(lst):
      return lst[1:] == lst[:-1]

def comparebytearrays(*args):
    for i in xrange(len(args[0])):
        items = [array[i] for array in args]
        if not compare(items):

            sys.stdout.write('%08d: ' % i)
            for byte in items:
                sys.stdout.write('%02x ' % byte)

            sys.stdout.write('    ')

            for byte in items:
                sys.stdout.write('%s ' % chr(byte).decode('cp437'))

            sys.stdout.write('\n')
            sys.stdout.flush()
