import git
import hglib
import logging
import os
import tempfile
import shutil
from tornado import gen
from tornado.ioloop import IOLoop
from tornado.web import RequestHandler, Application

LOCAL_GH_REPO_PATH = os.environ.get('LOCAL_GH_REPO_PATH', '/tmp/yt-git')
LOCAL_HG_REPO_PATH = os.environ.get('LOCAL_HG_REPO_PATH', '/tmp/yt-hg')
HG_REPO = os.environ.get('HG_REPO', 'https://bitbucket.org/yt_analysis/yt')
GH_REPO = os.environ.get(
    'GH_REPO', 'git+ssh://git@github.com:yt-project/yt-test.git')


@gen.coroutine
def sync_repos():
    configs = ['extensions.hggit=']
    try:
        repo = hglib.open(LOCAL_HG_REPO_PATH, configs=configs)
        repo.close()
    except hglib.error.ServerError:
        hglib.clone(source=HG_REPO, dest=LOCAL_HG_REPO_PATH)

    try:
        gh_repo = git.Repo(LOCAL_GH_REPO_PATH)
    except (git.exc.NoSuchPathError, git.exc.InvalidGitRepositoryError):
        gh_repo = git.Repo.init(LOCAL_GH_REPO_PATH, bare=True)
    finally:
        gh_repo.close()

    with hglib.open(LOCAL_HG_REPO_PATH, configs=configs) as repo:
        repo.pull(HG_REPO)
        repo.update('yt', check=True)
        head = repo.identify(id=True, rev='remote(tip, default)')
        head = head.decode().strip()
        repo.bookmark(b'master', rev=head, force=True)
        repo.push(LOCAL_GH_REPO_PATH, bookmark='master')

    tmpdir = tempfile.mkdtemp()
    with git.Repo.init(tmpdir, bare=False) as repo:
        origin = repo.create_remote('origin', LOCAL_GH_REPO_PATH)
        upstream = repo.create_remote('upstream', GH_REPO)
        origin.pull('master')
        upstream.push('master')
    shutil.rmtree(tmpdir)


class MainHandler(RequestHandler):

    @gen.coroutine
    def post(self):
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
