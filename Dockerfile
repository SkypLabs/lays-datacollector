#FROM docker.io/resin/rpi-raspbian:jessie
FROM docker.io/debian:jessie
MAINTAINER skyper@skyplabs.net

ENV LAYS_DEBUG=false

RUN apt-get update \
	&& apt-get install -y python3 python3-pip \
	&& mkdir -p /usr/src/app

COPY requirements.txt /tmp/

RUN pip3 install -r /tmp/requirements.txt \
	&& rm -f /tmp/requirements.txt

COPY data-collector.py /usr/src/app/

WORKDIR /usr/src/app
CMD ["python3", "-u", "data-collector.py"]
