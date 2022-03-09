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
Unit tests for ims_load_artifacts
"""

import os
import unittest

import fixtures
import mock
import responses
import sys
import testtools

# Add load_artifacts to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')))

from ims_load_artifacts import load_artifacts

manifest_yaml = """
---
version: "1.0.0"
images:
  shasta_barebones_image-1.2.4:
    artifacts:
      - link:
          path: http://localhost:8081/repository/shasta-boot-artifacts/cray-sles15sp1-barebones-1.2.4.sqshfs
          type: http
        md5: f3287b5d1267da964cf30fb5910d3126
        type: application/vnd.cray.image.rootfs.squashfs
      - link:
          path: http://localhost:8081/repository/shasta-boot-artifacts/kernel-1.2.4
          type: http
        md5: f3287b5d1267da964cf30fb5910d3126
        type: application/vnd.cray.image.kernel
      - link:
          path: http://localhost:8081/repository/shasta-boot-artifacts/initrd-1.2.4
          type: http
        md5: f3287b5d1267da964cf30fb5910d3126
        type: application/vnd.cray.image.initrd
recipes:
  shasta_barebones_recipe-1.2.4:
    link:
      path: http://localhost:8081/repository/shasta-image-recipes/cray-sles15sp1-barebones-1.2.4.tgz
      type: http
    md5: f3287b5d1267da964cf30fb5910d3126
    linux_distribution: sles15
    recipe_type: kiwi-ng
"""


class TestLoadArtifacts(testtools.TestCase):

    @responses.activate
    @mock.patch(".".join([load_artifacts.__name__, "yaml.dump"]))
    @mock.patch(".".join([load_artifacts.__name__, "open"]), new_callable=mock.mock_open, read_data=manifest_yaml)
    def test_init(self, mock_open, mock_yaml_dump):

        S3_ACCESS_KEY = self.getUniqueString()
        S3_SECRET_KEY = self.getUniqueString()
        S3_SSL_VALIDATE = self.getUniqueString()
        S3_ENDPOINT = self.getUniqueString()
        S3_BUCKET = self.getUniqueString()

        # IMS Ready Check
        responses.add(responses.GET, 'http://cray-ims/healthz/ready',
                      status=200,
                      content_type='application/octet-stream',
                      adding_headers={'Transfer-Encoding': 'chunked'})

        # IMS Recipe Data
        for url in ['http://localhost:8081/repository/shasta-image-recipes/cray-sles15sp1-barebones-1.2.4.tgz']:
            responses.add(responses.GET, url,
                          body='test', status=200,
                          content_type='application/octet-stream',
                          adding_headers={'Transfer-Encoding': 'chunked'})

        # IMS Image Data
        for url in ['http://localhost:8081/repository/shasta-boot-artifacts/cray-sles15sp1-barebones-1.2.4.sqshfs',
                    'http://localhost:8081/repository/shasta-boot-artifacts/kernel-1.2.4',
                    'http://localhost:8081/repository/shasta-boot-artifacts/initrd-1.2.4']:
            responses.add(responses.GET, url,
                          body='test', status=200,
                          content_type='application/octet-stream',
                          adding_headers={'Transfer-Encoding': 'chunked'})

        self.useFixture(fixtures.EnvironmentVariable(
            'ACCESS_KEY', S3_ACCESS_KEY))
        self.useFixture(fixtures.EnvironmentVariable(
            'SECRET_KEY', S3_SECRET_KEY))
        self.useFixture(fixtures.EnvironmentVariable(
            'S3_ENDPOINT', S3_ENDPOINT))
        self.useFixture(fixtures.EnvironmentVariable(
            'SSL_VALIDATE', S3_SSL_VALIDATE))
        self.useFixture(fixtures.EnvironmentVariable(
            'S3_BUCKET', S3_BUCKET))

        ih_mock = self.useFixture(fixtures.MockPatchObject(
            load_artifacts, 'ImsHelper', autospec=True)).mock

        ih_mock._md5.return_value = "f3287b5d1267da964cf30fb5910d3126"

        # Call load_artifacts
        ret_value = load_artifacts.main()

        self.assertEqual(ret_value, 0)

        # there are two instantiations of ims-python-helper, first for recipes, second for images
        self.assertEqual(ih_mock.call_count, 2)

        # There should be 6 total method calls, based on the test manifest above
        self.assertEqual(len(ih_mock.method_calls), 6)

        # method call 1, to validate the md5 of the barebones recipe tgz archive
        self.assertEqual(ih_mock.method_calls[0][0], "_md5")
        self.assertEqual(len(ih_mock.method_calls[0][1]), 1)
        self.assertEqual(ih_mock.method_calls[0][1][0], "/tmp/cray-sles15sp1-barebones-1.2.4.tgz")

        # method call 2, to upload the recipe to S3 and IMS
        self.assertEqual(ih_mock.method_calls[1][0], "().recipe_upload")
        self.assertEqual(len(ih_mock.method_calls[1][1]), 3)
        self.assertEqual(ih_mock.method_calls[1][1][0], "shasta_barebones_recipe-1.2.4")
        self.assertEqual(ih_mock.method_calls[1][1][1], "/tmp/cray-sles15sp1-barebones-1.2.4.tgz")
        self.assertEqual(ih_mock.method_calls[1][1][2], "sles15")

        # method call 3, to validate the md5 of the cray-sles15sp1-barebones-1.2.4.sqshfs
        self.assertEqual(ih_mock.method_calls[2][0], "_md5")
        self.assertEqual(len(ih_mock.method_calls[2][1]), 1)
        self.assertEqual(ih_mock.method_calls[2][1][0], "/tmp/cray-sles15sp1-barebones-1.2.4.sqshfs")

        # method call 4, to validate the md5 of the kernel-1.2.4
        self.assertEqual(ih_mock.method_calls[3][0], "_md5")
        self.assertEqual(len(ih_mock.method_calls[3][1]), 1)
        self.assertEqual(ih_mock.method_calls[3][1][0], "/tmp/kernel-1.2.4")

        # method call 5, to validate the md5 of the initrd-1.2.4
        self.assertEqual(ih_mock.method_calls[4][0], "_md5")
        self.assertEqual(len(ih_mock.method_calls[4][1]), 1)
        self.assertEqual(ih_mock.method_calls[4][1][0], "/tmp/initrd-1.2.4")

        # method call 6, to upload the image artifacts to S3 and IMS
        self.assertEqual(ih_mock.method_calls[5][0], "().image_upload_artifacts")
        self.assertEqual(len(ih_mock.method_calls[5][2]), 5)
        self.assertEqual(ih_mock.method_calls[5][2]["image_name"], 'shasta_barebones_image-1.2.4')
        self.assertEqual(ih_mock.method_calls[5][2]["rootfs"], ['/tmp/cray-sles15sp1-barebones-1.2.4.sqshfs'])
        self.assertEqual(ih_mock.method_calls[5][2]["kernel"], ['/tmp/kernel-1.2.4'])
        self.assertEqual(ih_mock.method_calls[5][2]["initrd"], ['/tmp/initrd-1.2.4'])
        self.assertEqual(ih_mock.method_calls[5][2]["boot_parameters"], None)


if __name__ == "__main__":
    unittest.main()
