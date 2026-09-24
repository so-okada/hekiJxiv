#!/usr/bin/env python3
# written by So Okada so.okada@gmail.com
# a part of hekiJxiv for posting to bsky and stdout
# https://github.com/so-okada/hekiJxiv/

import re
import os
import time
import traceback
from atproto import Client
import pandas as pd
from datetime import datetime, timezone
from ratelimit import limits, sleep_and_retry, rate_limited

from hekiJxiv_variables import *
import hekiJxiv_format as hJf
import hekiJxiv_daily_feed as hJd
import jalc_parser


def main(switches, logfiles, pt_mode, max_new=None, num_last_days=None):
    starting_time = utcnow()
    print("**process started at " + str(starting_time) + " (UTC)")

    client_dict = {}
    update_dict = {}

    newsubmission_mode = {}
    summary_mode = {}

    for cat in switches:
        # no login in stdout mode
        client_dict[cat] = atproto_client(switches[cat]) if pt_mode else None
        update_dict[cat] = sleep_and_retry(
            rate_limited(post_updates, an_hour)(update))
        newsubmission_mode[cat] = int(switches[cat]["newsubmissions"])
        # summaries default to on
        summary_mode[cat] = int(switches[cat].get("summaries", 1))

    # retrieval and new submissions, one bot after another.
    for i, cat in enumerate(switches):
        print("starting retrieval/new submissions for " + cat)
        newentries(
            logfiles,
            cat,
            client_dict[cat],
            update_dict[cat],
            newsubmission_mode[cat],
            summary_mode[cat],
            pt_mode,
            max_new,
            num_last_days,
        )
        if i != len(switches) - 1:
            print("waiting before the next bot")
            time.sleep(bot_wait)

    if not logfiles:
        ptext = (
            "No logfiles found. "
            + "hekiJxiv needs logfiles to know which preprints it has "
            + "already handled: JaLC's doilist carries every Jxiv doi "
            + "ever registered, with nothing in it to say which are new."
        )
        print(ptext)

    ending_time = utcnow()
    ptext = (
        "\n**process ended at "
        + str(ending_time)
        + " (UTC)"
        + "\n**elapsed time from the start: "
        + str(ending_time - starting_time)
    )
    print(ptext)


class dry_run_result:
    uri = ""
    cid = ""


# post with overall limit
@sleep_and_retry
@limits(calls=overall_bsky_limit_call, period=overall_bsky_limit_period)
def update(logfiles, cat, client, total, preprint_id, text, pt_mode, langs):
    result = 0

    if not pt_mode:
        update_print(cat, preprint_id, text, "", pt_mode, langs)
        # a stand-in for a bsky response
        return dry_run_result()

    if not client:
        update_print(
            cat, preprint_id,
            "\n**error: client not available:\n\n" + text,
            "", pt_mode, langs)
        return result

    try:
        result = client.send_post(
            text=text, facets=generate_facets_for_urls(text), langs=langs)
        update_print(cat, preprint_id, text, result.uri, pt_mode, langs)
    except Exception:
        time_now = utcnow()
        error_text = (
            "\n**error to post**"
            + "\nutc: " + str(time_now)
            + "\nlabel: " + cat
            + "\nclient_handle: " + client.me.handle
            + "\nclient_did: " + client.me.did
            + "\npreprint id: " + preprint_id
            + "\ntext: " + text
            + "\n"
        )
        print(error_text)
        traceback.print_exc()

    update_log(logfiles, cat, total, preprint_id, result, pt_mode)
    time.sleep(bsky_sleep)
    return result


# update stdout text format
def update_print(cat, preprint_id, text, result_uri, pt_mode, langs):
    time_now = utcnow()
    ptext = (
        "\nutc: "
        + str(time_now)
        + "\nlabel: "
        + cat
        + "\npreprint id: "
        + preprint_id
        + "\npost mode: "
        + str(pt_mode)
        + "\nlangs: "
        + ", ".join(langs)
        + "\nurl: "
        + atproto_uri_to_url(result_uri)
        + "\ntext: "
        + text
        + "\n"
    )
    print(ptext)


# the log file entry of one label, or None
def log_entry(logfiles, cat, keys):
    if not logfiles:
        return None
    if cat not in logfiles:
        print("no log file entry for " + cat + " in logfiles.json")
        return None
    entry = logfiles[cat]
    missing = [one for one in keys if one not in entry]
    if missing:
        print("no " + ", ".join(missing) + " for " + cat
              + " in logfiles.json")
        return None
    return entry


