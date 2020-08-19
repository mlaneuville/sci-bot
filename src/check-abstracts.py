''' Script to check if all json have an abstract included and if not, why not.
'''
import json
import os
import time

from pprint import pprint

from article import Article

if __name__ == '__main__':
    
    timestamp = time.time()
    previous = 0
    for (dirpath, dirnames, filenames) in os.walk('pdf/'):
        for fname in filenames:
            if fname.endswith('.json'):
                with open(os.path.join(dirpath, fname), 'r') as f:
                    dat = json.load(f)
                    doi = dat['doi'][0]
                if dat['abstract'] is None:
                    pprint(dat)
