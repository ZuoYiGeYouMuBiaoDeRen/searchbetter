from whoosh.fields import *
from whoosh.index import create_in, open_dir
from whoosh.qparser import MultifieldParser
from whoosh.query import *
import abc
import copy
import csv
import json
import os.path
import sys


# Abstract Search Engine class
# TODO: abstract out more functionality here
class SearchEngine(object):
    # make it an abstract class
    #
    __metaclass__ = abc.ABCMeta

    # TODO consider making more hierarchy. This is the WhooshSearchEngine,
    # which has the cool indexing capabilities. But more generally, you
    # could have a search engine that only has to support search().
    # but at that point it's just a useless interface, mostly.
    # anyway, such a search engine would let the query rewriting search engine
    # inherit from search engine too.

    def __init__(self, create, search_fields, index_path):
        """
        Creates a new search engine.

        :param create {bool}: If True, recreates an index from scratch.
            If False, loads the existing index
        :param search_fields {str[]}: An array names of fields in the index that our
            search engine will search against.
        :param index_path {str}: A relative path to a folder where the whoosh
            index should be stored.
        """
        # TODO have an auto-detect feature that will determine if the
        # index exists, and depending on that creates or loads the index

        self.index_path = index_path

        # both these functions return an index
        if create:
            self.index = self.create_index()
        else:
            self.index = self.load_index()

        # set up searching
        # first, query parser
        self.parser = MultifieldParser(search_fields, self.index.schema)


    def load_index(self):
        """
        Used when the index is already created. This just loads it and
        returns it for you.
        """

        index = open_dir(self.index_path)
        return index


    def create_index(self):
        """
        Subclasses must implement!
        """
        raise NotImplementedError("Subclasses must implement!")


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
        super(UdacitySearchEngine, self).__init__(
            create, self.SEARCH_FIELDS, self.INDEX_PATH)


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




class HarvardXSearchEngine(SearchEngine):
    INDEX_PATH = 'models/whoosh_indices/harvardx'
    SEARCH_FIELDS = ["display_name", "contents"]

    def __init__(self, create=False):
        """
        Creates a new HarvardX search engine. Searches over the HarvardX/DART
        database of all courses and course materials used in HarvardX. This includes
        videos, quizzes, etc.

        TODO: consider renaming to DART, probz

        :param create {bool}: If True, recreates an index from scratch.
            If False, loads the existing index
        """
        super(HarvardXSearchEngine, self).__init__(
            create, self.SEARCH_FIELDS, self.INDEX_PATH)


    def create_index(self):
        """
        Creates a new index to search the dataset. You only need to
        call this once; once the index is created, you can just load it again
        instead of creating it afresh all the time.

        Returns the index object.
        """

        # load data
        # real data
        csvfile_path = 'datasets/corpus_HarvardX_LatestCourses_based_on_2016-10-18.csv'
        # test data
        # csvfile_path = 'datasets/test.csv'

        # only consider resources with this category (type of content)
        # unsure about courses (b/c they have no content) and html (b/c they often include messy CSS/JS in there)
        # TODO: add "html" support. requires stripping comments
        #       http://stackoverflow.com/questions/753052/strip-html-from-strings-in-python
        #
        supported_categories = ('problem', 'video', 'course')

        # set up whoosh schema
        schema = Schema(
            course_id=ID(stored=True),
            display_name=TEXT(stored=True),
            contents=TEXT
        )


        # TODO: use StemmingAnalyzer here so we get the built-in benefits
        # of stemming in our search engine
        # http://whoosh.readthedocs.io/en/latest/stemming.html

        # make an index to store this stuff in
        if not os.path.exists(self.INDEX_PATH):
            os.mkdir(self.INDEX_PATH)
        index = create_in(self.INDEX_PATH, schema)

        # start adding documents (i.e. the courses) to the index

        # first, some of the fields are HUGE so we need to let the csv
        # reader handle them
        csv.field_size_limit(sys.maxsize)

        with open(csvfile_path, 'r') as csvfile:
            reader = csv.DictReader(csvfile)

            writer = index.writer()

            try:
                for row in reader:
                    # ensure the content is actually a valid type
                    if row['category'] not in supported_categories:
                        pass

                    # write
                    writer.add_document(
                        course_id=row['course_id'].decode('utf8'),
                        display_name=row['display_name'].decode('utf8'),
                        contents=row['contents'].decode('utf8'))

                writer.commit()
            except Exception as e:
                print e
                writer.cancel()


        # all done for now
        return index




class EdXSearchEngine(SearchEngine):
    INDEX_PATH = 'models/whoosh_indices/edx'
    SEARCH_FIELDS = ["name"]

    def __init__(self, create=False):
        """
        Creates a new search engine that searches over edX courses.

        :param create {bool}: If True, recreates an index from scratch.
            If False, loads the existing index
        """
        super(EdXSearchEngine, self).__init__(
            create, self.SEARCH_FIELDS, self.INDEX_PATH)


    def create_index(self):
        """
        Creates a new index to search the dataset. You only need to
        call this once; once the index is created, you can just load it again
        instead of creating it afresh all the time.

        Returns the index object.
        """

        # load data
        csvfile_path = 'datasets/Master CourseListings - edX.csv'

        # set up whoosh schema
        schema = Schema(
            course_id=ID(stored=True),
            name=TEXT(stored=True)
        )

        # TODO: use StemmingAnalyzer here so we get the built-in benefits
        # of stemming in our search engine
        # http://whoosh.readthedocs.io/en/latest/stemming.html

        # make an index to store this stuff in
        if not os.path.exists(self.INDEX_PATH):
            os.mkdir(self.INDEX_PATH)
        index = create_in(self.INDEX_PATH, schema)

        # start adding documents (i.e. the courses) to the index

        with open(csvfile_path, 'r') as csvfile:
            reader = csv.DictReader(csvfile)

            writer = index.writer()

            try:
                for row in reader:
                    # write
                    writer.add_document(
                        course_id=row['course_id'].decode('utf8'),
                        name=row['name'].decode('utf8'))

                writer.commit()
            except Exception as e:
                print e
                writer.cancel()

        # all done for now
        return index
