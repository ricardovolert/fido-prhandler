import logging
import json
import tempfile
import os
import re
import requests
import shutil
import hglib
from unidiff import PatchSet
import ConfigParser

IRC_TARGET = "irc://chat.freenode.net/#yt"
HOME_DIR = "/home/fido/fido"
REPOS_DIR = "/tmp/jenkins_doc"

CONFIG = ConfigParser.ConfigParser()
CONFIG.read('yt-fido.cfg')
JENKINS_TOKEN = CONFIG.get('jenkins', 'token')
JENKINS_URL = 'https://tests.yt-project.org'
debug = False


def _get_local_repo(path):
    repo_path = os.path.join(REPOS_DIR, path)
    if not os.path.isdir(repo_path):
        os.makedirs(repo_path)
        repo = hglib.clone("https://bitbucket.org/%s" % path, repo_path)
    repo = hglib.open(repo_path)
    repo.pull()
    repo.update(rev="yt", clean=True)
    repo.close()
    temp_repo = tempfile.mkdtemp()
    hglib.clone(repo_path, temp_repo)
    return temp_repo, hglib.open(temp_repo)


def _touches_docs(source_repo, rev):
    cwd = os.getcwd()
    temp_repo, repo = _get_local_repo("yt_analysis/yt")
    os.chdir(temp_repo)
    repo.update(rev="yt", clean=True)
    tip = repo.identify(id=True).strip()
    repo.pull("https://bitbucket.org/%s" % source_repo, update=False,
              rev=rev)
    anc = repo.log(revrange="max({0}::{1}) and not {0}".format(tip, rev))
    if len(anc) > 0:
        repo.update(rev=rev)
        diff = repo.diff(revs="%s..%s" % (tip, rev),
                         git=True, unified=4).split('\n')
    else:
        try:
            repo.merge(rev=rev, cb=hglib.merge.handlers.noninteractive,
                       tool="internal:merge")
            diff = repo.diff(git=True, unified=4).split('\n')
        except hglib.error.CommandError:
            diff = []
    diff = PatchSet(diff, encoding='utf-8')
    repo.close()
    os.chdir(cwd)
    shutil.rmtree(temp_repo, ignore_errors=True)
    files = [hunk.target_file[2:] for hunk in diff
             if hunk.is_added_file or hunk.is_modified_file]

    if filter(re.compile("^doc/.*$").match, files):
        return True
    return False


def _jenkins_hook(job):
    return "{}/job/{}/build?token={}".format(JENKINS_URL, job, JENKINS_TOKEN)


def pullrequest_created(data):
    dest = data["pullrequest"]["destination"]
    logging.debug("destination: hash=%s branch=%s repo=%s" %
                  (dest["commit"]["hash"], dest["branch"]["name"],
                   dest["repository"]["full_name"]))

    source = data["pullrequest"]["source"]
    logging.debug("source: hash=%s branch=%s repo=%s" %
                  (source["commit"]["hash"], source["branch"]["name"],
                   source["repository"]["full_name"]))

    msg = "will test PR {} by {}".format(data["pullrequest"]["id"],
                                         data["actor"]["display_name"])

    params = [
        {'name': 'IRKMSG', 'value': msg},
        {'name': 'YT_REPO', 'value': source["repository"]["full_name"]},
        {'name': 'YT_REV', 'value': source["commit"]["hash"]},
        {'name': 'YT_DEST', 'value': dest["commit"]["hash"]}
    ]

    payload = {
        'json': json.dumps({'parameter': params}),
        'Submit': 'Build'
    }

    jobs = ["yt_testsuite_dev"]
    if _touches_docs(source["repository"]["full_name"],
                     source["commit"]["hash"]):
        jobs.append("yt_docs")

    for job in jobs:
        r = requests.post(_jenkins_hook(job), data=payload)
        if r.status_code != 200:
            logging.warn("Failed to submit {}".format(job))


def pullrequest_updated(data):
    pullrequest_created(data)


def pullrequest_fullfilled(data):
    pass
