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
Support for loading artifacts in IMS through the IUF
"""
from copy import deepcopy
import logging
import os
from typing import Any, Iterable, Optional

import yaml

from ims_load_artifacts.loaders import ImsLoadArtifacts_v1_0_0


LOGGER = logging.getLogger(__name__)


def get_val_by_path(dict_val: dict, dotted_path: str, default_value: Optional = None) -> Any:
    """Get a value from a dictionary based on a dotted path.

    For example, if `dict_val` is as follows:

    dict_val = {
        'foo': {
            'bar': 'baz'
        }
    }

    Then get_val_by_path(dict_val, 'foo.bar') would return 'baz', and something
    like get_val_by_path(dict_val, 'no.such.keys') would return None.

    Args:
        dict_val: The dictionary in which to search for the dotted path.
        dotted_path: The dotted path to look for in the dictionary. The
            dot character, '.', separates the keys to use when traversing a
            nested dictionary.
        default_value: The default value to return when the given dotted path
            does not exist in the dict_val.

    Returns:
        The value that exists at the dotted path or `default_value` if no such
        path exists in `dict_val`.
    """
    current_val = dict_val
    for key in dotted_path.split('.'):
        if current_val and key in current_val:
            current_val = current_val[key]
        else:
            return default_value
    return current_val


def process_iuf_manifest(iuf_manifest: dict, distribution_root: str) -> dict:
    """Transform IUF manifest content to manifest.yaml schema expected by ImsLoadArtifacts.

    Args:
        iuf_manifest: parsed content from the IUF product manifest
        distribution_root: the path to the IUF product release distribution
            mounted inside the container

    Returns:
        a dict with the same schema as a manifest.yaml file in a "legacy"
        ims-load-artifacts Docker image. See README.md for details.
    """
    content_dir_manifests = {}
    content_dirs = get_val_by_path(iuf_manifest, 'content.ims.content_dirs')
    if content_dirs:
        content_dir_manifests = process_content_dirs(content_dirs, distribution_root)

    recipes = get_val_by_path(iuf_manifest, 'content.ims.recipes', [])
    images = get_val_by_path(iuf_manifest, 'content.ims.images', [])
    return merge_manifests(content_dir_manifests, process_enumerated_manifest(recipes, images, distribution_root))


def process_enumerated_manifest(
        recipes: Iterable[dict],
        images: Iterable[dict],
        distribution_root: str
) -> dict:
    """Transform an IUF manifest with enumerated images and recipes into a load-ims-artifacts manifest.

    Args:
        recipes: a list of recipes defined in the IUF product manifest
        images: a list of images defined in the IUF product manifest
        distribution_root: the path to the IUF product release distribution
            mounted inside the container

    Returns:
        a dict with the same schema as a manifest.yaml file in a "legacy"
        ims-load-artifacts Docker image. See README.md for details.
    """
    processed_manifest = {
        'version': '1.0.0',  # Create a manifest compatible with the _ImsLoadArtifacts_v1_0_0 helper
    }
    processed_recipes = {}
    for recipe in recipes:
        recipe_path = recipe['path']
        recipe_name = recipe.get('name')
        if not recipe_name:
            recipe_basename = os.path.basename(recipe_path)
            if recipe_basename.endswith('.tar.gz'):
                recipe_name = recipe_basename.removesuffix('.tar.gz')
            else:
                recipe_name, _ = os.path.splitext(recipe_basename)

        built_recipe = {
            key: recipe.get(key) for key in ['linux_distribution', 'recipe_type', 'template_dictionary']
            if recipe.get(key) is not None
        }
        built_recipe.update({
            'link': {
                'type': 'file',
                'path': os.path.join(distribution_root, recipe['path'])
            },
            'md5': recipe.get('md5sum', ''),
        })
        if recipe_name in processed_recipes:
            LOGGER.warning('Recipe "%s" is duplicated in the IUF product manifest; '
                           'only the last instance in the IUF product manifest will be imported.', recipe_name)
        processed_recipes[recipe_name] = built_recipe
    processed_manifest['recipes'] = processed_recipes

    artifact_key_to_type = {
        'rootfs': 'application/vnd.cray.image.rootfs.squashfs',
        'kernel': 'application/vnd.cray.image.kernel',
        'initrd': 'application/vnd.cray.image.initrd',
    }

    processed_images = {}
    for image in images:
        artifact_records = []
        for artifact_key, artifact_type in artifact_key_to_type.items():
            if artifact_key in image:
                artifact = image[artifact_key]
                artifact_records.append({
                    'link': {
                        'path': os.path.join(distribution_root, image['path'], artifact['path']),
                        'type': 'file'
                    },
                    'type': artifact_type,
                    'md5': artifact.get('md5sum', ''),
                })

        if artifact_records:
            image_name = image.get('name', os.path.basename(image['path']))
            if image_name in processed_images:
                LOGGER.warning('Image "%s" is duplicated in the IUF product manifest;'
                               'only the last instance in the IUF product manifest will be imported.', image_name)
            processed_images[image_name] = {
                'artifacts': artifact_records
            }
    processed_manifest['images'] = processed_images

    return processed_manifest


def process_content_dirs(content_dir_paths: Iterable[str], distribution_root: str) -> dict:
    """Process the content_dirs provided in the IUF manifest into a single load-ims-artifacts manifest

    Args:
        content_dir_paths: paths to content directories enumerated in the IUF manifest.
            Each content directory contains some IMS artifacts and a "legacy"
            manifest.yaml file described in README.md.
        distribution_root: the path to the IUF product release distribution
            mounted inside the container

    Returns:
        a dict with the same schema as a manifest.yaml file in a "legacy"
        ims-load-artifacts Docker image which combines the content from
        all the enumerated content directories' manifest.yaml files.
        See README.md for details.
    """
    content_dir_manifests = []
    for content_dir_path in content_dir_paths:
        full_content_dir_path = os.path.join(distribution_root, content_dir_path)
        content_dir_manifest_path = os.path.join(full_content_dir_path, 'manifest.yaml')
        try:
            with open(content_dir_manifest_path, encoding='utf-8') as content_dir_manifest:
                current_manifest = yaml.safe_load(content_dir_manifest)
                content_dir_manifests.append(
                    process_content_dir_manifest(
                        current_manifest,
                        full_content_dir_path
                    )
                )

        except OSError as err:
            LOGGER.warning('Could not open IMS content manifest %s; skipping', err)
        except yaml.YAMLError as err:
            LOGGER.warning('Could not parse manifest YAML from content directory %s: %s',
                           content_dir_path, err)

    return merge_manifests(*content_dir_manifests)


def process_content_dir_manifest(content_dir_manifest: dict, content_dir_path: str) -> dict:
    """Change artifact paths in content directories so their paths are correct

    This is needed since the manifest.yaml files from ims-load-artifacts images
    usually point to artifacts directly in the filesystem root. This function
    rewrites the file paths such that the filesystem root is interpreted as the
    content directory path, i.e. the root directory if the process chrooted
    into the content directory.

    Args:
        content_dir_manifest: a parsed manifest.yaml from a content directory
        content_dir_path: the path to the content directory containing the file
            which contains the raw content_dir_manifest content.
    """
    def fix_path(old_path):
        return os.path.join(content_dir_path, old_path.strip(os.path.sep))

    new_manifest = deepcopy(content_dir_manifest)
    for recipe_name in new_manifest.get('recipes', {}).keys():
        old_path = new_manifest['recipes'][recipe_name]['link']['path']
        new_manifest['recipes'][recipe_name]['link']['path'] = fix_path(old_path)

    for image_name in new_manifest.get('images', {}).keys():
        for image_artifact in new_manifest['images'][image_name]['artifacts']:
            old_path = image_artifact['link']['path']
            image_artifact['link']['path'] = fix_path(old_path)

    return new_manifest


def merge_manifests(*manifests: dict) -> dict:
    """Merge multiple load-ims-artifacts manifests into one single manifest.

    Note that this function does not support merging content directory manifests
    which have duplicate image or recipe names. Image and recipe manifest contents
    will be overwritten arbitrarily and a warning will be logged.

    Args:
        manifests: individual manifests constructed from parsed manifest.yaml
            files from each content directory and from the IUF product manifest.

    Returns:
        the content directory manifests merged into a single manifest.
    """
    merged_manifest = {
        'version': '1.0.0',
    }

    merged_recipes = {}
    merged_images = {}
    for manifest in manifests:
        for recipe_name, recipe_contents in manifest.get('recipes', {}).items():
            if recipe_name in merged_recipes:
                LOGGER.warning('Duplicate recipe %s detected', recipe_name)
            merged_recipes[recipe_name] = recipe_contents
        for image_name, image_contents in manifest.get('images', {}).items():
            if image_name in merged_images:
                LOGGER.warning('Duplicate image %s detected', image_name)
            merged_images[image_name] = image_contents

    if merged_recipes:
        merged_manifest['recipes'] = merged_recipes

    if merged_images:
        merged_manifest['images'] = merged_images

    return merged_manifest


def iuf_load_artifacts(iuf_distribution_root: str, iuf_manifest_path: str) -> bool:
    """Main entrypoint for IUF artifact loader."""
    with open(iuf_manifest_path, encoding='utf-8') as iuf_manifest:
        try:
            manifest_input_data = process_iuf_manifest(
                yaml.safe_load(iuf_manifest),
                iuf_distribution_root
            )
        except yaml.YAMLError as err:
            LOGGER.error("Could not load IUF product manifest: %s", err)
            return False

    artifact_loader = ImsLoadArtifacts_v1_0_0()
    return artifact_loader(manifest_input_data)
