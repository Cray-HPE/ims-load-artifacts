# IMS Load Artifacts

The Image Management Service (IMS) Load Artifacts utility loads product recipes 
and pre-built product images into IMS from the Nexus artifact repository service. 
Recipes and Images that are successfully loaded into IMS by the Load Artifacts 
utility result in new IMS Recipe and Image records.

The utility also writes out `/results/records.yaml` which provides information
about the IMS records that were created for recipes and images, respectively.
Example file contents:

```yaml
images:
  foo:
    id: a49d6d6e-6463-4530-86cd-7055ad8ceb93
  bar:
    id: bc42542d-292a-4921-a09c-2c63d892086b
recipes:
  foo:
    id: 32d19800-f4c9-4f7c-99a5-cd77a836b89d
  bar:
    id: 35b3f7f2-4c85-432f-a1db-035408073153
```

## Environment Variables

* `LOG_LEVEL` -- the level of logging output (`DEBUG`, `INFO`, `WARN`, `ERROR`, `CRITICAL`), defaults to `WARN`.
* `IMS_URL` -- URL to use to access IMS, defaults to `http://cray-ims`.
* `S3_IMS_BUCKET` -- S3 bucket to upload IMS recipes to, defaults to `IMS`.
* `S3_BOOT_IMAGES_BUCKET` -- S3 bucket to upload pre-built images and boot artifacts to, defaults to `boot-images`.

On a shasta system, the `ims-s3-credentials` secret should be used to populate the following environment variables.
* `S3_ENDPOINT` -- URI to use to talk to the S3 host, example: `https://rgw-vip.local`
* `ACCESS_KEY` -- Access key used to authenticate to S3
* `SECRET_KEY` -- Secret key used to authenticate to S3
* `SSL_VALIDATE` -- Whether to validate SSL connections. Currently, this should be set to `False`.

Example:
```
LOG_LEVEL = INFO
IMS_URL = https://cray-ims
S3_ENDPOINT = https://rgw-vip.local
ACCESS_KEY = FI9O1CZJWZIUPWS2WI2H
SECRET_KEY = WHkGp6YsAtpZZnc9JBZ6o4NiSch6hniZnAUmbNXx
SSL_VALIDATE = False
S3_IMS_BUCKET = ims
S3_BOOT_IMAGES_BUCKET = boot-images
```

## manifest.yaml

The ims-load-artifacts container will look for a file named `manifest.yaml` in the root of the running image. This
file contains the list of IMS recipes and pre-built images to be uploaded to S3 and added to IMS. 

```
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
```

## Build the Docker image
docker build -t dtr.dev.cray.com/cray/cray-ims-load-artifacts .

## Run the Docker image
```bash
$ docker run --rm \
 -e IMS_URL=http://cray-ims \
 -e S3_ENDPOINT=https://rgw-vip.local \
 -e ACCESS_KEY=FI9O1CZJWZIUPWS2WI2H \
 -e SECRET_KEY=WHkGp6YsAtpZZnc9JBZ6o4NiSch6hniZnAUmbNXx \
 -e SSL_VALIDATE=False \
 -e S3_IMS_BUCKET=ims \
 -e S3_BOOT_IMAGES_BUCKET=boot-images \
 -e LOG_LEVEL=INFO \
 dtr.dev.cray.com/cray/cray-ims-load-artifacts:latest
```

## Contributing

To develop, clone this git repo and install the prerequisites. A requirements.txt and constraints.txt file are provided for you. 
```bash 
$ git clone <repo url> ims_load_artifacts 
$ cd ims_load_artifacts
$ pip install -r requirements.txt
```

You are now ready to make changes to the codebase (preferably in a virtual environment).

## Testing

Note that the unit tests and linters are run when the docker image is built.

```
(ims_load_artifacts) $ pip install -r requirements.txt
(ims_load_artifacts) $ pip install -r requirements-test.txt
(ims_load_artifacts) $ python3 -m unittest -v 
test_load_artifacts (tests.test_load_artifacts.TestLoadArtifacts)
tests.test_load_artifacts.TestLoadArtifacts.test_init ... ok

----------------------------------------------------------------------
Ran 1 test in 0.193s

OK
```

## License

Copyright 2019-2020 Hewlett Packard Enterprise Development LP
