# Dockerfile for ims-load-artifacts container
# Copyright 2020-2021 Hewlett Packard Enterprise Development LP
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#
# (MIT License)

FROM artifactory.algol60.net/docker.io/alpine:3.13 as base
COPY requirements.txt constraints.txt /
RUN apk add --upgrade --no-cache apk-tools &&  \
	apk update && \
	apk add --no-cache \
        gcc \
        python3-dev \
        libc-dev \
        py3-pip \
        python3 && \
	apk -U upgrade --no-cache && \
    pip3 install --upgrade pip \
        --no-cache-dir \
        --index-url https://arti.dev.cray.com:443/artifactory/api/pypi/pypi-remote/simple && \
    pip3 install --no-cache-dir -r requirements.txt

# The testing container
# Run unit tests
FROM base as testing
COPY requirements-test.txt constraints-test.txt /
RUN pip3 install --no-cache-dir -r /requirements-test.txt
RUN mkdir /ims_load_artifacts && mkdir /tests
COPY ims_load_artifacts /ims_load_artifacts
COPY tests /tests
RUN echo -e $(ls -l /tests/*)
RUN python3 -m unittest -v

# Run code style checkers
FROM testing as codestyle
COPY .pylintrc .pycodestyle /
ARG FORCE_STYLE_CHECKS=null
RUN pycodestyle --config=/.pycodestyle /ims_load_artifacts
RUN pylint ./ims_load_artifacts

# The final application release product container
FROM base as application

RUN mkdir -p /ims_load_artifacts /results && \
  chown -R "nobody:nobody" /ims_load_artifacts /results

USER nobody
COPY ims_load_artifacts /ims_load_artifacts
ENTRYPOINT ["/ims_load_artifacts/load_artifacts.py"]
