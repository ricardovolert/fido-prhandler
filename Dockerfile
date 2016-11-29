FROM debian:sid
MAINTAINER xarthisius.kk@gmail.com

ENV JENKINS_TOKEN=foo JENKINS_URL="https://tests.yt-project.org"

RUN apt-get update -qy && \
  apt-get install -qy python-hglib python-tornado python-requests \
    python-setuptools python-requests-oauthlib curl unzip && \
  cd /tmp && \
  curl -OL https://github.com/matiasb/python-unidiff/archive/master.zip && \
  unzip master.zip && \
  cd python-unidiff-master && \
  python2 setup.py install && \
  cd /tmp && \
  rm -rf *.zip python-unidiff-master && \
  apt-get remove -qy curl unzip && \
  apt-get clean && \
  rm -rf /var/lib/apt/lists/*

ADD main.py /srv/prhandler/main.py
ADD tasks.py /srv/prhandler/tasks.py

EXPOSE 8888
WORKDIR /srv/prhandler
CMD ["python2", "main.py"]
