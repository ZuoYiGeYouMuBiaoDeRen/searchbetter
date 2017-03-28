import json
import os.path
from whoosh.index import create_in, open_dir
from whoosh.fields import *
from whoosh.query import *
from whoosh.qparser import MultifieldParser
import copy
import abc


# Abstract Search Engine class
# TODO: abstract out more functionality here
class SearchEngine(object):
    __metaclass__ = abc.ABCMeta

    def load_index(self):
        """
        Used when the index is already created. This just loads it and
        returns it for you.
        """

        index = open_dir(self.INDEX_PATH)
        return index


    def search(self, query_string):
        """
        Runs a plain-English search and returns results.
        :param query_string {String}: a query like you'd type into Google.
        :return: a list of dicts, each of which encodes a search result.
        """
        outer_results = []

        with self.index.searcher() as searcher:
            query_obj = self.parser.parse(query_string)
            # this variable is closed when the searcher is closed, so save this data
            # in a variable outside the with-block
            results = searcher.search(query_obj)
            # this is still a list of Hits; convert to just a list of dicts
            result_dicts = [hit.fields() for hit in list(results)]
            # make sure we store it outside the with-block b/c scope
            outer_results = result_dicts

        return outer_results



class UdacitySearchEngine(SearchEngine):
    DATASET_PATH = 'datasets/udacity-api.json'
    INDEX_PATH = 'models/whoosh_indices/udacity'
    SEARCH_FIELDS = ["title", "subtitle", "expected_learning", "syllabus", "summary", "short_summary"]

    def __init__(self, create=False):
        """
        Creates a new Udacity search engine.

        :param create {bool}: If True, recreates an index from scratch.
            If False, loads the existing index
        """
        # TODO have an auto-detect feature that will determine if the
        # index exists, and depending on that creates or loads the index

        # TODO clean up the object orientation here

        # both these functions return an index
        if create:
            self.index = self.create_index()
        else:
            self.index = self.load_index()

        # set up searching
        # first, query parser
        self.parser = MultifieldParser(self.SEARCH_FIELDS, self.index.schema)


    def create_index(self):
        """
        Creates a new index to search the Udacity dataset. You only need to
        call this once; once the index is created, you can just load it again
        instead of creating it afresh all the time.
        """

        # load data
        udacity_data = None
        with open(self.DATASET_PATH, 'r') as file:
            udacity_data = json.load(file)

        # set up whoosh
        # schema

        # TODO: use StemmingAnalyzer here so we get the built-in benefits
        # of stemming in our search engine
        # http://whoosh.readthedocs.io/en/latest/stemming.html

        schema = Schema(
            slug=ID(stored=True),
            title=TEXT(stored=True),
            subtitle=TEXT,
            expected_learning=TEXT,
            syllabus=TEXT,
            summary=TEXT,
            short_summary=TEXT
        )

        # make an index to store this stuff in
        if not os.path.exists(self.INDEX_PATH):
            os.mkdir(self.INDEX_PATH)
        index = create_in(self.INDEX_PATH, schema)

        # start adding documents (i.e. the courses) to the index
        try:
            writer = index.writer()
            for course in udacity_data['courses']:
                writer.add_document(
                    slug=course['slug'],
                    title=course['title'],
                    subtitle=course['subtitle'],
                    expected_learning=course['expected_learning'],
                    syllabus=course['syllabus'],
                    summary=course['summary'],
                    short_summary=course['short_summary'])
            writer.commit()
        except Exception as e:
            print e

        # all done for now
        return index