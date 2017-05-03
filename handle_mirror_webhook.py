import git
import hashlib
import hglib
import hmac
import json
import logging
import os
import requests
from ipaddress import ip_address, ip_network
from tornado import gen
from tornado.ioloop import IOLoop
from tornado.web import RequestHandler, Application, HTTPError

LOCAL_GIT_REPO_PATH = os.environ.get('LOCAL_GIT_REPO_PATH', '/tmp/yt-git')
LOCAL_HG_REPO_PATH = os.environ.get('LOCAL_HG_REPO_PATH', '/tmp/yt-hg')
HG_REPO = os.environ.get('HG_REPO', 'ssh://hg@bitbucket.org/yt_analysis/yt')
GH_REPO = os.environ.get('GH_REPO', 'git@github.com:yt-project/yt.git')
GH_SECRET = os.environ.get('GH_SECRET', 'bla')


@gen.coroutine
def sync_repos():
    try:
        gh_repo = git.Repo(LOCAL_GIT_REPO_PATH)
    except (git.exc.NoSuchPathError, git.exc.InvalidGitRepositoryError):
        logging.info('initializing %s' % LOCAL_GIT_REPO_PATH)
        gh_repo = git.Repo.init(LOCAL_GIT_REPO_PATH)
        gh_repo.create_remote('origin', GH_REPO)
    finally:
        gh_repo.close()

    configs = ['extensions.hggit=']
    try:
        repo = hglib.open(LOCAL_HG_REPO_PATH, configs=configs)
        repo.close()
    except hglib.error.ServerError:
        logging.info('cloning %s to %s' % (HG_REPO, LOCAL_HG_REPO_PATH))
        hglib.clone(source=HG_REPO, dest=LOCAL_HG_REPO_PATH)
        # need to do this to ensure the correct hashes in the
        # converted git repo since two-way conversion is lossy see
        # e.g. https://groups.google.com/forum/#!topic/hg-git/1r1LBrqLeXc
        with hglib.open(LOCAL_HG_REPO_PATH, configs=configs) as repo:
            logging.info('pushing %s to %s' %
                         (LOCAL_HG_REPO_PATH, LOCAL_GIT_REPO_PATH))
            repo.push(LOCAL_GIT_REPO_PATH)

    with git.Repo(LOCAL_GIT_REPO_PATH) as repo:
        logging.info('pull from %s on branch master' % GH_REPO)
        repo.remotes.origin.pull('master')

    with hglib.open(LOCAL_HG_REPO_PATH, configs=configs) as repo:
        logging.info('pull from %s to %s on branch master' %
                     (LOCAL_GIT_REPO_PATH, LOCAL_HG_REPO_PATH))
        repo.pull(LOCAL_GIT_REPO_PATH)
        repo.update('master', check=True)
        logging.info('push from %s to %s on bookmark master' %
                     (LOCAL_HG_REPO_PATH, HG_REPO))
        repo.push(HG_REPO, bookmark='master')
    logging.info('Done!')


class MainHandler(RequestHandler):

    @gen.coroutine
    def _verify_ip(self):
        remote_ip = self.request.headers.get(
            "X-Real-IP", self.request.remote_ip)
        src_ip = ip_address(u'{}'.format(remote_ip))
        whitelist = requests.get('https://api.github.com/meta').json()['hooks']
        for valid_ip in whitelist:
            if src_ip in ip_network(valid_ip):
                break
        else:
            raise HTTPError(403, 'Remote address not whitelisted')

    @gen.coroutine
    def _verify_signature(self):
        header_signature = self.request.headers.get('X-Hub-Signature')
        if not header_signature:
            raise HTTPError(403, 'Request is missing "X-Hub-Signature"')
        try:
            sha_name, signature = header_signature.split('=')
        except:
            raise HTTPError(403, '"X-Hub-Signature" is malformed')
        if sha_name != 'sha1':
            raise HTTPError(501, 'Only SHA1 is supported')

        # HMAC requires the key to be bytes, but data is string
        mac = hmac.new(str(GH_SECRET), msg=self.request.body.decode('utf8'),
                       digestmod=hashlib.sha1)
        if not hmac.compare_digest(str(mac.hexdigest()), str(signature)):
            raise HTTPError(403, 'Wrong signature')

    @gen.coroutine
    def post(self):
        yield [
            self._verify_ip(),
            self._verify_signature()
        ]

        # Implement ping
        event = self.request.headers.get('X-GitHub-Event', 'ping')
        if event == 'ping':
            self.write(json.dumps({'msg': 'pong'}))
        elif event in ['push']:
            IOLoop.current().spawn_callback(sync_repos)
            self.set_status(202)
        self.finish()


if __name__ == "__main__":
    logging.getLogger().setLevel(logging.INFO)
    handlers = [
        (r"/", MainHandler),
    ]

    app = Application(handlers)
    app.listen(5000)
    IOLoop.current().start()
