'''
If passed a file path, loads a csv file and expands any hex-encoded fields.
If passed a string, deserializes and prints content.
usage:
$> python base64_helper.py /path/to/any/csv_file_containing_hex_encoded_stuff
'''
import sys
import os
import csv
import binascii
import pprint
import json

def deserialize(s):
    if s.startswith('0x'):
        return binascii.unhexlify(s[2:]).decode()
    return s


def deserialize_file(filename, delimiter=','):
    """
    creates a new file with deserialized content for every previously base64 encoded value.
    """
    output_file = ''.join([os.path.splitext(filename)[0], '_expanded.csv'])
    with open(filename, 'r') as src:
        with open(output_file, 'w') as dst:
            reader = csv.reader(src, delimiter=delimiter)
            for tokens in reader:
                dst.write(delimiter.join([deserialize(t) for t in tokens]))
                dst.write('\n')
    return output_file

if __name__ == "__main__":
    f = sys.argv[1]
    if os.path.isfile(f):
        print('created:', deserialize_file(f))
    else:
        data = json.loads(deserialize(f))
        pp = pprint.PrettyPrinter(indent=4)
        pp.pprint(data)
