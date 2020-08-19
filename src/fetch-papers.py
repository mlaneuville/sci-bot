''' Script to iterate over all json and try to obtain pdf for it
'''
import json
import os
import random
import time

from article import Article

if __name__ == '__main__':
    
    timestamp = time.time()
    previous = 0
    for (dirpath, dirnames, filenames) in os.walk('pdf/'):
        if len(filenames) == 0:
            continue
        random.shuffle(filenames)
        for fname in filenames:
            if fname.endswith('.json'):
                if os.path.isfile(os.path.join(dirpath, fname[:-5]+'.pdf')):
                    continue

                with open(os.path.join(dirpath, fname), 'r') as f:
                    dat = json.load(f)
                    doi = dat['doi'][0]
                    print(doi)

                dt = random.randint(2,10)
                while timestamp < previous + dt:
                    time.sleep(1)
                    timestamp = time.time()
                
                target = Article(doi)
                previous = time.time()
                print()
