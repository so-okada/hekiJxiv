#!/usr/bin/env python3
# written by So Okada so.okada@gmail.com
# a JaLC REST API client of Jxiv preprints for hekiJxiv
# https://github.com/so-okada/hekiJxiv/

import re
import html
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from ratelimit import limits, sleep_and_retry

from hekiJxiv_variables import *

# the human page of a preprint; NNNN is the OJS submission id.
JXIV_VIEW = "https://jxiv.jst.go.jp/index.php/jxiv/preprint/view/"
DOI_RESOLVER = "https://doi.org/"


# a request that fails the same way on every try
class JaLCRequestError(Exception):
    pass


# a 404: an unpublished DOI or a doilist page past the end
class JaLCNotFound(JaLCRequestError):
    pass


# one http attempt at the JaLC API; every request, retries included,
# passes here under the rate limits.
@sleep_and_retry
@limits(calls=jalc_minute_calls, period=jalc_minute_period)
@sleep_and_retry
@limits(calls=jalc_calls, period=jalc_call_period)
def jalc_call(request):
    with urllib.request.urlopen(request, timeout=jalc_timeout) as r:
        return r.read()


# one request with retries on transient http errors
def jalc_request(path, params=None):
    url = jalc_base_url.rstrip("/") + path
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    print("JaLC request: " + url)
    headers = {"Accept": "application/json"}
    if jalc_user_agent:
        headers["User-Agent"] = jalc_user_agent
    request = urllib.request.Request(url, headers=headers)

    for trial in range(jalc_http_retries + 1):
        try:
            raw = jalc_call(request)
            break
        except urllib.error.HTTPError as e:
            body = error_body(e)
            print("**JaLC http error " + str(e.code) + " " + str(e.reason)
                  + "\nurl: " + url
                  + ("\nbody: " + body if body else ""))
            if e.code in jalc_retry_http_codes and trial < jalc_http_retries:
                wait = retry_after(e.headers.get("Retry-After"))
                print("retrying in " + str(wait) + "s")
                time.sleep(wait)
                continue
            if e.code == 404:
                raise JaLCNotFound("http 404 for " + url) from e
            if e.code not in jalc_retry_http_codes:
                # a client error
                raise JaLCRequestError(
                    "http " + str(e.code) + " for " + url
                    + (": " + body if body else "")) from e
            raise

    try:
        return json.loads(raw.decode("utf-8", "replace"))
    except ValueError as e:
        raise JaLCRequestError("unparsable json from " + url) from e


def error_body(e):
    try:
        raw = e.read(jalc_error_body_len * 4)
    except Exception:
        return ""
    text = raw.decode("utf-8", "replace")
    return clean(text)[:jalc_error_body_len]


def retry_after(value):
    if value and value.strip().isdigit():
        # capped
        return min(int(value.strip()), jalc_retry_after_max)
    return jalc_page_sleep


# ---------------------------------------------------------------- doilist


class doi_list:
    """One walk of /doilist/{prefix}. With from_days, the from
    parameter limits the walk to DOIs registered or updated in the
    last so many days; without it, the walk takes everything. The
    first page declares total and totalPages, and `complete` records
    whether the walk collected the declared total.
    """

    def __init__(self, prefix=None, from_days=None):
        prefix = prefix or jalc_prefix
        from_date = ""
        # 0 is today alone
        if from_days is not None:
            cutoff = (datetime.now(timezone.utc)
                      - timedelta(days=from_days)).date()
            from_date = cutoff.isoformat()
        dois = {}
        declared = 0
        declared_pages = 0
        pages = 0
        ended = False

        while pages < jalc_max_pages:
            page = pages + 1
            params = {"rows": jalc_rows, "page": page}
            if from_date:
                params["from"] = from_date
            try:
                payload = jalc_request("/doilist/" + prefix, params)
            except JaLCNotFound:
                # a page past the end is a 404; an empty window on
                # page 1 is allowed, an empty whole archive is not.
                if page == 1 and not from_date:
                    raise
                ended = True
                break
            pages = page
            if page == 1:
                declared = find_number(payload, TOTAL_KEYS)
                declared_pages = find_number(payload, PAGE_KEYS)
                if declared or declared_pages:
                    print("the doilist declares " + str(declared)
                          + " doi(s) over " + str(declared_pages)
                          + " page(s)")
            found = list_items(payload)
            if not found:
                ended = True
                break
            absorb(dois, found)
            if declared_pages and page >= declared_pages:
                ended = True
                break
            time.sleep(jalc_page_sleep)
        else:
            print("**reached jalc_max_pages of " + str(jalc_max_pages)
                  + ", the doilist walk is incomplete")

        # a declared total decides completeness.
        if declared:
            complete = len(dois) == declared
            if not complete:
                print("**collected " + str(len(dois)) + " doi(s) but the"
                      + " doilist declares " + str(declared)
                      + ". The walk is incomplete.")
        else:
            complete = ended
            if pages:
                print("**the doilist declared no total this parser could"
                      + " read, so completeness is inferred from where"
                      + " the list ended rather than verified.")

        self.prefix = prefix
        self.from_date = from_date
        self.pages = pages
        self.dois = set(dois)
        self.updated = dois
        self.complete = complete
        self.declared = declared
        self.total = len(dois)


