#
# MIT License
#
# (C) Copyright 2022 Hewlett Packard Enterprise Development LP
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

"""
Tests for IUF support
"""
import os
from textwrap import dedent
from unittest.mock import patch, mock_open

import pytest
import yaml

from ims_load_artifacts.iuf import (
    process_content_dir_manifest,
    process_content_dirs,
    process_enumerated_manifest,
    process_iuf_manifest,
)

iuf_manifest_image_name = 'shasta_barebones_image-1.2.4'
iuf_manifest_recipe_name = 'shasta_barebones_recipe-1.2.4'
iuf_content_dir = '/mnt/path/in/container'

squashfs_path = f'{iuf_manifest_image_name}.squashfs'
kernel_path = f'{iuf_manifest_image_name}.kernel'
initrd_path = f'{iuf_manifest_image_name}.initrd'
recipe_path = f'{iuf_manifest_recipe_name}.tgz'
ims_artifacts_dir = 'ims'

content_dir_image_name = f'content-dir-{iuf_manifest_image_name}'
content_dir_recipe_name = f'content-dir-{iuf_manifest_recipe_name}'
content_dir_path = 'ims-content'
md5sum = 'f3287b5d1267da964cf30fb5910d3126'


processed_iuf_images = {
    iuf_manifest_image_name: {
        'artifacts': [
            {
                'link': {
                    'path': os.path.join(iuf_content_dir, ims_artifacts_dir, squashfs_path),
                    'type': 'file'
                },
                'md5': md5sum,
                'type': 'application/vnd.cray.image.rootfs.squashfs'
            },
            {
                'link': {
                    'path': os.path.join(iuf_content_dir, ims_artifacts_dir, kernel_path),
                    'type': 'file'
                },
                'md5': md5sum,
                'type': 'application/vnd.cray.image.kernel'
            },
            {
                'link': {
                    'path': os.path.join(iuf_content_dir, ims_artifacts_dir, initrd_path),
                    'type': 'file'
                },
                'md5': md5sum,
                'type': 'application/vnd.cray.image.initrd'
            },
        ]
    }
}


@pytest.fixture
def content_dir_manifest():
    return dedent(f"""\
    ---
    version: "1.0.0"
    images:
      {content_dir_image_name}:
        artifacts:
          - link:
              path: /{squashfs_path}
              type: file
            md5: {md5sum}
            type: application/vnd.cray.image.rootfs.squashfs
          - link:
              path: /{kernel_path}
              type: file
            md5: {md5sum}
            type: application/vnd.cray.image.kernel
          - link:
              path: /{initrd_path}
              type: file
            md5: {md5sum}
            type: application/vnd.cray.image.initrd
    recipes:
      {content_dir_recipe_name}:
        link:
          path: /{recipe_path}
          type: file
        md5: {md5sum}
        linux_distribution: sles15
        recipe_type: kiwi-ng
    """)


@pytest.fixture
def content_dir_manifest_only_recipes():
    return dedent(f"""\
    ---
    version: "1.0.0"
    recipes:
      {content_dir_recipe_name}:
        link:
          path: /{recipe_path}
          type: file
        md5: {md5sum}
        linux_distribution: sles15
        recipe_type: kiwi-ng
    """)


@pytest.fixture
def enumerated_iuf_manifest():
    return dedent(f"""\
    ---
    name: shasta_barebones
    description: >
      A barebones IMS recipe and image.
    version: "1.0.0"
    content:
      ims:
        recipes:
        - name: {iuf_manifest_recipe_name}
          path: {recipe_path}
          linux_distribution: sles15
          recipe_type: kiwi-ng
          template_dictionary:
            product_version: "22.12"
          md5sum: {md5sum}
        images:
        - name: {iuf_manifest_image_name}
          path: {ims_artifacts_dir}
          rootfs:
            path: {squashfs_path}
            md5sum: {md5sum}
          kernel:
            path: {kernel_path}
            md5sum: {md5sum}
          initrd:
            md5sum: {md5sum}
            path: {initrd_path}
    """)


@pytest.fixture
def mixed_iuf_manifest():
    return dedent(f"""\
    ---
    name: shasta_barebones
    description: >
      A barebones IMS recipe and image
    version: 1.0.0
    content:
      ims:
        content_dirs:
        - {content_dir_path}
        images:
        - name: {iuf_manifest_image_name}
          path: {ims_artifacts_dir}
          rootfs:
            path: {squashfs_path}
            md5sum: {md5sum}
          kernel:
            path: {kernel_path}
            md5sum: {md5sum}
          initrd:
            md5sum: {md5sum}
            path: {initrd_path}
    """)


def test_process_content_dir_manifest(content_dir_manifest):
    """Test that artifact paths are correctly re-written"""
    manifest_parsed = yaml.safe_load(content_dir_manifest)
    new_manifest = process_content_dir_manifest(manifest_parsed, iuf_content_dir)

    assert new_manifest['recipes'][content_dir_recipe_name]['link']['path'] == os.path.join(iuf_content_dir, recipe_path)
    for idx, expected_path in enumerate([os.path.join(iuf_content_dir, path) for path in [squashfs_path, kernel_path, initrd_path]]):
        assert new_manifest['images'][content_dir_image_name]['artifacts'][idx]['link']['path'] == expected_path


def test_process_content_dirs(content_dir_manifest):
    """Test that content dirs are opened and processed properly"""
    with patch('builtins.open', mock_open(read_data=content_dir_manifest)):
        manifest = process_content_dirs([iuf_content_dir], iuf_content_dir)
    assert process_content_dir_manifest(yaml.safe_load(content_dir_manifest), iuf_content_dir) == manifest


def test_mixed_manifest(content_dir_manifest_only_recipes, mixed_iuf_manifest):
    """Test a manifest with content dirs and enumerated artifacts"""
    with patch('builtins.open', mock_open(read_data=content_dir_manifest_only_recipes)):
        manifest = yaml.safe_load(mixed_iuf_manifest)
        processed_manifest = process_iuf_manifest(manifest, iuf_content_dir)
        expected_manifest = {
            'version': '1.0.0',
            'recipes': {
                content_dir_recipe_name: {  # The recipes are in the content dir, not the IUF manifest
                    'link': {
                        'type': 'file',
                        'path': os.path.join(iuf_content_dir, content_dir_path, recipe_path),
                    },
                    'linux_distribution': 'sles15',
                    'recipe_type': 'kiwi-ng',
                    'md5': md5sum
                }
            },
            'images': processed_iuf_images
        }
        assert processed_manifest == expected_manifest


def test_processing_enumerated_iuf_manifest(enumerated_iuf_manifest):
    manifest = yaml.safe_load(enumerated_iuf_manifest)
    recipes = manifest['content']['ims']['recipes']
    images = manifest['content']['ims']['images']
    assert process_enumerated_manifest(recipes, images, iuf_content_dir) == {
        'version': '1.0.0',
        'recipes': {
            iuf_manifest_recipe_name: {
                'link': {
                    'type': 'file',
                    'path': os.path.join(iuf_content_dir, recipe_path)
                },
                'linux_distribution': 'sles15',
                'recipe_type': 'kiwi-ng',
                'template_dictionary': {'product_version': '22.12'},
                'md5': md5sum
            }
        },
        'images': processed_iuf_images
    }
