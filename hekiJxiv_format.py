#!/usr/bin/env python3
# written by So Okada so.okada@gmail.com
# a part of hekiJxiv for formatting Jxiv metadata from JaLC
# https://github.com/so-okada/hekiJxiv/

import re
from hekiJxiv_variables import *


# format all new submissions
def format(entries):
    return [format_each(one) for one in entries]


# format each new submission
def format_each(orig_entry):
    entry = orig_entry.copy()
    entry["tail"] = tail(entry)
    fixed_length = len(list(entry["tail"])) + newsub_spacer + margin
    orig_title = entry["title"]

    authors_title = entry["authors"] + entry["title"]
    current_len = len(list(authors_title)) + fixed_length

    # first, a title
    if current_len > max_len:
        difference = current_len - max_len
        current_len_title = len(list(entry["title"]))
        lim = max(min_len_title, current_len_title - difference)
        entry["title"] = simple(entry["title"], lim)

    authors_title = entry["authors"] + entry["title"]
    current_len = len(list(authors_title)) + fixed_length

    # second, authors
    if current_len > max_len:
        difference = current_len - max_len
        current_len_authors = len(list(entry["authors"]))
        lim = max(min_len_authors, current_len_authors - difference)
        entry["authors"] = authors(
            entry["authors"], lim, entry.get("authors_surnames", ""))

    # third, a longer title if the length of authors' names becomes shorter
    entry["title"] = orig_title
    authors_title = entry["authors"] + entry["title"]
    current_len = len(list(authors_title)) + fixed_length

    if current_len > max_len:
        difference = current_len - max_len
        current_len_title = len(list(entry["title"]))
        lim = max(min_len_title, current_len_title - difference)
        entry["title"] = simple(entry["title"], lim)

    entry["post_text"] = post_text(entry)
    return entry


# the doi link
def tail(entry):
    return entry["url"]


def post_text(entry):
    prefix = entry["authors"] + ": " if entry["authors"] else ""
    text = prefix + entry["title"]
    if entry["tail"]:
        text = text + " " + entry["tail"] if text else entry["tail"]
    return text


# a simple text cut
def simple(orig, lim):
    orig = orig.strip()
    wlen = len(list(orig))
    if wlen <= lim:
        return orig

    while wlen > lim:
        orig = orig[:-1]
        wlen = len(list(orig))

    return orig[:-3] + "..."


# formatting authors' names; surnames come from jalc_parser.py
def authors(orig, lim, surnames=""):
    if lim < 1:
        return ""
    if len(list(orig)) <= lim:
        return orig

    no_paren = noparen(orig)
    if len(list(no_paren)) <= lim:
        return no_paren

    if surnames and len(list(surnames)) <= lim:
        return surnames

    et_al = etal(no_paren)
    if len(list(et_al)) <= lim:
        return et_al

    return ""


def noparen(test_str):
    ret = ""
    skip = 0
    for i in test_str:
        if i == "(":
            skip += 1
        elif i == ")":
            skip -= 1
        elif skip == 0:
            ret += i
    ret = re.sub(r"[ ]+;", ";", ret)
    ret = re.sub(r"[ ]+$", "", ret)
    return ret


# cf. https://stackoverflow.com/questions/14596884/remove-text-between-and-in-python/14598135#14598135


def etal(orig):
    names = orig.split(author_separator.strip())
    first_author = names[0].strip()
    return first_author + ", et al."


