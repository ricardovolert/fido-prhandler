import git
import hglib
import logging
import os
from tornado import gen
from tornado.ioloop import IOLoop
from tornado.web import RequestHandler, Application

LOCAL_GIT_REPO_PATH = os.environ.get('LOCAL_GIT_REPO_PATH', '/tmp/yt-git')
LOCAL_HG_REPO_PATH = os.environ.get('LOCAL_HG_REPO_PATH', '/tmp/yt-hg')
HG_REPO = os.environ.get('HG_REPO', 'ssh://hg@bitbucket.org/yt_analysis/yt')
GH_REPO = os.environ.get('GH_REPO', 'git@github.com:yt-project/yt.git')


@gen.coroutine
def sync_repos():
    try:
        gh_repo = git.Repo(LOCAL_GIT_REPO_PATH)
    except (git.exc.NoSuchPathError, git.exc.InvalidGitRepositoryError):
        print('initializing %s' % LOCAL_GIT_REPO_PATH)
        gh_repo = git.Repo.init(LOCAL_GIT_REPO_PATH)
        gh_repo.create_remote('origin', GH_REPO)
    finally:
        gh_repo.close()

    configs = ['extensions.hggit=']
    try:
        repo = hglib.open(LOCAL_HG_REPO_PATH, configs=configs)
        repo.close()
    except hglib.error.ServerError:
        print('cloning %s to %s' % (HG_REPO, LOCAL_HG_REPO_PATH))
        hglib.clone(source=HG_REPO, dest=LOCAL_HG_REPO_PATH)
        # need to do this to ensure the correct hashes in the
        # converted git repo since two-way conversion is lossy see
        # e.g. https://groups.google.com/forum/#!topic/hg-git/1r1LBrqLeXc
        with hglib.open(LOCAL_HG_REPO_PATH, configs=configs) as repo:
            print('pushing %s to %s' % 
                  (LOCAL_HG_REPO_PATH, LOCAL_GIT_REPO_PATH))
            repo.push(LOCAL_GIT_REPO_PATH)

    with git.Repo(LOCAL_GIT_REPO_PATH) as repo:
        print('pull from %s on branch master' % GH_REPO)
        repo.remotes.origin.pull('master')

    with hglib.open(LOCAL_HG_REPO_PATH, configs=configs) as repo:
        print('pull from %s to %s on branch master' % 
              (LOCAL_GIT_REPO_PATH, LOCAL_HG_REPO_PATH))
        repo.pull(LOCAL_GIT_REPO_PATH)
        repo.update('master', check=True)
        print('push from %s to %s on bookmark master' %
              (LOCAL_HG_REPO_PATH, HG_REPO))
        repo.push(HG_REPO, bookmark='master')
    print('Done!')


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