# logging for update
def update_log(logfiles, cat, total, preprint_id, result, pt_mode):
    if not result or not pt_mode or not logfiles:
        return None

    time_now = utcnow()
    logname = "post_summary_log" if not preprint_id else "post_log"
    entry = log_entry(logfiles, cat, [logname, "username"])
    if entry is None:
        print("**not logged for " + cat + ": " + logname
              + (", preprint id: " + preprint_id if preprint_id else ""))
        return None

    if logname == "post_summary_log":
        log_text = [
            [time_now, total, entry["username"], result.uri, result.cid]
        ]
        df = pd.DataFrame(
            log_text, columns=["utc", "total", "username", "uri", "cid"])
    else:
        log_text = [
            [time_now, preprint_id, entry["username"],
             result.uri, result.cid]
        ]
        df = pd.DataFrame(
            log_text,
            columns=["utc", "doi", "username", "uri", "cid"]
        )

    filename = entry[logname]
    if not filename:
        return None
    if os.path.exists(filename):
        df.to_csv(filename, mode="a", header=None, index=None)
    else:
        df.to_csv(filename, mode="w", index=None)


# retrieval of new entries, and calling a sub process for new submissions
def newentries(
    logfiles,
    cat,
    client,
    update_limited,
    newsubmission_mode,
    summary_mode,
    pt_mode,
    max_new=None,
    num_last_days=None,
):
    print("getting new entries for " + cat)

    if pt_mode:
        required = ["post_log", "username"]
        if summary_mode:
            required.append("post_summary_log")
        entry = log_entry(logfiles, cat, required)
        if entry is None or any(
                not isinstance(entry[key], str) or not entry[key].strip()
                for key in required):
            print("**nothing posted for " + cat
                  + ": live posting requires nonempty log paths and username")
            return None

    # an unreadable post log means nothing is posted for this label.
    try:
        announced = announced_ids(cat, logfiles)
    except Exception:
        print("\n**error for post log**\nlabel: " + cat
              + "\nnothing posted, since an unreadable post log cannot "
              + "rule out a second announcement.")
        traceback.print_exc()
        return None

    # a day already posted needs no requests.
    if summary_mode and check_log_dates(
            cat, "post_summary_log", logfiles):
        print(cat + " already posted for today")
        return None

    try:
        entries = hJd.new_records(cat, announced, max_new, num_last_days)
    except hJd.TooManyNew:
        # nothing posted, summary included.
        print("\n**refusing to post for " + cat + "**")
        traceback.print_exc()
        return None
    except Exception:
        print("\n**error for retrieval**\nlabel: " + cat)
        traceback.print_exc()
        if summary_mode and not check_log_dates(
                cat, "post_summary_log", logfiles):
            # retrieval failed and no summary for today has been posted.
            time_now = utcnow()
            ptext = intro(time_now, 0, cat)
            update_limited(
                logfiles, cat, client, "0", "", ptext, pt_mode,
                [post_language_default])
        return None

    if not newsubmission_mode:
        if summary_mode:
            total = len(entries.newsubmissions)
            ptext = intro(utcnow(), total, cat)
            update_limited(
                logfiles, cat, client, str(total), "", ptext, pt_mode,
                [post_language_default])
        return None

    print("new submissions for " + cat)
    newsub_entries = hJf.format(entries.newsubmissions)
    newsubmissions(
        logfiles, cat, client, update_limited, newsub_entries, summary_mode,
        pt_mode)


# the language tag of a post: the language of the title it quotes,
# else the default.
def post_langs(language):
    return [language if language else post_language_default]


# an introductory text of each bot
# an example: [2026-08-25 Tue (UTC), 4 new preprints found for Jxiv]
def intro(given_time, num, cat):
    ptext = "[" + given_time.strftime("%Y-%m-%d %a") + " (UTC), "
    if num == 0:
        ptext = ptext + "no new preprints found for "
    elif num == 1:
        ptext = ptext + str(num) + " new preprint found for "
    else:
        ptext = ptext + str(num) + " new preprints found for "
    ptext = ptext + cat

    if num > post_updates - 1:
        ptext = (
            ptext
            + ", but only first "
            + str(post_updates - 1)
            + " preprints to post."
            + "]"
        )
    else:
        ptext = ptext + "]"
    return ptext


# new submissions by posts
def newsubmissions(
    logfiles, cat, client, update_limited, entries, summary_mode, pt_mode
):
    if summary_mode:
        time_now = utcnow()
        ptext = intro(time_now, len(entries), cat)
        update_limited(
            logfiles, cat, client, str(len(entries)), "", ptext, pt_mode,
            [post_language_default])
    else:
        print("no summary for " + cat + ", "
              + str(len(entries)) + " new preprint(s) to post")

    # the post log is appended as each post succeeds; a dry run writes
    # nothing.
    post_counter = 1
    for each in entries:
        if post_counter < post_updates:
            preprint_id = each["id"]
            langs = post_langs(each["language"])
            update_limited(
                logfiles, cat, client, "", preprint_id, each["post_text"],
                pt_mode, langs)
            post_counter += 1


