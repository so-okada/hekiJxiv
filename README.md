# Application Info

hekiJxiv delivers [Jxiv](https://jxiv.jst.go.jp/) daily new preprints
and daily summaries by bluesky posts. heki means azure (碧/へき) in Japanese. We use python3 scripts with atproto.
hekiJxiv is not affiliated with JST.


## Setup

* Install atproto, pandas, ratelimit, and nameparser.

	```
	% pip3 install atproto pandas ratelimit nameparser
	```

* Let hekiJxiv.py be executable.

	 ```
	 % chmod +x hekiJxiv.py
	 ```

*  Put the following python scripts in the same directory.

	- hekiJxiv.py
	- hekiJxiv_post.py
	- hekiJxiv_format.py
	- hekiJxiv_daily_feed.py
	- jalc_parser.py
	- hekiJxiv_variables.py


* Configure switches.json and logfiles.json in the tests directory
  for your settings.

	- switches.json specifies bluesky access keys and whether to use
	new submissions and daily summaries by hekiJxiv.  Each top level
	key is a label of one bot.

    - logfiles.json indicates log file locations for post summaries
	and posts.  You can check their formats by
	ppbot_post_summaries.csv and ppbot_posts.csv in the
	tests/logfiles directory.  hekiJxiv needs a post log.  It is
	what keeps a preprint from being announced twice, and it keeps
		the daily summary from being posted twice a day.
		Live posting requires nonempty `post_log` and `username` settings,
		and `post_summary_log` when summaries are enabled. A configured
		CSV file may be created by the first live run.

* Configure hekiJxiv_variables.py for your settings.

   - hekiJxiv_variables.py assigns format parameters for hekiJxiv
   posts and access frequencies for JaLC and bluesky.

## Notes

* jalc_parser.py is a client of the JaLC REST API for hekiJxiv. We use this
  via hekiJxiv_daily_feed.py to regularly obtain data. It walks
  `/doilist/10.51094` and fetches `/dois/{doi}` for the DOIs it has not
  seen before.

* Metadata license.  JaLC's terms for its general data service
  ([一般向けデータ提供サービス利用規約](https://japanlinkcenter.org/top/doc/JaLC_general_riyoukiyaku.pdf))
  govern what hekiJxiv may repost.  Article 5.2 grants free use of
  DOIs, bibliographic data, and URIs for any purpose, subject to the
  other provisions of the terms
  (「利用者は、DOI、書誌データ及びURIを利用目的及び態様を問わず自由に
  利用できますが、本規約の定めに従うものとします」).  Article 3 defines the
  bibliographic data (書誌データ)
  of a DOI-registered content item as its title, authors, journal
  name, volume and issue, first page, ISBN, ISSN, and the like
  (「DOIを付与されたコンテンツに係る標題、著者、収録ジャーナル名、
  収録巻・号、開始ページ、ISBN、ISSN等」).  That
  grant is what covers the titles, author names, dates, and links in
  hekiJxiv posts, except abstracts covered in Article 5.3.

* API usage.  Metadata comes from the provided method, the Japan Link
  Center (JaLC)
  [REST API](https://japanlinkcenter.org/top/doc/REST_API_Functional_Description.pdf).
  Its [online manual](https://api.japanlinkcenter.org/api-docs/index.html)
  states the rate limits, which hekiJxiv keeps well under (see
  hekiJxiv_variables.py).

* What is new is what has not been seen, not what is recent.  A
  daily run asks JaLC's doilist for the last `jalc_from_days` days of
  registrations and updates (the `from` parameter; `-n` overrides the
  reach, capped by `jalc_from_days_upper_limit`) and subtracts the seen
  log — the same window-plus-log logic aozoraSciELO uses against
  OAI-PMH.  The date only bounds the question put to JaLC; the log
  alone decides what is announced, because the window mixes newly
  published preprints with old records whose metadata was merely
  touched.  A Jxiv DOI suffix says nothing about when its preprint
  appeared: suffixes are assigned at submission and preprints publish
  out of order after screening, sometimes years after their numbers
  were assigned, so a largest-suffix watermark cannot work.  The walk
  verifies its count against the total the envelope declares.

* A DOI joins the post log only once it has been announced.  Not when
  it is walked, and not when its metadata arrives.  A run that dies
  between the two, or a bluesky call that fails, leaves the preprint to
  be announced next time.  A DOI whose `/dois/` fetch returns 404 is
  left unlogged on purpose: a DOI can be registered before its preprint
  clears screening, and it is announced when it publishes.

* hekiJxiv only posts the first version announcement.  A revision
  keeps its DOI, so the post log drops it, and the DOI link of the
  original post always resolves to the latest version on Jxiv.

* The post log starts empty and is created by the first live run.  A
  missing log therefore risks at most one window's worth of posts, and
  a run that finds more than `max_new_per_run` unannounced DOIs stops
  instead of posting: that is what a lost or truncated post log looks
  like, not a busy day.  If the post log cannot be read, hekiJxiv
  posts nothing for that label rather than risk a second
  announcement.

* Bilingual metadata.  Many Jxiv records carry both Japanese and
  English titles and author names, language tagged, and neither is
  guaranteed.  hekiJxiv posts the original: Japanese where a record
  has it, English otherwise, and whatever the record does carry as a
  last resort.  The bluesky language tag follows the title the post
  actually quotes rather than a fixed default.

* Outputs of hekiJxiv can differ from the Jxiv web pages. This can be
  due to bugs in my scripts, a lag before Jxiv metadata reaches JaLC,
  or other errors.

* A daily summary is posted once per UTC day per bot, and the summary
  log is what marks a day as already done.  When retrieval fails
  outright and no summary has gone out yet that day, hekiJxiv still
  posts a summary reporting no new preprints, so that a silent failure
  does not look like a quiet day.  A bot with `summaries` of 0 reports
  neither.


## Usage

```
% ./hekiJxiv.py -h
usage: hekiJxiv.py [-h] --switches_keys SWITCHES_KEYS [--logfiles LOGFILES]
                     [--dois DOIS] [--num_last_days NUM_LAST_DAYS]
                     [--max_new MAX_NEW] [--mode {0,1}]

Jxiv daily new preprints by posts and daily summaries by posts, from Japan
Link Center metadata.

options:
  -h, --help            show this help message and exit
  --switches_keys SWITCHES_KEYS, -s SWITCHES_KEYS
                        output switches and api keys in json
  --logfiles LOGFILES, -l LOGFILES
                        log file names in json
  --dois DOIS           a comma separated list of dois to fetch and format
                        instead of walking the doilist, such as
                        10.51094/jxiv.10 or the bare jxiv.10. Prints formatted
                        posts without posting or writing files. For checking
                        metadata and post formatting.
  --num_last_days NUM_LAST_DAYS, -n NUM_LAST_DAYS
                        how many last days of registrations and updates to
                        ask JaLC for, 0 for today alone,
                        jalc_from_days_upper_limit at most. jalc_from_days
                        of hekiJxiv_variables.py when omitted. What is new
                        is still decided by the post log; this only bounds
                        the question put to JaLC.
  --max_new MAX_NEW     how many unseen dois one run may announce.
                        max_new_per_run of hekiJxiv_variables.py when
                        omitted. Raise it only once you know why a run found
                        more than that.
  --mode {0,1}, -m {0,1}
                        1 for bsky and 0 for stdout only
```


## Sample stdouts

* Checking a few preprints without walking the list or writing anything:

	```
	% ./hekiJxiv.py -s tests/switches.json --dois jxiv.xxxx,jxiv.yyyy
	JaLC request: https://api.japanlinkcenter.org/dois/10.51094%2Fjxiv.xxxx

	doi: 10.51094/jxiv.xxxx
	date: xxxx-xx-xx
	langs: ja
	view: https://jxiv.jst.go.jp/index.php/jxiv/preprint/view/xxxx
	pdf: https://jxiv.jst.go.jp/xxxx
	length: xx of 300
	text: XXX YYY; ZZZ WWW: xxxxxxxxxxxxxxxxxxxxxxxx https://doi.org/10.51094/jxiv.xxxx
	```

* A dry run of new preprints and a daily summary:

	```
	% ./hekiJxiv.py -s tests/switches.json -l tests/logfiles.json -m 0
	**process started at xxxx-xx-xx xx:xx:xx (UTC)
	starting retrieval/new submissions for Jxiv
	getting new entries for Jxiv
	JaLC request: https://api.japanlinkcenter.org/doilist/10.51094?rows=1000&page=1&from=xxxx-xx-xx
	the doilist declares 23 doi(s) over 1 page(s)
	JaLC request: https://api.japanlinkcenter.org/dois/10.51094%2Fjxiv.xxxx
	...
	walked 23 doi(s) in 1 page(s) from xxxx-xx-xx for Jxiv
	2 doi(s) not yet announced for Jxiv
	new submissions for Jxiv

	utc: xxxx-xx-xx xx:xx:xx
	label: Jxiv
	preprint id:
	post mode: 0
	langs: en
	url:
	text: [xxxx-xx-xx Tue (UTC), 2 new preprints found for Jxiv]

	utc: xxxx-xx-xx xx:xx:xx
	label: Jxiv
	preprint id: 10.51094/jxiv.xxxx
	post mode: 0
	langs: ja
	url:
	text: xxxx; xxxx: xxxxxxxxxxxxxxxxxxxx https://doi.org/10.51094/jxiv.xxxx

	....

	**process ended at xxxx-xx-xx xx:xx:xx (UTC)
	**elapsed time from the start: xx:xx:xx
	```

* A summary already posted today stops the run before any request:

	```
	getting new entries for Jxiv
	Jxiv already posted for today
	```


## Versions

* 0.0.1, initial release.


## Bot List

* 


## Author
So Okada, so.okada@gmail.com, https://so-okada.github.io/

## Motivation
This is an open-science practice
(see https://github.com/so-okada/twXiv#motivation).  Since 2013-04, the
author has been running twitter bots for all arXiv math categories.
Since 2023-01, the author has been running mastodon bots for
all arXiv categories with [toXiv](https://github.com/so-okada/toXiv).
Since 2025-02, the author has been running bluesky bots for arXiv
categories with [bXiv](https://github.com/so-okada/bXiv).
Since 2026-07, [aozoraSciELO](https://github.com/so-okada/aozoraSciELO)
extends the practice to
[SciELO Preprints](https://preprints.scielo.org/). Since 2026-09,
[aoiHAL](https://github.com/so-okada/aoiHAL) extends it to
[HAL](https://hal.science/), and hekiJxiv
extends it to [Jxiv](https://jxiv.jst.go.jp/), the preprint server of
the Japan Science and Technology Agency (JST).

## License
The scripts of hekiJxiv are under
[AGPLv3](https://www.gnu.org/licenses/agpl-3.0.en.html).
