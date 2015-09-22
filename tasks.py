import logging


def handle_approve(data):
    pass


def handle_unapprove(data):
    pass


def handle_comment_created(data):
    pass


def handle_comment_deleted(data):
    pass


def handle_comment_updated(data):
    pass


def handle_created(data):
    dest = data["destination"]
    logging.debug("destination: hash=%s branch=%s repo=%s" %
                  (dest["commit"]["hash"], dest["branch"]["name"],
                   dest["repository"]["full_name"]))

    source = data["source"]
    logging.debug("source: hash=%s branch=%s repo=%s" %
                  (source["commit"]["hash"], source["branch"]["name"],
                   source["repository"]["full_name"]))


def handle_updated(data):
    # this is gonna be fun: figure out whether code changed or not...
    pass


def handle_declined(data):
    pass


def handle_merged(data):
    pass
