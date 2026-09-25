#!/usr/bin/env python3
# written by So Okada so.okada@gmail.com
# a part of hekiJxiv for retrieval of Jxiv records by jalc_parser.py
# https://github.com/so-okada/hekiJxiv/

import re
import time
import traceback

from hekiJxiv_variables import *
import jalc_parser


# one harvest: a window of the doilist minus the announced DOIs, with
# metadata fetched for the rest.
def new_records(label, announced, max_post=None, num_last_days=None):
    max_post = max_post_per_run if max_post is None else max_post
    # a command line -n wins over jalc_from_days.
    from_days = jalc_from_days if num_last_days is None else num_last_days

    trial_num = 0
    while trial_num < jalc_max_trial:
        try:
            listing = jalc_parser.doi_list(from_days=from_days)
            break
        except jalc_parser.JaLCRequestError:
            # not retried
            print("**doilist request refused for " + label
                  + ", not retrying")
            traceback.print_exc()
            raise
        except Exception:
            print(str(trial_num + 1) + "th doilist error for " + label)
            traceback.print_exc()
            trial_num += 1
            if trial_num < jalc_max_trial:
                print("sleep " + str(jalc_retry_sleep) + "s and retry for "
                      + label)
                time.sleep(jalc_retry_sleep)
            else:
                raise Exception("fatal doilist error for " + label)

    print("walked " + str(listing.total) + " doi(s) in "
          + str(listing.pages) + " page(s) from "
          + (listing.from_date or "the beginning") + " for " + label
          + ("" if listing.complete else " (INCOMPLETE)"))

    # numeric suffix order
    new_dois = sorted(listing.dois - announced, key=suffix_number)
    print(str(len(new_dois)) + " doi(s) not yet announced for " + label)

    records = []
    old = []
    unavailable = []
    failed = []
    for doi in new_dois:
        # a failed fetch skips this DOI; it stays unlogged.
        try:
            entry = jalc_parser.fetch_doi(doi)
        except Exception:
            print("**error fetching " + doi + " for " + label)
            traceback.print_exc()
            failed.append(doi)
            continue
        if not entry:
            unavailable.append(doi)
        elif not entry.get("issued") or entry["issued"] < listing.from_date:
            # issued before the window; not logged.
            old.append(doi + " (v" + (entry.get("version") or "?")
                       + ", issued " + (entry.get("issued") or "?") + ")")
        else:
            entry["updated_date"] = listing.updated.get(doi, "")
            records.append(entry)

    if old:
        print(str(len(old)) + " doi(s) issued before " + listing.from_date
              + " skipped for " + label + ": " + ", ".join(old[:10])
              + (" ..." if len(old) > 10 else ""))

    # the rest stays unlogged.
    if len(records) > max_post:
        print(str(len(records) - max_post) + " doi(s) over max_post of "
              + str(max_post) + " left for a later run for " + label)
        records = records[:max_post]

    if unavailable:
        # not logged; fetched again next run.
        print(str(len(unavailable)) + " doi(s) with no metadata yet for "
              + label + ": " + ", ".join(unavailable[:10])
              + (" ..." if len(unavailable) > 10 else ""))
    if failed:
        print(str(len(failed)) + " doi(s) whose fetch failed for "
              + label + ": " + ", ".join(failed[:10])
              + (" ..." if len(failed) > 10 else ""))

    return feed(label, listing, records, unavailable, failed)


# the number in a Jxiv DOI suffix, 0 when there is none.
def suffix_number(doi):
    digits = re.sub(r"\D", "", doi.split("/", 1)[-1])
    return int(digits) if digits else 0


class feed:
    def __init__(self, label, listing, records, unavailable, failed):
        self.label = label
        self.listing = listing
        self.pages = listing.pages
        self.complete = listing.complete
        self.current = listing.dois
        self.records = records
        self.unavailable = unavailable
        self.failed = failed
        # the records to post
        self.newsubmissions = records
        self.total = len(records)
