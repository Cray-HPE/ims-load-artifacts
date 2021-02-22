#!/usr/bin/env python3
# Copyright 2019-2021 Hewlett Packard Enterprise Development LP
"""
Cray IMS Load Artifacts Container
This loads and registers recipes and pre-built image artifacts with IMS.
"""

import logging
import os
import sys
import time
from string import Template

import botocore.exceptions
import requests
import urllib3
import yaml
from ims_python_helper import ImsHelper
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

LOGGER = logging.getLogger(__name__)

MANIFEST_FILE = os.environ.get("MANIFEST_FILE", "/manifest.yaml")
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


def wait_for_istio():
    """
    Loop until we are successfully able to call the IMS ready endpoint.
    """
    LOGGER.debug("Waiting for Istio...")
    ims_ready_endpoint = "/".join([IMS_URL, "healthz/ready"])
    while True:
        try:
            LOGGER.debug("Calling ims ready endpoint")
            r = requests.get(ims_ready_endpoint)
            if r.ok:
                LOGGER.info("Successfully talked to IMS Ready endpoint.")
                break
            LOGGER.warning("Could not talk to IMS Ready endpoint. Request returned http status %s", r.status_code)
        except requests.RequestException as exc:
            LOGGER.warning(exc)
        LOGGER.info("Trying again in 2 seconds")
        time.sleep(2)


class _ImsLoadArtifacts_v1_0_0:
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
                "ims_image_name": '"IMS Id: {}"'.format(ims_image_id),
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
            if not os.path.isfile(link["path"]):
                raise ImsLoadArtifactsFileNotFoundException(
                    "Failed to find artifact {} in given local container path. Please contact "
                    "your service person to notify HPE of this error.".format(link["path"])
                )
            return link["path"]

        try:
            local_filename = {
                "http": _download_http_artifact,
                "file": _download_file_artifact,
            }.get(link["type"])()

            if md5sum:
                LOGGER.info("Verifying md5sum of the downloaded file.")
                if md5sum != ImsHelper._md5(local_filename):  # pylint: disable=protected-access
                    raise ImsLoadArtifactsDownloadException("The calculated md5sum does not match the expected value.")
                LOGGER.info("Successfully verified the md5sum of the downloaded file.")
            else:
                LOGGER.info("Not verifying md5sum of the downloaded file.")

            return local_filename
        except ValueError:
            raise ImsLoadArtifactsDownloadException(
                "Cannot download artifact due to unsupported or missing link type. {}".format(link)) from ValueError

    def load_recipe(self, ih, recipe_name, recipe_data):
        """ call IMS Helper to load recipe into IMS and S3 """

        ret_value = False
        try:
            md5sum = recipe_data["md5"]
            linux_distribution = recipe_data["linux_distribution"]
            link = recipe_data["link"]
            recipe_path = self.download_artifact(link, md5sum)

            try:
                return ih.recipe_upload(recipe_name, recipe_path, linux_distribution)
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
            with open('/results/records.yaml', 'w') as results_file:
                yaml.dump(records, results_file)

        # Return a boolean of if everything was successful
        return all([ret_recipes, ret_images])


def load_artifacts():
    """
    Read a manifest.yaml file. If the object was not found, log it and return an error..
    """
    with open(MANIFEST_FILE) as inf:
        manifest_data = yaml.safe_load(inf)

    try:
        return {
            "1.0.0": _ImsLoadArtifacts_v1_0_0()
        }.get(manifest_data["version"])(manifest_data)
    except ValueError:
        raise ImsLoadArtifactsBaseException(
            "Cannot process manifest.yaml due to unsupported or missing manifest version {}".format(manifest_data)) \
            from ValueError


def main():
    """
    Load artifacts from manifest.yaml into S3 and register with IMS.
    """

    # pylint: disable=global-statement
    global S3_ENDPOINT
    global S3_SECRET_KEY
    global S3_ACCESS_KEY
    global S3_SSL_VERIFY

    retValue = 0

    log_level = os.environ.get('LOG_LEVEL', 'WARN')
    logging.basicConfig(level=log_level)

    try:
        # The key names used below match the values defined in the
        #  *-s3-credentials secrets available on shasta systems.
        # ncn-w001:~ # kubectl  get secrets -o yaml ims-s3-credentials
        # data:
        #   access_key: R0k0WEdKVzJPSDlZQkVaOVkwNjk=
        #   s3_endpoint: aHR0cDovL3Jndy5sb2NhbDo4MDgw
        #   secret_key: NDdHZUdPanhPNlhRc2RMUWxyb1k3WXhvMWNqb2NLMmoxQnBRb0o4NQ==
        #   ssl_validate: ZmFsc2U=
        S3_ENDPOINT = os.environ['S3_ENDPOINT']
        S3_SECRET_KEY = os.environ['SECRET_KEY']
        S3_ACCESS_KEY = os.environ['ACCESS_KEY']
        S3_SSL_VERIFY = os.environ['SSL_VALIDATE']
    except KeyError as key_error:
        LOGGER.error("Missing environment variable %s.", key_error)
        sys.exit(1)

    wait_for_istio()

    try:
        retValue = 0 if load_artifacts() else 1
    except FileNotFoundError as exc:
        LOGGER.error("Missing manifest file.", exc_info=exc)
    except ImsLoadArtifactsBaseException as exc:
        LOGGER.error(exc)

    return retValue


if __name__ == '__main__':
    sys.exit(main())