# every preprint doi this bot has already posted
def announced_ids(cat, logfiles):
    if not logfiles:
        return set()

    entry = log_entry(logfiles, cat, ["post_log", "username"])
    if entry is None:
        # raising leaves this label unposted.
        raise Exception("no readable log file entry for " + cat)

    filename = entry["post_log"]
    if not os.path.exists(filename):
        print("log file does not exist: " + filename)
        return set()

    try:
        df = pd.read_csv(filename, dtype=object)
    except pd.errors.EmptyDataError:
        return set()
    except Exception:
        time_now = utcnow()
        error_text = "\nutc: " + str(time_now) + "\nfilename: " + filename
        error_text = "\n**error for log file**" + error_text
        print(error_text)
        traceback.print_exc()
        raise

    if "doi" not in df.columns:
        raise Exception("no doi column in " + filename)

    username = entry["username"]
    ids = df.loc[df["username"] == username, "doi"]
    return set(one for one in ids.dropna().astype(str))


# true if this finds a today's post.
def check_log_dates(cat, logname, logfiles):
    if not logfiles:
        print("no log files")
        return False

    entry = log_entry(logfiles, cat, [logname, "username"])
    if entry is None:
        return False

    filename = entry[logname]
    if not os.path.exists(filename):
        print("log file does not exists: " + filename)
        return False

    time_now = utcnow()
    try:
        df = pd.read_csv(filename, dtype=object)
    except pd.errors.EmptyDataError:
        return False
    except Exception:
        error_text = "\nutc: " + str(time_now) + "\nfilename: " + filename
        error_text = "\n**error for log file**" + error_text
        print(error_text)
        traceback.print_exc()
        return False
    for index, row in df.iterrows():
        log_time = datetime.fromisoformat(row["utc"])
        if (
            check_dates(log_time, time_now)
            and row["username"] == entry["username"]
        ):
            return True
    return False


# true if dates of input times are the same
def check_dates(time1, time2):
    return time1.date() == time2.date()


# a naive utc timestamp, as written to and read back from the log files
def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


def atproto_client(keys):
    client = Client()
    try:
        time.sleep(bsky_createaccts_sleep)
        client.login(keys["username"], keys["password"])
    except Exception:
        print("\n**error: " + keys["username"] + " failed to login.")
        traceback.print_exc()
        return None
    return client


def atproto_uri_to_url(uri):
    if not uri:
        return ""
    path = uri[5:]
    parts = path.split("/", 1)
    did = parts[0]
    resource = parts[1]
    post_id = resource.split("/")[-1]
    return f"https://bsky.app/profile/{did}/post/{post_id}"


def generate_facets_for_urls(text):
    url_pattern = re.compile(r"https?://[^\s\[\]]+")
    facets = []

    for match in url_pattern.finditer(text):
        # convert character offsets to UTF-8 byte offsets
        byte_start = len(text[:match.start()].encode("utf-8"))
        byte_end = len(text[:match.end()].encode("utf-8"))
        url = match.group()

        facets.append(
            {
                "index": {
                    "byteStart": byte_start,
                    "byteEnd": byte_end,
                },
                "features": [
                    {
                        "$type": "app.bsky.richtext.facet#link",
                        "uri": url,
                    }
                ],
            }
        )
    return facets


# fetch, format and print the given dois; nothing is written or
# posted. A bare suffix such as jxiv.10 is accepted.
def show_dois(doi_text):
    dois = [one.strip() for one in doi_text.split(",") if one.strip()]
    dois = [one if one.startswith(jalc_prefix + "/")
            else jalc_prefix + "/" + one for one in dois]

    records = []
    for doi in dois:
        entry = jalc_parser.fetch_doi(doi)
        if entry:
            records.append(entry)
        else:
            print("**no metadata for " + doi + ", left unseen")

    for each in hJf.format(records):
        print(
            "\ndoi: " + each["doi"]
            + "\ndate: " + each["date"]
            + "\nlangs: " + ", ".join(post_langs(each["language"]))
            + "\nview: " + each["view_url"]
            + "\npdf: " + each["pdf_url"]
            + "\nlength: " + str(len(list(each["post_text"])))
            + " of " + str(max_len)
            + "\ntext: " + each["post_text"]
            + "\n")
