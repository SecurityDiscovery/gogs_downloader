#!/usr/bin/python

import argparse
import json
import os
import re
import subprocess
import sys
import time

try:
    from BeautifulSoup import BeautifulSoup
except ImportError:
    from bs4 import BeautifulSoup
import requests
from requests.adapters import HTTPAdapter, Retry
from urllib3.exceptions import InsecureRequestWarning
import unicodedata
import re

# Suppress only the single warning from urllib3 needed.
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

parser = argparse.ArgumentParser()

parser.add_argument('-t', '--target', required=True,
                    help="The target. E.g., https://example.com/gogs/ or https://gogs.example.com/")
parser.add_argument('-o', '--output', required=True, default=".",
                    help="The destination directory to clone the repositories to")
parser.add_argument('-s', '--s', required=False, action="store_true", default=False, help="Only show list of repos (not git clone)")
parser.add_argument('-v', '--v', required=False, action="store_true", default=False, help="Verbose?")

args = parser.parse_args()

args.target = args.target if args.target.endswith("/") else args.target + "/"
args.output = args.output if args.output.endswith("/") else args.output + "/"

if args.v:
    print(f"[+] Target: '{args.target}', Output: '{args.output}'")

if not os.path.isdir(args.output):
    print("[-] Output directory does not exist. Verify the output directory exists and try again.\n", file=sys.stderr)
    sys.exit(1)

s = requests.Session()
s.verify = False
s.max_redirects = 2
retries = Retry(total=5,
                backoff_factor=0.1,
                status_forcelist=[500, 502, 503, 504])

s.mount('http://', HTTPAdapter(max_retries=retries))
s.mount('https://', HTTPAdapter(max_retries=retries))


def build_url(page_number):
    return {
        'page': page_number,
        'q': ''
    }


def git(*args):
    return subprocess.check_call(['git', '-c', 'http.sslVerify=false'] + list(args))

def slugify(value, allow_unicode=False):
    """
    Taken from https://github.com/django/django/blob/master/django/utils/text.py
    Convert to ASCII if 'allow_unicode' is False. Convert spaces or repeated
    dashes to single dashes. Remove characters that aren't alphanumerics,
    underscores, or hyphens. Convert to lowercase. Also strip leading and
    trailing whitespace, dashes, and underscores.
    """
    value = str(value)
    if allow_unicode:
        value = unicodedata.normalize('NFKC', value)
    else:
        value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^\w\s-]', '', value.lower())
    return re.sub(r'[-\s]+', '-', value).strip('-_')


def extract_repos(page_text):
    try:
        parsed_html = BeautifulSoup(page_text, 'html.parser')
        div_repo_list = parsed_html.body.find('div', {'class': 'ui repository list'})
        if div_repo_list:
            links = div_repo_list.find_all('a', {'class': 'name'})
            arepos = []
            for link in links:
                link = link.get("href")
                if link[0] == "/":
                    link = link[1:]
                link = f'{args.target}{link}.git'
                arepos = arepos + [link]
            return arepos
    except Exception as e:
        print(e)
        pass


page_number = 0
all_repos = []
while True:
    time.sleep(1)
    try:
        base_request = requests.get(args.target + "explore/repos", params=build_url(page_number))
        repos = extract_repos(base_request.text)
        if args.v:
            print(f"[+] Page {page_number}, Found repos: {len(repos)}")
        if len(repos) > 0:
            page_number = page_number + 1
            all_repos = all_repos + repos
            continue
        break
    except Exception as e:
        print(e, file=sys.stderr)


all_repos = list(set(all_repos))

if args.s:
    if args.v:
        print("Repos found:")
        for repo in all_repos:
            print(f"- {repo}")
    else:
        print(json.dumps(all_repos))
else:
    print(f"[+] Cloning {len(all_repos)} repos")
    for repo in all_repos:
        print(f"[+] Cloning {repo}")
        for ch in ['"', '\\', '?', '#', ';', '\n', '&']:
            c_repo = repo.replace(ch, '')
        out_dir = os.path.join(args.output, slugify(c_repo.replace(args.target, "").replace("/", "-")))
        git("clone", repo, out_dir)