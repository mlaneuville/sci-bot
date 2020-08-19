'''
'''

import datetime
import json
import logging
import numpy as np
import os
import re
import requests
import subprocess
import time

import ads

from bs4 import BeautifulSoup
from grobidclient import grobidclient
from habanero import Crossref
from textwrap import fill
from sklearn.feature_extraction.text import TfidfVectorizer

HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) \
           AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'}

logging.basicConfig()
logger = logging.getLogger()
logger.setLevel(logging.INFO)

cr = Crossref()

class Article:
    def __init__(self, doi):
        self.doi = doi
        self.basedir = 'pdf/'+'/'.join(doi.split('/')[:-1]) + '/'
        logger.info("Initializing paper %s" %self.doi)
        p = subprocess.run(['mkdir', '-p', self.basedir])

        if not self._hasfile('.json'):
            logger.info("No json, fetching info from ADS...")
            self.information = self._fetchinformation()
            if self.information is None:
                return
        else:
            with open(self.basedir+self.doi.split('/')[-1]+'.json', 'r') as f:
                self.information = json.load(f)
                logger.info("json loaded from file...")

            last = datetime.datetime.strptime(self.information['timestamp'], "%Y-%m-%dT%H:%M:%S.%f")
            if datetime.datetime.now() - last > datetime.timedelta(days=30):
                logger.info("json too old, fetching new one...")
                self.information = self._fetchinformation()

        if not self._hasfile('.pdf'):
            logger.info("No pdf, trying to download...")
            self._download()

        print(self.information['first_author'], self.information['year'])
        print(self.information['title']) 


        if self._hasfile('.pdf') and not self._hasfile('.tei.xml'):
            logger.info("No xml, parsing pdf")
            self._parsepdf()

    def _hasfile(self, ext):
        return os.path.isfile(self.basedir+self.doi.split('/')[-1]+ext)

    def _download(self):
        fname = self.basedir + self.doi.split('/')[-1] + '.pdf'

        def geturl(url):
            logging.info(url)
            try:
                res = requests.get(url, headers=HEADERS)
            except:
                logging.info("Coudn't get url %s" % url)
                return False

            if res.status_code == 200 and res.headers['Content-Type'][:15] == 'application/pdf':
                with open(fname, 'wb') as f:
                    f.write(res.content)
                    logger.info("PDF downloaded from %s" % url)
                    return True
            else:
                logger.info("Issue with download")
                return False

        res = cr.works(ids=self.doi)
        if res['status'] == 'ok':
            url = None
            if 'link' in res['message'].keys():
                for link in res['message']['link']:
                    if link['URL'].split('.')[-1] == 'pdf':
                        url = link['URL'] 
            if url is None:
                logging.info("No url available on crossref")
            else:
                if geturl(url):
                    return True

        unp = "https://api.unpaywall.org/v2/%s?email=YOUR_EMAIL" % self.doi
        logging.info(unp)
        res = requests.get(unp)
        if res.status_code == 200:
            dat = json.loads(res.content.decode('utf-8'))
            if 'best_oa_location' in dat.keys():
                if dat['best_oa_location'] == None:
                    logging.info("No OA location found")
                    #return False
                elif dat['best_oa_location']['version'] == 'publishedVersion':
                    url = dat['best_oa_location']['url_for_pdf']
                    if url is None:
                        for location in dat['oa_locations']:
                            if location['version'] == 'publishedVersion' and location['url_for_pdf'] is not None:
                                url = location['url_for_pdf']
                    if url is None:
                        logger.info("Couldn't find an OA url for pdf")
                        #return False
                    elif url.find("wiley") > 0:
                        url = re.sub("pdf", "pdfdirect", url)
                    else:
                        if geturl(url):
                            return True
                        logger.info("Issue with download...")
                        logger.error(res.headers)
                else:
                    logger.info("Only %s available" % dat['best_oa_location']['version'])
            else:
                logger.info("No OA location available...")

        logger.info("You may want to try https://sci-hub.tw/%s ..." % self.doi)
        return False

    def _parsepdf(self):
        service = 'processFulltextDocument'
        generateIDs = False
        consolidate_header = False
        consolidate_citations = False
        force = False
        teiCoordinates = False

        client = grobidclient(config_path='grobid-config.json')

        start_time = time.time()

        client.process(self.basedir, self.basedir, 20, service, generateIDs,
                       consolidate_header, consolidate_citations, force,
                       teiCoordinates)

        runtime = round(time.time() - start_time, 3)
        logging.info("grobid runtime: %s seconds " % (runtime))

    def _fetchinformation(self):
        target = list(ads.SearchQuery(doi=self.doi, 
                                      fl=['id', 'doi', 'bibcode', 'year',
                                          'title', 'first_author', 'abstract',
                                          'reference', 'citation']))

        if len(target) != 1:
            logger.info("More than one paper (%d) return by ads, odd. %s", len(target), self.doi)
            return

        info = {
            'doi': target[0].doi,
            'bibcode': target[0].bibcode,
            'year': target[0].year,
            'title': target[0].title[0],
            'first_author': target[0].first_author,
            'abstract': target[0].abstract,
            'reference': target[0].reference,
            'citation': target[0].citation,
            'timestamp': datetime.datetime.now().isoformat()
        }

        with open(self.basedir+self.doi.split('/')[-1]+'.json', 'w') as f:
            json.dump(info, f)

        return info

    def findreference(self, author, year):

        fname = self.basedir + self.doi.split('/')[-1] + '.tei.xml'
        if not self._hasfile('.tei.xml'):
            logger.info("No raw text available, skipping...")
            return

        print("Looking for reference...", author, year)
        with open(fname, "r") as f:
            data = f.read()
        soup = BeautifulSoup(data, 'lxml')
            
        refidx = None
        for bib in soup.body.find_all("biblstruct"):
            bibitem = bib.find('author')
            if bibitem and refidx is None:
                if bibitem.persname.surname is None:
                    continue
                if bibitem.persname.surname.getText() == author:
                    if 'when' in bib.date.attrs:
                        pubdate = bib.date.attrs['when'] 
                        if len(pubdate.split('-')) > 1:
                            pubdate = pubdate.split('-')[0]
                        if pubdate == year:
                            refidx = bib.attrs['xml:id']

        if refidx is None:
            logger.info("Couldn't find the reference!")
                      
        printed = False
        for paragraph in soup.body.find_all("p"): #, attrs={"target":"#b50"}):
            refs = paragraph.find_all("ref", attrs={"target":"#%s" % refidx})
            if len(refs) > 0: #print(refs)
                #sentences = nltk.sent_tokenize(paragraph.getText())
                #for i,sent in enumerate(sentences):
                #    if author in sent:
                #        ctx = sentences[max(0,i-1):min(i+1,len(sentences)-1)]
                #        ctx = ' '.join(ctx)
                #        ctx = re.sub(author, '\033[1m%s\033[0m' % author, ctx)
                #        print(fill(ctx))
                #        print()
                print()
                print(fill(re.sub(author, "\033[1m%s\033[0m" % author,
                                  paragraph.getText()), width=80))
                printed = True

        return printed

    def checkproximity(self):
        proximity = []
        corpus = []
        for (dirpath, dirnames, filenames) in os.walk('pdf/'):
            for fname in filenames:
                if fname.endswith('.json'):
                    with open(os.path.join(dirpath, fname), 'r') as f:
                        dat = json.load(f)

                    abstract = dat['abstract']
                    if abstract is None:
                        abstract = 'isnone'
                    corpus.append(abstract)

                    common = 0
                    if 'reference' in dat.keys():
                        for ref in dat['reference']:
                            if ref in self.information['reference']:
                                common += 1

                    proximity.append([dat['first_author'], dat['year'], dat['title'], 
                                      common*1./len(self.information['reference'])])

        v = TfidfVectorizer(input='content', encoding='utf-8', decode_error='replace',
                            strip_accents='unicode', lowercase=True, analyzer='word',
                            stop_words='english', token_pattern=r'(?u)\b[a-zA-Z_][a-zA-Z0-9_]+\b',
                            ngram_range=(1, 2), max_features=10000, norm='l2', use_idf=True,
                            sublinear_tf=True, max_df=1.0, min_df=1)

        if len(corpus) > 0:
            X = v.fit_transform(corpus)
            pairwise_similarity = X * X.T 
            arr = pairwise_similarity.toarray()
            np.fill_diagonal(arr, np.nan) 

            if self.information['abstract'] is not None:
                input_idx = corpus.index(self.information['abstract']) 
                for i in range(len(proximity)):
                    proximity[i][3] = 0.5*(proximity[i][3] + arr[input_idx][i])

        if len(proximity) > 0:
            author, year, title, score = sorted(proximity, key=lambda x: x[3], reverse=True)[1]
            print("Highest proximity (based on common cites and abstract similarity):")
            print(author, year, title, score)