def absorb(dois, items):
    for one in items:
        doi = item_doi(one)
        if doi:
            dois[doi] = text_of(one.get("updated_date"))


# keys of the totals in the response; "rows" and "page" are not
# totals.
TOTAL_KEYS = ("total", "total_count", "totalcount", "total_results",
              "totalresults", "num_found", "numfound")
PAGE_KEYS = ("totalpages", "total_pages", "total_page", "totalpage",
             "last_page", "lastpage", "page_count", "pagecount")


def find_number(payload, keys, depth=0):
    if depth > 4 or not isinstance(payload, dict):
        return 0
    best = 0
    for key, value in payload.items():
        if isinstance(value, (dict,)):
            best = max(best, find_number(value, keys, depth + 1))
            continue
        if str(key).lower().replace("-", "_") in keys:
            number = as_int(value)
            if number > best:
                best = number
    return best


def as_int(value):
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value if value > 0 else 0
    text = text_of(value)
    if text.isdigit():
        return int(text)
    return 0


# the first list of dicts that carries DOIs
def list_items(payload):
    for candidate in walk_lists(payload):
        if any(item_doi(one) for one in candidate if isinstance(one, dict)):
            return [one for one in candidate if isinstance(one, dict)]
    return []


def walk_lists(node, depth=0):
    if depth > 4:
        return
    if isinstance(node, list):
        yield node
        return
    if isinstance(node, dict):
        for value in node.values():
            for found in walk_lists(value, depth + 1):
                yield found


# a doilist item carries {dois: {doi, url}, ra, siteId, updated_date};
# a bare {doi: ...} is accepted too.
def item_doi(item):
    if not isinstance(item, dict):
        return ""
    inner = item.get("dois")
    if isinstance(inner, dict):
        doi = text_of(inner.get("doi"))
        if doi:
            return doi
    return text_of(item.get("doi"))


# ------------------------------------------------------------ one record


# the metadata of one preprint, or None on a 404; such a DOI stays
# unseen.
def fetch_doi(doi):
    path = "/dois/" + urllib.parse.quote(doi, safe="")
    if jalc_dois_version:
        path = "/" + jalc_dois_version.strip("/") + path
    try:
        payload = jalc_request(path)
    except JaLCNotFound:
        return None
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        data = payload if isinstance(payload, dict) else {}
    return record(doi, data)


def record(doi, data, updated_date=""):
    titles = language_values(data.get("title_list"), ("title", "name"))
    # a ja-tagged title without CJK is retagged en; names are not.
    titles = [("en" if one_lang == "ja" and not is_cjk(one_title)
               else one_lang, one_title)
              for one_lang, one_title in titles]
    lang, title = choose(titles)
    if not title:
        # no title, no announcement; the DOI stays unseen.
        print("**no usable title for " + doi)
        return None

    fulls, lasts = creator_names(data.get("creator_list"), lang)
    suffix = doi.split("/", 1)[-1]
    numeric = re.sub(r"^\D+", "", suffix)

    entry = {}
    entry["doi"] = doi
    # the post log key
    entry["id"] = doi
    entry["title"] = title
    entry["language"] = lang
    entry["authors"] = author_separator.join(fulls)
    entry["authors_surnames"] = author_separator.join(lasts)
    # the date of the latest version, not of the first
    entry["date"] = publication_date(data)
    # for the skip line only
    entry["version"] = edition_version(data)
    # the date of the first version
    entry["issued"] = issued_date(data)
    entry["updated_date"] = updated_date
    # what a post links
    entry["url"] = DOI_RESOLVER + doi
    entry["view_url"] = JXIV_VIEW + numeric if numeric else ""
    entry["pdf_url"] = pdf_url(data)
    # description_list is not read.
    return entry


# ---------------------------------------------------------- languages


# ja-JP, jpn and JA all name the same language.
THREE_TO_TWO = {"jpn": "ja", "eng": "en", "jan": "ja"}


def norm_lang(value):
    value = (value or "").strip().lower()
    if not value:
        return ""
    value = re.split(r"[-_]", value)[0]
    if value in THREE_TO_TWO:
        return THREE_TO_TWO[value]
    if re.fullmatch(r"[a-z]{2}", value):
        return value
    return ""


def lang_of(item):
    if not isinstance(item, dict):
        return ""
    for key in ("lang", "language", "xml:lang"):
        if item.get(key):
            return norm_lang(item.get(key))
    return ""


# a list of language tagged dicts flattened to (language, text) pairs.
def language_values(items, keys):
    result = []
    if not isinstance(items, list):
        return result
    for one in items:
        if not isinstance(one, dict):
            continue
        for key in keys:
            value = clean(text_of(one.get(key)))
            if value:
                result.append((lang_of(one), value))
                break
    return result


