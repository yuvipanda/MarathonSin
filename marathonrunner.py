#!/usr/bin/env python
import sys
import os

import time
import yaml
import pickle
import random

import twitter

class Store(object):
    def __init__(self, buckets, filepath=None):
        self.filepath = filepath
        if filepath and os.path.exists(filepath):
            self._store = pickle.load(open(filepath))
        else:
            self._store = {}
        for b in buckets:
            if not b in self._store:
                self._store[b] = {}

    def get(self, bucket, key):
        if bucket in self._store:
            if key in self._store[bucket]:
                return self._store[bucket][key]
        return None

    def set(self, bucket, key, value):
        if bucket in self._store:
            self._store[bucket][key] = value
            if self.filepath:
                pickle.dump(self._store, open(self.filepath, 'w')) # Slow, but okay for now
        else:
            raise KeyError("%s bucket not found" % bucket)

class Bot(object):
    def __init__(self, name, username, delay, store_filepath):
        self.name = name
        self.username = username
        self.delay = delay
        self.behaviors = []
        
        self._api = None
        self._store = Store(['search'], store_filepath)

    def add_search_behavior(self, search_term, responses):
        self.behaviors.append({
            'type': 'search',
            'term': search_term,
            'responses': responses})

    def set_auth_credentials(self, consumer_key, consumer_secret, access_key, access_secret):
        if self._api:
            self._api = None # Clear api if it's already been c
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.access_key = access_key
        self.access_secret = access_secret

    def loop_once(self):
        api = self._get_api()
        print "starting loop"
        for behavior, results in self._actionable_search_results():
            print "%s results" % len(results)
            for tweet in results:
                tweet_text = "@%s %s" % (tweet.user.screen_name, random.choice(behavior['responses']))
                try:
                    api.PostUpdate(tweet_text, in_reply_to_status_id=tweet.id)
                except twitter.TwitterError:
                    continue
                print tweet_text

    def loop(self):
        while True:
            self.loop_once()
            time.sleep(self.delay)

    def _get_api(self):
        if not self._api:
            self._api = twitter.Api(
                    consumer_key=self.consumer_key,
                    consumer_secret=self.consumer_secret,
                    access_token_key=self.access_key,
                    access_token_secret=self.access_secret)
        return self._api

    def _actionable_search_results(self):
        api = self._get_api()
        for behavior in self.behaviors:
            if behavior['type'] == 'search':                
                since_id = self._store.get('search', behavior['term'])
                results = api.GetSearch(behavior['term'], per_page=50, since_id=since_id)
                yield (behavior, results)
                if len(results) > 0:
                    self._store.set('search', behavior['term'], results[0].id)

def resolve_filerefs(value):
    def is_sequence(arg):
        return (not hasattr(arg, "strip") and
                hasattr(arg, "__getitem__") or
                hasattr(arg, "__iter__"))
    if is_sequence(value):
        return value
    else:
        data = open(value)
        return [l.strip() for l in data.readlines()] # Stripping the Newline

if __name__ == "__main__":
    data_file = sys.argv[1]
    creds_file = sys.argv[2]
    data = yaml.load(open(data_file))
    creds = yaml.load(open(creds_file))

    bot = Bot(data['name'], data['username'], int(data['delay']) * 60, data['store-file'])
    for behavior in data['behaviors']:
        if 'search-term' in behavior:
            bot.add_search_behavior(behavior['search-term'], resolve_filerefs(behavior['responses']))
    bot.set_auth_credentials(
            creds['consumer-key'],
            creds['consumer-secret'],
            creds['access-key'],
            creds['access-secret'])

    bot.loop()
