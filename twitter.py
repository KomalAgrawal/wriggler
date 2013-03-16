"""
Robust Twitter crawler primitives.
"""

from __future__ import division
from time import sleep
from requests_oauthlib import OAuth1

import times
import req


# Constants
RESET_BUFFER      = 60
RATE_LIMIT_BUFFER = 5
FAILURE_RETRY     = 60
MAX_RETRY         = 24 * 60

from logbook import Logger
log = Logger(__name__)

def check_rate_limit(r):
    """
    Check the rate limit and sleep off if it is hit.

    r - The response object from requests.
    """

    try:
        # If we hit the rate limit sleep
        remain = r.headers["x-rate-limit-remaining"]
        remain = int(remain)
        if remain <= RATE_LIMIT_BUFFER:
            log.debug("Hit rate limit - {}", remain)

            now   = r.headers["date"]
            now   = times.parse(now)
            now   = times.to_unix(now)

            reset = r.headers["x-rate-limit-reset"]
            reset = int(reset)

            # Sleep past the reset time
            log.debug("Rate limit reset in {} seconds", reset - now)
            sleep(reset - now + RESET_BUFFER)
    except KeyError as e:
        # We dont have the proper headers
        log.error("Header not found - {}", e)
        sleep(FAILURE_RETRY)

def user_timeline(user_id, token):
    """
    Get as many tweets from the user as possible.

    user_id - A single user_id of a twitter user.
    returns - A list of tweets for the given user. The list may be empty.
    """

    url = "http://api.twitter.com/1.1/statuses/user_timeline.json"
    headeroauth = OAuth1(client_key=token['client_key'], 
                      client_secret=token['client_secret'],
                      resource_owner_key=token['resource_owner_key'], 
                      resource_owner_secret=token['resource_owner_secret'], 
                      signature_type='auth_header')
    params = {
        "user_id": user_id,
        "count": 200,
        "include_rts": 1,
        "include_entities": 1
    }

    # We gather all tweets here
    tweets = []
    ids = set()
    tcount = 0

    tries = 0
    while tries < MAX_RETRY:
        r = req.get(url, params=params, auth=headeroauth, timeout=60.0)
        # Proper receive
        if r.status_code == 200:
            for tweet in r.json():
                if tweet["id"] not in ids:
                    tweets.append(tweet)
                    ids.add(tweet["id"])

            # If we have not added any more tweets; return
            if len(ids) == tcount:
                return tweets
            tcount = len(ids)

            # Set the new max_id value
            params["max_id"] = min(ids)
            tries = 0
            check_rate_limit(r)
            continue

        # Check if rate limited
        if r.status_code == 400:
            log.info(u"Try {}: Being throttled - {} {}",
                     tries, r.status_code, r.text)
            check_rate_limit(r)
            tries += 1
            continue

        # User doesn't exist
        if r.status_code in (401, 403, 404):
            log.info(u"Try {}: User doesn't exist - {} {}",
                     tries, r.status_code, r.text)
            check_rate_limit(r)
            return tweets

        # Dont expect anything else
        log.warn(u"Try {}: Unexepectd response - {} {}",
                 tries, r.status_code, r.text)
        check_rate_limit(r)
        tries += 1
        continue

    log.critical("Maximum retries exhausted ...")
    raise SystemExit()

def users_lookup(user_ids, token):
    """
    Lookup profiles of as many users as possible.

    user_ids - A list of user_ids of twitter users (max 100).
    returns  - A list of profiles for the given users. The list may not contain
               profiles for all the users.
    """
    headeroauth = OAuth1(client_key=token['client_key'], 
                    client_secret=token['client_secret'],
                    resource_owner_key=token['resource_owner_key'], 
                    resource_owner_secret=token['resource_owner_secret'],
                    signature_type='auth_header')    

    user_ids = map(str, user_ids)
    user_ids = ",".join(user_ids)

    url = "http://api.twitter.com/1.1/users/lookup.json"
    params = {
        "user_id": user_ids,
        "include_entities": 1
    }

    tries = 0
    while tries < MAX_RETRY:
        r = req.get(url, params=params, auth=headeroauth, timeout=60.0)

        # Proper receive
        if r.status_code == 200:
            check_rate_limit(r)
            return r.json()

        # User doesn't exist
        if r.status_code in (403, 404):
            log.info(u"Try {}: User doesn't exist - {} {}",
                     tries, r.status_code, r.text)
            check_rate_limit(r)
            return []

        # Check if rate limited
        if r.status_code == 400:
            log.info(u"Try {}: Being throttled - {} {}",
                     tries, r.status_code, r.text)
            check_rate_limit(r)
            tries += 1
            continue

        # Dont expect anything else
        log.warn(u"Try {}: Unexepectd response - {} {}",
                 tries, r.status_code, r.text)
        check_rate_limit(r)
        tries += 1
        continue

    log.critical("Maximum retries exhausted ...")
    raise SystemExit()

def users_show(user_id, token):
    """
    Get the profile of the given of the given user.

    user_id - A user_id of a single twitter user.
    return  - A 2 tuple. First is the status code returned by Twitter, second is
              the profile of the Twitter user. If status code is 403 or 403, the
              profile will instead contain the reason of absence of the profile.
    """

    url = "http://api.twitter.com/1.1/users/show.json"
    params = {
        "user_id": user_id,
        "include_entities": 1
    }
    
    headeroauth = OAuth1(client_key=token['client_key'], 
                    client_secret=token['client_secret'],
                    resource_owner_key=token['resource_owner_key'], 
                    resource_owner_secret=token['resource_owner_secret'],
                    signature_type='auth_header')
    tries = 0
    while tries < MAX_RETRY:
        r = req.get(url, params=params, auth=headeroauth, timeout=60.0)

        # Proper receive
        if r.status_code == 200:
            check_rate_limit(r)
            return (200, r.json())

        # User doesn't exist
        if r.status_code in (403, 404):
            check_rate_limit(r)
            return (r.status_code, r.json())

        # Check if rate limited
        if r.status_code == 400:
            log.info(u"Try {}: Being throttled - {} {}",
                     tries, r.status_code, r.text)
            check_rate_limit(r)
            tries += 1
            continue

        # Dont expect anything else
        log.warn(u"Try {}: Unexepectd response - {} {}",
                 tries, r.status_code, r.text)
        check_rate_limit(r)
        tries += 1
        continue

    log.critical("Maximum retries exhausted ...")
    raise SystemExit()

