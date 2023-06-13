#!/usr/bin/env python3
#
# MIT License
#
# (C) Copyright 2019-2022 Hewlett Packard Enterprise Development LP
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
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#

"""
Cray IMS Load Artifacts Container
This loads and registers recipes and pre-built image artifacts with IMS.
"""

import logging
import os
import sys
import tempfile
import time
from functools import partial

import jinja2
import requests
import urllib3
import yaml

import ims_load_artifacts.loaders
from ims_load_artifacts.iuf import iuf_load_artifacts
from ims_load_artifacts.loaders import IMS_URL, ImsLoadArtifactsBaseException, ImsLoadArtifacts_v1_0_0

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

MANIFEST_FILE = os.environ.get("MANIFEST_FILE", "/manifest.yaml")
TEMPLATE_DICTIONARY = os.environ.get("TEMPLATE_DICTIONARY", "/mnt/image-recipe-import/template_dictionary")

LOGGER = logging.getLogger(__name__)


def wait_for_istio():
    """
    Loop until we are successfully able to call the IMS ready endpoint.
    """
    LOGGER.debug("Waiting for Istio...")
    ims_ready_endpoint = "/".join([IMS_URL, "healthz/ready"])
    while True:
        try:
            LOGGER.debug("Calling ims ready endpoint")
            r = requests.get(ims_ready_endpoint, timeout=10)
            if r.ok:
                LOGGER.info("Successfully talked to IMS Ready endpoint.")
                break
            LOGGER.warning("Could not talk to IMS Ready endpoint. Request returned http status %s", r.status_code)
        except requests.RequestException as exc:
            LOGGER.warning(exc)
        LOGGER.info("Trying again in 2 seconds")
        time.sleep(2)


def load_template(name):
    """
    Prevent malicious attackers from importing sensitive files in the container by
    only allow jinja2 to read MANIFEST_FILE.
    """
    if name == MANIFEST_FILE:
        with open(MANIFEST_FILE, encoding="utf-8") as inf:
            return inf.read()
    return None


def load_artifacts():
    """
    Read a manifest.yaml file. If the object was not found, log it and return an error..
    """

    manifest_file = MANIFEST_FILE
    try:
        if os.path.isfile(TEMPLATE_DICTIONARY):
            LOGGER.info("Templating manifest.yaml")
            template_loader = jinja2.FunctionLoader(load_template)
            template_env = jinja2.Environment(loader=template_loader)
            template = template_env.get_template(MANIFEST_FILE)
            with open(TEMPLATE_DICTIONARY, encoding="utf-8") as td, \
                    tempfile.NamedTemporaryFile("w", delete=False) as outf:
                outf.write(template.render(**yaml.safe_load(td)))
                manifest_file = outf.name
                outf.close()

        with open(manifest_file, 'rt', encoding='utf-8') as inf:
            manifest_data = yaml.safe_load(inf)

        try:
            return {
                "1.0.0": ImsLoadArtifacts_v1_0_0(),
                "1.1.0": ImsLoadArtifacts_v1_0_0()
            }[manifest_data["version"]](manifest_data)
        except KeyError:
            raise ImsLoadArtifactsBaseException(
                f"Cannot process manifest.yaml due to unsupported or missing manifest version {manifest_data}") \
                from ValueError

    except yaml.YAMLError as exc:
        raise ImsLoadArtifactsBaseException("Cannot loading manifest.yaml.", exc=exc) from yaml.YAMLError


def main() -> int:
    """
    Load artifacts from manifest.yaml into S3 and register with IMS.
    """

    is_in_iuf = bool(os.getenv('IUF'))
    log_level = os.environ.get('LOG_LEVEL', 'WARN')
    logging_params = {
        'level': log_level
    }
    if is_in_iuf:
        logging_params['format'] = '%(levelname)s %(message)s'
    logging.basicConfig(**logging_params)

    try:
        # The key names used below match the values defined in the
        #  *-s3-credentials secrets available on shasta systems.
        # ncn-w001:~ # kubectl  get secrets -o yaml ims-s3-credentials
        # data:
        #   access_key: R0k0WEdKVzJPSDlZQkVaOVkwNjk=
        #   s3_endpoint: aHR0cDovL3Jndy5sb2NhbDo4MDgw
        #   secret_key: NDdHZUdPanhPNlhRc2RMUWxyb1k3WXhvMWNqb2NLMmoxQnBRb0o4NQ==
        #   ssl_validate: ZmFsc2U=
        ims_load_artifacts.loaders.S3_ENDPOINT = os.environ['S3_ENDPOINT']
        ims_load_artifacts.loaders.S3_SECRET_KEY = os.environ['SECRET_KEY']
        ims_load_artifacts.loaders.S3_ACCESS_KEY = os.environ['ACCESS_KEY']
        ims_load_artifacts.loaders.S3_SSL_VERIFY = os.environ['SSL_VALIDATE']
    except KeyError as key_error:
        LOGGER.error("Missing environment variable %s.", key_error)
        sys.exit(1)

    try:
        if is_in_iuf:
            iuf_distribution_root = os.getenv('IUF_RELEASE_PATH', os.getcwd())
            iuf_manifest_path = os.getenv('IUF_MANIFEST_PATH',
                                          os.path.join(iuf_distribution_root, 'iuf-product-manifest.yaml'))
            load_artifacts_fn = partial(iuf_load_artifacts, iuf_distribution_root, iuf_manifest_path)
        else:
            load_artifacts_fn = load_artifacts
            wait_for_istio()
        return int(not load_artifacts_fn())
    except FileNotFoundError as exc:
        LOGGER.error("Missing manifest file.", exc_info=exc)
    except ImsLoadArtifactsBaseException as exc:
        LOGGER.error(exc)

    return 1


if __name__ == '__main__':
    sys.exit(main())
