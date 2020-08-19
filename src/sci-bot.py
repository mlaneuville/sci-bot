'''
    > python sci-bot.py DOI

    Returns:
    - citation context for last 5 citations
'''
import ads

from argparse import ArgumentParser

from article import Article

parser = ArgumentParser()
parser.add_argument("--doi", help="Target paper DOI", required=True)
parser.add_argument("--parse", default=False, type=bool, help="Also fetch citing papers")
args = parser.parse_args()

if __name__ == '__main__':
    target = Article(args.doi)

    if target.information['citation'] is not None and args.parse:
        print()
        print("Cited by %d" % len(target.information['citation']))
        print("Looping through citations...")
        worked = 0
        for cite in sorted(target.information['citation'], reverse=True):
            print(cite)
            article = list(ads.SearchQuery(bibcode=cite, fl=['id', 'title', 'doi', 'bibcode', 'year', 'first_author', 'abstract', 'reference', 'citation'],
                                                         fq=['property:refereed']))
            if len(article) != 1:
                continue
            if article[0] is None:
                continue
            if article[0].doi is None:
                continue

            doi = article[0].doi[0]
            citation = Article(doi)
            #p = citation.findreference(target.information['first_author'].split(',')[0], target.information['year'])
            #if p:
            #    worked += 1
            #if worked == 10:
            #    break
            print()

    print()
    #target.checkproximity()
