# written by So Okada so.okada@gmail.com
# parameters of hekiJxiv
# https://github.com/so-okada/hekiJxiv/

# Japan Link Center REST API
jalc_base_url = "https://api.japanlinkcenter.org"

# output format version of the dois resource, /[${ver}/]dois/${doi};
# empty means the API's default.
jalc_dois_version = ""

# rows per doilist page, 1 to 1000
jalc_rows = 1000

# the furthest back a walk may reach, in days.
jalc_from_days_upper_limit = 60

# how many days back a walk asks for when -n is omitted, counted in
# UTC
jalc_from_days = 7

# the DOI prefix of Jxiv, siteId SI/JST.preprint
jalc_prefix = "10.51094"
jalc_timeout = 60

# user agent string for JaLC requests
jalc_user_agent = "hekiJxiv (https://github.com/so-okada/hekiJxiv)"

# sleep between doilist pages of one walk
jalc_page_sleep = 1

# max doilist pages of one walk
jalc_max_pages = 400

# rate limits on JaLC requests, retries included. The online manual,
# https://api.japanlinkcenter.org/api-docs/index.html, states about
# 10 requests a second and 300 a minute.
jalc_calls = 1
jalc_call_period = 1

# per minute
jalc_minute_calls = 240
jalc_minute_period = 60

# how many times a whole doilist walk is tried
jalc_max_trial = 2
# how many times one request is retried on a transient http error
jalc_http_retries = 2
# a cap on a Retry-After header, in seconds
jalc_retry_after_max = 5 * 60

# retry transient server errors only.
jalc_retry_http_codes = (500, 502, 503, 504)
# sleep before retrying a whole doilist walk.
jalc_retry_sleep = 60
# how much of an error page to show.
jalc_error_body_len = 800

# how many new DOIs one run may announce; more than this stops the
# run.
max_new_per_run = 50

# rounds of unescaping and markup stripping for metadata
unescape_rounds = 3

# pause between one bot and the next of a multi bot run
bot_wait = 10

# max post length is 300
max_len = 300

# languages of a title and an author list, best first
preferred_languages = ("ja", "en")

# the bluesky language tag of the daily summary
post_language_default = "en"

# author separator
author_separator = "; "

# posts for new submissions
min_len_authors = 30
min_len_title = 100
# the space before the tail; the ": " after the authors plus one
newsub_spacer = 1
margin = 3

# rate limit for each bot
# https://docs.bsky.app/docs/advanced-guides/rate-limits
an_hour = 60 * 60
post_updates = 1500

# limits independent to specific bots
bsky_createaccts_sleep = 3
overall_bsky_limit_call = 2500
overall_bsky_limit_period = 5 * 60
bsky_sleep = 1
