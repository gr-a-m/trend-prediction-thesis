import calendar
from collections import Counter
import datetime as dt
import re
import json


class TwitterTrend:
    """ Represents a trend from the Twitter API.

    Note that this is different from a TrendLine. This simply represents a
    trend's name and when Twitter said is was in the top trending. A TrendLine
    on the other hand is intended to communicate change in a Trend over time
    based on some properties of the Tweets as they were in a time window. Use
    this to model the output from the Twitter API's trending endpoint.
    """

    def __init__(self, name, timestamps=None, window_size=120):
        """ Constructor for TwitterTrend with or without timestamps.

        If no timestamps are provided, it is assumed that they will be filled
        in at a later time and timestamps is initialized to an empty list. Name
        should be the name of the trend as in the JSON file retrieved from the
        Twitter API. The window_size should almost never be changed, but it is
        the number of seconds between trend windows, aka, it represents how
        granular our trends are.
        """
        self.name = name
        self.timestamps = [] if timestamps is None else timestamps
        self.window_size = window_size

    @staticmethod
    def from_file(json_file):
        """ Read a trends from a file using the from_twitter_json method. """
        lines = []
        with open(json_file, encoding='utf-8') as f:
            for line in f:
                lines.append(line)
        return TwitterTrend.from_json_strings(lines)

    @staticmethod
    def from_json_strings(json_strings):
        """ Constructs a list of TwitterTrends from a list of json strings.

        This json_strings argument is expected to be a list of JSON strings,
        each of which is the return value from the Twitter API's trends
        endpoint at a particular time.
        """
        trends_timestamps = {}
        last_ts = 0
        for json_s in json_strings:
            json_obj = json.loads(json_s)
            if json_obj.get('as_of') is None:
                continue
            jdt = dt.datetime.strptime(json_obj['as_of'], '%Y-%m-%dT%H:%M:%SZ')

            # Reduce jdt to the nearest 2-minute window, rounded down
            minutes = jdt.minute
            minutes -= minutes % 2  # If odd, reduce to even
            jdt.replace(minute=minutes, second=0, microsecond=0)

            ts = calendar.timegm(jdt.utctimetuple())

            if last_ts == 0:
                last_ts = ts - (ts % 120)

            while ts > last_ts:
                for topic in json_obj['trends']:
                    if trends_timestamps.get(topic['name']) is None:
                        trends_timestamps[topic['name']] = []
                        trends_timestamps[topic['name']].append(last_ts)
                    else:
                        trends_timestamps[topic['name']].append(last_ts)
                last_ts += 120

        trends = []
        for trend, timestamps in trends_timestamps.items():
            twitter_trend = TwitterTrend(trend, timestamps=timestamps)
            trends.append(twitter_trend)

        return trends


class BagOfWords(Counter):
    """ Represents a bag-of-words model of Tweets.

    This is used to construct "non-trends", i.e., strings that are sampled from
    the distribution of words in Tweets that could be trends, but are not. It
    follows what you would expect for a bag-of-words model of tweets to do. One
    important thing to understand is how words are read from a Tweet. A word is
    something that matches the word_re regex and is flanked by whitespace.
    """
    word_re = re.compile("#?\w\w+\Z")

    def random_trend_names(self, positive_trends, n=1):
        """ Creates n unique topics that don't match any positive topics. """
        total = 0
        words = []
        weights = []
        for word, weight in self.items():
            total += weight
            weights.append(total)
            words.append(word)

        negative_names = set()

        for i in range(n):
            if len(negative_names) != i:
                print("Problem making random names")

            new_trend = None

            while True:
                new_trend, count = self.most_common(1)[0]
                self[new_trend] = 0

                if new_trend not in positive_trends and new_trend not in negative_names:
                    break

            negative_names |= set([new_trend])
        return list(negative_names)

    @staticmethod
    def from_file(json_file, stopwords=set()):
        """ Takes a file of Tweets and a stopwords set and create a word model.

        The json_file should be a string path to the file containing one tweet
        per line encoded in JSON as the Twitter API does. Technically, all that
        is required for model creation is just the 'text' field of the objects,
        so other fields can be dropped for bag of words model creation. The
        stopwords argument is a set containing the words to ignore when
        constructing the model.
        """
        bag_of_words = BagOfWords()
        with open(json_file, encoding='utf-8') as f:
            for line in f:
                tweet = json.loads(line)
                words = tweet['text'].split()
                for word in words:
                    word = word.lower()
                    if word in stopwords:
                        continue
                    elif BagOfWords.word_re.match(word) is None:
                        continue
                    else:
                        bag_of_words[word] += 1
        return bag_of_words


class Stopwords(set):
    """ This class represents a set of words to ignore constructing a model.

    It's a fairly simple superclass of set that has a method to load from a
    CSV file.
    """

    @staticmethod
    def from_csv(stopwords_file):
        """ Load stopwords from a CSV file. """
        sw = Stopwords()
        with open(stopwords_file, encoding='utf-8') as f:
            for line in f:
                words = line.split(",")
                sw.update(words)
        return sw
