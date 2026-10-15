import sys
assert __name__ == '__main__' and __spec__ is None and __package__ == ''
assert sys.argv[0] == __file__ and sys.argv[1:] == ['argument']
print('frozen-main')
