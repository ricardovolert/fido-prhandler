import git
import hglib
import logging
import os
from tornado import gen
from tornado.ioloop import IOLoop
from tornado.web import RequestHandler, Application

LOCAL_GIT_REPO_PATH = os.environ.get('LOCAL_GIT_REPO_PATH', '/tmp/yt-git')
LOCAL_HG_REPO_PATH = os.environ.get('LOCAL_HG_REPO_PATH', '/tmp/yt-hg')
HG_REPO = os.environ.get('HG_REPO', 'https://bitbucket.org/yt_analysis/yt')
GH_REPO = os.environ.get(
    'GH_REPO', 'git+ssh://git@github.com/yt-project/yt.git')
GIT_BRANCH_MAP = {
    'yt': 'master',
    'stable': 'stable',
    'yt-2.x': 'yt-2.x',
}


def get_revision_from_remote_repo(repo, name):
    head = repo.identify(id=True, rev='remote(%s, default)' % name)
    return head.decode().strip()


@gen.coroutine
def sync_repos():
    configs = ['extensions.hggit=']
    try:
        repo = hglib.open(LOCAL_HG_REPO_PATH, configs=configs)
        repo.close()
    except hglib.error.ServerError:
        print('cloning %s to %s' % (HG_REPO, LOCAL_HG_REPO_PATH))
        hglib.clone(source=HG_REPO, dest=LOCAL_HG_REPO_PATH)

    try:
        gh_repo = git.Repo(LOCAL_GIT_REPO_PATH)
    except (git.exc.NoSuchPathError, git.exc.InvalidGitRepositoryError):
        print('initializing %s' % LOCAL_GIT_REPO_PATH)
        gh_repo = git.Repo.init(LOCAL_GIT_REPO_PATH, bare=True)
        gh_repo.create_remote('origin', GH_REPO)
    finally:
        gh_repo.close()

    with hglib.open(LOCAL_HG_REPO_PATH, configs=configs) as repo:
        repo.pull(HG_REPO)
        for hg_branch in ['yt', 'stable', 'yt-2.x']:
            rev = get_revision_from_remote_repo(repo, hg_branch)
            print('updating to %s on branch %s' % (rev, hg_branch))
            repo.update(rev, check=True)
            git_branch = GIT_BRANCH_MAP[hg_branch]
            print('setting bookmark %s on branch %s' % (git_branch, hg_branch))
            repo.bookmark(git_branch, force=True)
            print('pushing to %s on branch %s' % (
                LOCAL_GIT_REPO_PATH, git_branch))
            repo.push(LOCAL_GIT_REPO_PATH, bookmark=git_branch)

    with git.Repo(LOCAL_GIT_REPO_PATH) as repo:
        print('pushing to %s from %s' % (GH_REPO, LOCAL_GIT_REPO_PATH))
        repo.remotes.origin.push(all=True)
        repo.remotes.origin.push(tags=True)


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