# the first value in a preferred language, else the first value
def choose(pairs):
    for wanted in preferred_languages:
        for lang, value in pairs:
            if lang == wanted and value:
                return lang, value
    for lang, value in pairs:
        if value:
            return lang, value
    return "", ""


# ------------------------------------------------------------- creators


def creator_names(creators, lang):
    fulls = []
    lasts = []
    if not isinstance(creators, list):
        return fulls, lasts
    for one in creators:
        variants = name_variants(one)
        pick = variants.get(lang)
        if not pick:
            for wanted in preferred_languages:
                if variants.get(wanted):
                    pick = variants[wanted]
                    break
        if not pick:
            pick = next((v for v in variants.values() if v), None)
        if pick and pick[0]:
            fulls.append(pick[0])
            lasts.append(pick[1] or pick[0])
    return fulls, lasts


# {language: (full name, family name)} for one creator; a flat name
# is accepted as well.
def name_variants(creator):
    if not isinstance(creator, dict):
        return {}
    entries = None
    for key in ("names", "name_list", "name"):
        if isinstance(creator.get(key), list):
            entries = creator[key]
            break
    if entries is None:
        entries = [creator]

    variants = {}
    for one in entries:
        if not isinstance(one, dict):
            continue
        lang = lang_of(one)
        last = clean(text_of(first_key(
            one, ("last_name", "family_name", "familyName", "surname"))))
        given = clean(text_of(first_key(
            one, ("first_name", "given_name", "givenName", "forename"))))
        flat = clean(text_of(first_key(one, ("name", "full_name", "value"))))

        if last or given:
            full = join_name(last, given)
        elif flat:
            full = flat
            last = surname_of(flat)
        else:
            continue
        if full:
            variants[lang] = (full, last)
    return variants


def first_key(mapping, keys):
    for key in keys:
        if mapping.get(key):
            return mapping[key]
    return ""


CJK = re.compile(
    r"[぀-ヿ㐀-䶿一-鿿豈-﫿]")


def is_cjk(text):
    return bool(CJK.search(text or ""))


# 岡田創 in Japanese, So Okada in English.
def join_name(last, given):
    if last and given:
        if is_cjk(last) or is_cjk(given):
            return last + given
        return given + " " + last
    return last or given


# the family name of a flat name; a CJK name is taken whole.
def surname_of(name):
    name = (name or "").strip()
    if not name:
        return ""
    if "," in name:
        return name.split(",")[0].strip() or name
    if is_cjk(name):
        return name
    try:
        from nameparser import HumanName
        return HumanName(name).last or name
    except Exception:
        return name


# ----------------------------------------------------------------- misc


def publication_date(data):
    node = data.get("publication_date")
    if not isinstance(node, dict):
        return ""
    year = text_of(first_key(node, ("year", "publication_year")))
    month = text_of(first_key(node, ("month", "publication_month")))
    day = text_of(first_key(node, ("day", "publication_day")))
    if not year:
        return ""
    parts = [year.zfill(4)]
    if month:
        parts.append(month.zfill(2))
        if day:
            parts.append(day.zfill(2))
    return "-".join(parts)


def edition_version(data):
    node = data.get("edition")
    if not isinstance(node, dict):
        return ""
    return text_of(node.get("version"))


# the date_list item of type Issued, "" when there is none
def issued_date(data):
    items = data.get("date_list")
    if not isinstance(items, list):
        return ""
    for one in items:
        if (isinstance(one, dict)
                and text_of(one.get("type")).lower() == "issued"):
            return text_of(one.get("date"))
    return ""


# the relation_list item labelled fullTextPdf, else any .pdf url
def pdf_url(data):
    relations = data.get("relation_list")
    if not isinstance(relations, list):
        return ""
    for one in relations:
        if not isinstance(one, dict):
            continue
        relation = text_of(one.get("relation")).lower()
        content = text_of(one.get("content"))
        if relation == "fulltextpdf" and content.startswith("http"):
            return content
    for one in relations:
        if not isinstance(one, dict):
            continue
        for value in one.values():
            text = text_of(value)
            if text.startswith("http") and ".pdf" in text.lower():
                return text
    return ""


def text_of(value):
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return str(value)
    if not isinstance(value, str):
        return ""
    return value.strip()


# strip html markup and character references
def clean(text):
    if not text:
        return ""
    # unescape and strip until the text stops changing.
    text = strip_markup(text)
    for round in range(unescape_rounds):
        unescaped = html.unescape(text)
        if unescaped == text:
            break
        text = strip_markup(unescaped)
    # normalize whitespace, U+3000 included.
    text = text.replace("\xa0", " ").replace("\u200b", "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def strip_markup(text):
    text = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", text)
    text = re.sub(r"(?i)<br\s*/?>|</p\s*>|</div\s*>|</li\s*>", " ", text)
    # only a tag-shaped <...>, so that "a < b" survives.
    return re.sub(r"(?i)</?[a-z][a-z0-9]*(\s[^<>]*)?/?>", "", text)
