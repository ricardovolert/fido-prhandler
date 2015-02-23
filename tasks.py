import logging


def handle_approve():
    pass


def handle_unapprove():
    pass


def handle_comment_created():
    pass


def handle_comment_deleted():
    pass


def handle_comment_updated():
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


def handle_updated():
    pass


def handle_declined():
    pass


def handle_merged():
    pass
