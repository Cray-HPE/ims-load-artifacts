# Dockerfile for ims-load-artifacts container
# Copyright 2020-2021 Hewlett Packard Enterprise Development LP

FROM dtr.dev.cray.com/baseos/alpine:3.12.0 as base
COPY requirements.txt constraints.txt /
RUN apk add --no-cache py3-pip python3 && \
    pip3 install --upgrade pip \
        --no-cache-dir \
        --index-url https://arti.dev.cray.com:443/artifactory/api/pypi/pypi-remote/simple && \
    pip3 install --no-cache-dir -r requirements.txt

# The testing container
# Run unit tests
FROM base as testing
COPY requirements-test.txt constraints-test.txt /
RUN pip install --no-cache-dir -r /requirements-test.txt
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
RUN mkdir -p /ims_load_artifacts /results
COPY ims_load_artifacts /ims_load_artifacts

ENTRYPOINT ["/ims_load_artifacts/load_artifacts.py"]
