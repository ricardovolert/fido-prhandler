import logging

def pullrequest_created(data):
    dest = data["destination"]
    logging.debug("destination: hash=%s branch=%s repo=%s" %
                  (dest["commit"]["hash"], dest["branch"]["name"],
                   dest["repository"]["full_name"]))

    source = data["source"]
    logging.debug("source: hash=%s branch=%s repo=%s" %
                  (source["commit"]["hash"], source["branch"]["name"],
                   source["repository"]["full_name"]))


def pullrequest_updated(data):
    # this is gonna be fun: figure out whether code changed or not...
    pass


def pullrequest_fullfilled(data):
    pass
