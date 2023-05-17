#
# MIT License
#
# (C) Copyright 2018-2023 Hewlett Packard Enterprise Development LP
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
Common utilities for loading artifacts into IMS
"""

import logging
import os
from string import Template

import botocore.exceptions
from ims_python_helper import ImsHelper
import requests
from requests.adapters import HTTPAdapter
from urllib3 import Retry
import yaml


LOGGER = logging.getLogger(__name__)
IMS_URL = os.environ.get('IMS_URL', 'http://cray-ims').strip("/")
S3_IMS_BUCKET = os.environ.get('S3_IMS_BUCKET', "ims")
S3_BOOT_IMAGES_BUCKET = os.getenv('S3_BOOT_IMAGES_BUCKET', 'boot-images')
DOWNLOAD_ROOT = os.getenv('DOWNLOAD_PATH', '/tmp')
BOS_URL = os.environ.get('BOS_URL', 'http://cray-bos').strip("/")
BOS_SESSION_ENDPOINT = os.environ.get('BOS_SESSION_ENDPOINT', 'v1/sessiontemplate').lstrip("/")
BOS_KERNEL_PARAMETERS = os.environ.get('BOS_KERNEL_PARAMETERS',
                                       "console=ttyS0,115200 bad_page=panic crashkernel=340M hugepagelist=2m-2g "
                                       "intel_iommu=off intel_pstate=disable iommu=pt ip=dhcp "
                                       "numa_interleave_omit=headless numa_zonelist_order=node oops=panic "
                                       "pageblock_order=14 pcie_ports=native printk.synchronous=y rd.neednet=1 "
                                       "rd.retry=10 rd.shell turbo_boost_limit=999 "
                                       "spire_join_token=${SPIRE_JOIN_TOKEN}")
BOS_ROOTFS_PROVIDER = os.environ.get('BOS_ROOTFS_PROVIDER', 'cpss3')
BOS_ROOTFS_PROVIDER_PASSTHROUGH = os.environ.get(
    'BOS_ROOTFS_PROVIDER_PASSTHROUGH', 'dvs:api-gw-service-nmn.local:300:nmn0')
BOS_CFS_CONFIGURATION = os.environ.get('BOS_CFS_CONFIGURATION', '')
BOS_ENABLE_CFS = \
    'True' if os.environ.get('BOS_ENABLE_CFS', 'False').lower in ['true', 'on', 'yes', 't', '1'] else 'False'

S3_ENDPOINT = None
S3_SECRET_KEY = None
S3_ACCESS_KEY = None
S3_SSL_VERIFY = None


class ImsLoadArtifactsBaseException(Exception):
    """
    Toplevel ImsLoadArtifacts Exception
    """


class ImsLoadArtifactsDownloadException(ImsLoadArtifactsBaseException):
    """
    ImsLoadArtifacts Download Exception
    """


class ImsLoadArtifactsFileNotFoundException(ImsLoadArtifactsBaseException):
    """
    ImsLoadArtifacts File Not Found Exception
    """


class ImsLoadArtifactsPermissionException(ImsLoadArtifactsBaseException):
    """
    ImsLoadArtifacts Incorrect Permissions Exception
    """


class ImsLoadArtifacts_v1_0_0:
    """
    Load Artifacts Handler for 1.0.0 versioned manifest files
    """

    BOS_SESSION_TEMPLATE = \
        """
        boot_sets:
          compute:
            boot_ordinal: 2
            etag: ${ims_etag}
            kernel_parameters: ${bos_kernel_parameters}
            network: nmn
            node_roles_groups:
            - Compute
            path: ${ims_manifest_path}
            rootfs_provider: ${bos_rootfs_provider}
            rootfs_provider_passthrough: ${bos_rootfs_provider_passthrough}
            type: s3
        cfs:
          configuration: ${bos_cfs_configuration}
        enable_cfs: ${bos_enable_cfs}
        name: ${ims_image_name}
        """

    def __init__(self):
        self.session = requests.session()
        auth_token = os.getenv('AUTH_TOKEN')
        if auth_token:
            self.session.headers['Authorization'] = 'Bearer ' + auth_token
        self.retries = Retry(total=10, backoff_factor=2, status_forcelist=[502, 503, 504])
        self.session.mount("http://", HTTPAdapter(max_retries=self.retries))

    def create_bos_session_template(self, ims_etag, ims_manifest_path, ims_image_id):
        """
        Generate a BOS Session template for the IMS Image
        """
        try:
            bos_session_template = Template(self.BOS_SESSION_TEMPLATE).substitute({
                "ims_etag": ims_etag,
                "ims_manifest_path": ims_manifest_path,
                "ims_image_name": f'"IMS Id: {ims_image_id}"',
                'bos_kernel_parameters': BOS_KERNEL_PARAMETERS,
                'bos_rootfs_provider': BOS_ROOTFS_PROVIDER,
                'bos_rootfs_provider_passthrough': BOS_ROOTFS_PROVIDER_PASSTHROUGH,
                'bos_cfs_configuration': BOS_CFS_CONFIGURATION,
                'bos_enable_cfs': BOS_ENABLE_CFS,
            })
            LOGGER.debug(bos_session_template)
            body = yaml.safe_load(bos_session_template)
            if not isinstance(body, dict):
                LOGGER.error("Session Template must be formatted as a dictionary.")
                return False

            # When loading a dictionary value that is an empty string, yaml will convert the empty string to None.
            # >> > a = "{ a: { b: "" } }"
            # >> > yaml.safe_load(a)
            # {'a': {'b': None}}
            # This can cause BOS to throw an error. Fix up possible None values.

            body["boot_sets"]["compute"]["kernel_parameters"] = \
                '' if not body["boot_sets"]["compute"]["kernel_parameters"] \
                else body["boot_sets"]["compute"]["kernel_parameters"]
            body["boot_sets"]["compute"]["rootfs_provider"] = \
                '' if not body["boot_sets"]["compute"]["rootfs_provider"] \
                else body["boot_sets"]["compute"]["rootfs_provider"]
            body["boot_sets"]["compute"]["rootfs_provider_passthrough"] = \
                '' if not body["boot_sets"]["compute"]["rootfs_provider_passthrough"] \
                else body["boot_sets"]["compute"]["rootfs_provider_passthrough"]
            body["cfs"]["configuration"] = \
                '' if not body["cfs"]["configuration"] \
                else body["cfs"]["configuration"]

        except yaml.YAMLError as exc:
            LOGGER.error("BOS Session Template was not proper YAML: %s", exc)
            return False
        try:
            resp = self.session.post('/'.join([BOS_URL, BOS_SESSION_ENDPOINT]), json=body)
            resp.raise_for_status()
        except requests.RequestException as err:
            LOGGER.error("Problem contacting the Boot Orchestration Service (BOS): %s", err)
            return False
        return True

    def download_artifact(self, link, md5sum):
        """ download and verify artifact using link reference """

        def _download_http_artifact():
            """
            Handle download of http artifact
            """

            local_filename = os.path.abspath(os.path.join(DOWNLOAD_ROOT, link["path"].split('/')[-1]))
            with self.session.get(link["path"], stream=True) as r:
                r.raise_for_status()
                one_megabyte = 1024 * 1024
                with open(local_filename, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=one_megabyte):
                        f.write(chunk)
            return local_filename

        def _download_file_artifact():
            """
            Handle local artifacts that have been baked into the
            ims-load-artifacts container.
            """
            filename = link["path"]
            if not os.path.isfile(filename):
                raise ImsLoadArtifactsFileNotFoundException(
                    f"Failed to find artifact {filename} in given local container path. "
                    "Please contact your service person to notify HPE of this error."
                )
            if not os.access(filename, os.R_OK):
                # log file permissions and ownership
                st = os.stat(filename)
                LOGGER.info("Accessing local file: %s", filename)
                LOGGER.info("  File permissions: %s", oct(st.st_mode))
                LOGGER.info("  File ownership: %d,%d", st.st_uid, st.st_gid)
                LOGGER.info("  Current userid:grpid - %d:%d", os.getuid(), os.getgid())
                raise ImsLoadArtifactsPermissionException(
                    f"Failed to access artifact {filename} due to permission issues."
                )

            return filename

        try:
            local_filename = {
                "http": _download_http_artifact,
                "file": _download_file_artifact,
            }[link["type"]]()

            if md5sum:
                LOGGER.info("Verifying md5sum of the downloaded file.")
                lf_md5sum = ImsHelper._md5(local_filename)  # pylint: disable=protected-access
                if md5sum != lf_md5sum:
                    LOGGER.info("  Input md5    :%s", md5sum)
                    LOGGER.info("  Download md5 :%s", lf_md5sum)
                    raise ImsLoadArtifactsDownloadException("The calculated md5sum does not match the expected value.")
                LOGGER.info("Successfully verified the md5sum of the downloaded file.")
            else:
                LOGGER.info("Not verifying md5sum of the downloaded file.")

            return local_filename
        except KeyError:
            raise ImsLoadArtifactsDownloadException(
                f"Cannot download artifact due to unsupported or missing link type. {link}") from ValueError

    def load_recipe(self, ih, recipe_name, recipe_data):
        """ call IMS Helper to load recipe into IMS and S3 """

        ret_value = False
        try:
            md5sum = recipe_data["md5"]
            linux_distribution = recipe_data["linux_distribution"]
            link = recipe_data["link"]
            recipe_path = self.download_artifact(link, md5sum)
            template_dictionary = recipe_data.get("template_dictionary", [])

            try:
                return ih.recipe_upload(recipe_name, recipe_path, linux_distribution, template_dictionary)
            except requests.RequestException as exc:
                if hasattr(exc, "response"):
                    LOGGER.warning("IMS Service Response is %s", exc.response.text)
                else:
                    LOGGER.warning(exc)
            except (botocore.exceptions.BotoCoreError,
                    ImsLoadArtifactsDownloadException,
                    ImsLoadArtifactsFileNotFoundException) as exc:
                LOGGER.warning(exc)
                ret_value = False

        except (requests.RequestException, ImsLoadArtifactsDownloadException,
                ImsLoadArtifactsFileNotFoundException) as exc:
            LOGGER.warning("Error downloading recipe %s. %s", recipe_name, str(exc))
            ret_value = False
        except ValueError as exc:
            LOGGER.warning("Malformed recipe %s in manifest. Missing recipe value. %s", recipe_name, str(exc))
            ret_value = False

        return ret_value

    def load_recipes(self, manifest_data):
        """ Process IMS recipes listed in the manifest file. """

        ret_value = True
        recipe_results = {'recipes': {}}

        ih = ImsHelper(
            ims_url=IMS_URL,
            session=self.session,
            s3_endpoint=S3_ENDPOINT,
            s3_secret_key=S3_SECRET_KEY,
            s3_access_key=S3_ACCESS_KEY,
            s3_ssl_verify=S3_SSL_VERIFY,
            s3_bucket=S3_IMS_BUCKET
        )

        if "recipes" in manifest_data:
            for recipe_name, recipe_data in manifest_data["recipes"].items():
                recipe_result = self.load_recipe(ih, recipe_name, recipe_data)
                if recipe_result:
                    recipe_results['recipes'][recipe_name] = {'id': recipe_result['id']}
                else:
                    ret_value = False

        if ret_value:
            return recipe_results

        return ret_value

    def download_image_artifact(self, artifact_data):
        """ Helper function to download image artifact """
        LOGGER.debug('Artifact Data: "%s" ', artifact_data)
        md5 = artifact_data["md5"]
        link = artifact_data["link"]
        mime_type = artifact_data["type"]
        artifact_path = self.download_artifact(link, md5)
        return mime_type, artifact_path

    def load_image(self, ih, image_name, image_data):
        """ call IMS Helper to load image into IMS and S3 """
        ret_value = False
        try:
            image_artifacts = {}
            for artifact_data in image_data["artifacts"]:
                mime_type, image_artifact = self.download_image_artifact(artifact_data)
                image_artifacts[mime_type] = image_artifact

            rootfs = [image_artifacts['application/vnd.cray.image.rootfs.squashfs']] \
                if image_artifacts.get('application/vnd.cray.image.rootfs.squashfs') else None
            kernel = [image_artifacts['application/vnd.cray.image.kernel']] \
                if image_artifacts.get('application/vnd.cray.image.kernel') else None
            initrd = [image_artifacts['application/vnd.cray.image.initrd']] \
                if image_artifacts.get('application/vnd.cray.image.initrd') else None
            boot_parameters = [image_artifacts['application/vnd.cray.image.parameters.boot']] \
                if image_artifacts.get('application/vnd.cray.image.parameters.boot') else None

            ih_upload_kwargs = {
                'image_name': image_name,
                'rootfs': rootfs,
                'kernel': kernel,
                'initrd': initrd,
                'boot_parameters': boot_parameters
            }
            if os.getenv('IUF'):
                # Only skip images with the same name when running in an IUF context.
                ih_upload_kwargs['skip_existing'] = True

            try:
                result = ih.image_upload_artifacts(**ih_upload_kwargs)
                if os.environ.get("CREATE_BOS_SESSION_TEMPLATE", "False").lower() in ['true', 'on', 'yes', 't', '1']:
                    try:
                        LOGGER.info('Creating BOS Session Temnplate for image "%s"', image_name)
                        ims_etag = result["ims_image_record"]["link"]["etag"]
                        ims_image_path = result["ims_image_record"]["link"]["path"]
                        ims_image_id = result["ims_image_record"]["id"]
                        self.create_bos_session_template(ims_etag, ims_image_path, ims_image_id)
                    except KeyError as exc:
                        LOGGER.error("Error creating BOS Session Template. IMS image result missing variable %s. %s",
                                     exc, result)
                return result
            except requests.RequestException as exc:
                if hasattr(exc, "response"):
                    LOGGER.warning("IMS Service Response is %s", exc.response.text)
                else:
                    LOGGER.warning(exc)
            except (botocore.exceptions.BotoCoreError,
                    ImsLoadArtifactsDownloadException,
                    ImsLoadArtifactsFileNotFoundException) as exc:
                LOGGER.warning(exc)
                ret_value = False

        except (requests.RequestException, ImsLoadArtifactsDownloadException,
                ImsLoadArtifactsFileNotFoundException) as exc:
            LOGGER.warning("Error downloading image %s. %s", image_name, str(exc))
            ret_value = False

        except ValueError as exc:
            LOGGER.warning("Malformed image %s in manifest. Missing image value. %s", image_name, str(exc))
            ret_value = False

        return ret_value

    def load_images(self, manifest_data):
        """ Process IMS images listed in the manifest file. """

        ret_value = True
        image_results = {'images': {}}

        ih = ImsHelper(
            ims_url=IMS_URL,
            session=self.session,
            s3_endpoint=S3_ENDPOINT,
            s3_secret_key=S3_SECRET_KEY,
            s3_access_key=S3_ACCESS_KEY,
            s3_ssl_verify=S3_SSL_VERIFY,
            s3_bucket=S3_BOOT_IMAGES_BUCKET
        )

        if "images" in manifest_data:
            for image_name, image_data in manifest_data["images"].items():
                image_result = self.load_image(ih, image_name, image_data)
                if image_result:
                    image_results['images'][image_name] = {
                        'id': image_result['ims_image_record']['id']
                    }
                else:
                    ret_value = False

        if ret_value:
            return image_results

        return ret_value

    def __call__(self, manifest_data):
        """ Process IMS recipes and images listed in the manifest file. """
        ret_recipes = self.load_recipes(manifest_data)
        ret_images = self.load_images(manifest_data)

        # If everything was successful, write out the results
        if all([ret_recipes, ret_images]):
            records = dict(ret_recipes, **ret_images)
            LOGGER.info(yaml.dump(records))
            with open('/results/records.yaml', 'wt', encoding='utf-8') as results_file:
                yaml.dump(records, results_file)

        # Return a boolean of if everything was successful
        return all([ret_recipes, ret_images])
