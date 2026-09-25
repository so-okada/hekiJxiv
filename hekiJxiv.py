#!/usr/bin/env python3
# written by So Okada so.okada@gmail.com
# a main interface of hekiJxiv
# https://github.com/so-okada/hekiJxiv/

import json
import argparse
import traceback
import hekiJxiv_post as hJp

parser = argparse.ArgumentParser(
    description='Jxiv daily new preprints by posts and daily summaries '
    'by posts, from Japan Link Center metadata.')
parser.add_argument("--switches_keys",
                    "-s",
                    required=True,
                    default='',
                    help="output switches and api keys in json")
parser.add_argument("--logfiles",
                    "-l",
                    default='',
                    help="log file names in json")
parser.add_argument("--dois",
                    default='',
                    help="a comma separated list of dois to fetch and "
                    "format instead of walking the doilist, such as "
                    "10.51094/jxiv.10 or the bare jxiv.10. Prints formatted "
                    "posts without posting or writing files. For checking metadata and post "
                    "formatting.")
parser.add_argument("--num_last_days",
                    "-n",
                    type=int,
                    default=None,
                    help="how many last days of registrations and "
                    "updates to ask JaLC for, 0 for today alone. "
                    "jalc_from_days of hekiJxiv_variables.py when "
                    "omitted. Preprints not in the post log and "
                    "issued since then are posted.")
parser.add_argument("--max_post",
                    type=int,
                    default=None,
                    help="how many preprints one run may post; the rest "
                    "stay unlogged. max_post_per_run of "
                    "hekiJxiv_variables.py when omitted.")
parser.add_argument("--mode",
                    "-m",
                    choices=[0, 1],
                    type=int,
                    default='0',
                    help='1 for bsky and 0 for stdout only')


args = parser.parse_args()
switches = args.switches_keys
logfiles = args.logfiles
pt_mode = args.mode
max_post = args.max_post
num_last_days = args.num_last_days

if max_post is not None and max_post < 0:
    raise Exception('max_post cannot be negative')
if num_last_days is not None and num_last_days < 0:
    raise Exception('num_last_days cannot be negative')

try:
    f = open(switches)
except Exception:
    traceback.print_exc()
    raise Exception('can not obtain output switches and api keys')
switches = json.load(f)

if logfiles:
    try:
        f = open(logfiles)
    except Exception:
        traceback.print_exc()
        raise Exception('can not obtain log filenames')
    logfiles = json.load(f)

if args.dois:
    hJp.show_dois(args.dois)
else:
    hJp.main(switches, logfiles, pt_mode, max_post, num_last_days)
