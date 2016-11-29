import logging
import json
import tempfile
import os
import re
import requests
import shutil
import hglib
from unidiff import PatchSet
from requests_oauthlib import OAuth1Session

IRC_TARGET = "irc://chat.freenode.net/#yt"
HOME_DIR = "/home/fido/fido"
REPOS_DIR = "/tmp/jenkins_doc"
SKIP_TEST_KEY = ("wip", "notest")

JENKINS_TOKEN = os.environ.get("JENKINS_TOKEN", None)
JENKINS_URL = os.environ.get("JENKINS_URL", "https://tests.yt-project.org")
debug = False

CONTRIBUTORS = None


def _new_contributor(uuid):
    global CONTRIBUTORS
    if CONTRIBUTORS is None:
        api_url = 'https://api.bitbucket.org'
        prs = api_url + (
            '/2.0/repositories/{username}/{repo_slug}/pullrequests'
        )

        bb = OAuth1Session(
            os.environ.get("OAUTH_KEY"),
            client_secret=os.environ.get("OAUTH_SECRET"),
            resource_owner_key=os.environ.get("OAUTH_TOKEN"),
            resource_owner_secret=os.environ.get("OAUTH_TOKEN_SECRET"))

        def get_users(url, contributors=set()):
            logging.debug('Getting contributors... make take a while.')
            data = bb.get(url, params={'state': ''}).json()
            contributors.update(
                set([_['author']['uuid'] for _ in data['values']]))
            if 'next' in data:
                get_users(data['next'], contributors)
            return contributors

        url = prs.format(username='yt_analysis', repo_slug='yt')
        CONTRIBUTORS = get_users(url)
        bb.close()

    return uuid in CONTRIBUTORS


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
        diff = repo.diff(revs=[tip, rev], git=True, unified=4).split('\n')
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


def _comment_on_pullrequest(user, repo, prno, message, append=True):
    """
    Comment as fido on a pull request

    Parameters
    ----------
    user : str
        Bitbucket username
    repo : str
        Bitbucket repository name
    prno : int
        Pullrequest id
    message : str
        Comment to be added
    append : bool (optional)
        If True and at least one comment by fido already exists, it will append
        message to the last comment.
    """
    bb = OAuth1Session(
        os.environ.get("OAUTH_KEY"),
        client_secret=os.environ.get("OAUTH_SECRET"),
        resource_owner_key=os.environ.get("OAUTH_TOKEN"),
        resource_owner_secret=os.environ.get("OAUTH_TOKEN_SECRET"))
    api_url = 'https://api.bitbucket.org'
    if append:
        comments = api_url + (
            '/1.0/repositories/{username}/{repo_slug}/pullrequests'
            '/{pull_request_id}/comments'
        )
        url = comments.format(username=user, repo_slug=repo,
                              pull_request_id=prno)
        resp = bb.get(url)
        comments = json.loads(resp.content.decode('utf8'))
        fido_comments = [
            _ for _ in comments
            if _['author_info']['username'] == 'yt-fido' and not _['deleted']
        ]
        if fido_comments:
            current_content = fido_comments[-1]['content']
            if not current_content.startswith('*'):
                current_content = '* ' + current_content
            if not current_content.endswith('\n'):
                current_content += '\n'
            if not message.startswith('*'):
                message = '* ' + message
            current_content += message
            bb.put(url + '/%i' % fido_comments[-1]['comment_id'],
                   data={'content': current_content})
        else:
            bb.post(url, data={'content': message})
    else:
        bb.post(url, data={'content': message})


def _run_tests_yt(data):
    if any(x in data["pullrequest"]["title"].lower() for x in SKIP_TEST_KEY):
        return
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

    jobs = ["yt_testsuite"]
    if _touches_docs(source["repository"]["full_name"],
                     source["commit"]["hash"]):
        jobs.append("yt_docs")

    for job in jobs:
        r = requests.post(_jenkins_hook(job), data=payload)
        if r.status_code != 200:
            logging.warn("Failed to submit {}".format(job))


def pullrequest_updated(data):
    if data['repository']['full_name'] == 'yt_analysis/yt':
        _run_tests_yt(data)
    else:
        user, repo = data['repository']['full_name'].split('/')
        prno = data['pullrequest']['id']
        message = 'Hi there!'
        _comment_on_pullrequest(user, repo, prno, message)


def pullrequest_created(data):
    global CONTRIBUTORS
    if data['repository']['full_name'] == 'yt_analysis/yt':
        user = data['actor']['uuid']
        if _new_contributor(user):
            CONTRIBUTORS.add(user)
            # do something here
    pullrequest_updated(data)


def pullrequest_fulfilled(data):
    payload = {'Submit': 'Build', 'json': json.dumps({})}
    jobs = ["conda_ytdev"]
    for job in jobs:
        r = requests.post(_jenkins_hook(job), data=payload)
        if r.status_code != 200:
            logging.warn("Failed to submit {}".format(job))
