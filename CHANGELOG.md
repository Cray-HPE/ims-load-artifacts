# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.9.0] - 2025-06-17
### Dependencies
- CASMCMS-8022:  update python modules
- Bumped dependency patch versions:
| Package                | From      | To        |
|------------------------|-----------|-----------|
| `boto3`                | 1.12.49   | 1.36.2    |
| `botocore`             | 1.15.49   | 1.36.26   |
| `certifi`              | 2023.7.22 | 2025.6.15 |
| `chardet`              | 3.0.4     | 5.2.0     |
| `docutils`             | 0.14      | 0.21.0    |
| `idna`                 | 2.8       | 3.10.0    |
| `jmespath`             | 0.9.5     | 1.0.1     |
| `oauthlib`             | 2.1.0     | 3.2.2     |
| `requests`             | 2.23.0    | 2.32.4    |
| `requests-oauthlib`    | 1.0.0     | 2.0.0     |
| `s3transfer`           | 0.3.7     | 0.11.3    |
| `urllib3`              | 1.25.11   | 2.4.0     |
| `Jinja2`               | 3.0.3     | 3.1.6     |

## [2.8.0] - 2025-02-13
### Dependencies
- CASMCMS-9282: Bump Alpine version from 3.15 to 3.18, because 3.15 no longer receives security patches

## [2.7.2] - 2024-07-25
### Dependencies
- Resolve CVE by bumping `certifi` from 2019.11.28 to 2023.7.22

## [2.7.1] - 2024-04-10
### Dependencies
- Bump `ims-python-helper` from `2.14` to `3.0`

## [2.7.0] - 2023-08-14
### Changed
- CASMCMS-8743 - templatize the BOS kernel parameters.
- Disabled concurrent Jenkins builds on same branch/commit
- Added build timeout to avoid hung builds

### Dependencies
Bumped dependency patch versions:
| Package                  | From     | To       |
|--------------------------|----------|----------|
| `boto3`                  | 1.12.9   | 1.12.49  |
| `botocore`               | 1.15.9   | 1.15.49  |
| `jmespath`               | 0.9.4    | 0.9.5    |
| `python-dateutil`        | 2.8.1    | 2.8.2    |
| `s3transfer`             | 0.3.0    | 0.3.7    |
| `urllib3`                | 1.25.9   | 1.25.11  |

## [2.6.1] - 2023-07-18
### Dependencies
- Bump `PyYAML` from 5.4.1 to 6.0.1 to avoid build issue caused by https://github.com/yaml/pyyaml/issues/601

## [2.6.0] - 2023-06-13
### Changed
- CASMCMS-8656: Use `update_external_version` to get latest `ims-python-helper` version.
- Pin ims-python-helper to 2.14.z.

## [2.5.3] - 2023-06-05
### Changed
- CASMCMS-8365 - Add platform information to loader.

## [2.5.2] - 2023-06-05
### Changed
- CASM-4232: Require at least version 2.14.0 of `ims-python-helper` in order to get associated logging enhancements.

## [2.5.1] - 2023-05-31
### Changed
- CASM-4232: Enhanced logging for [`loaders.py`](ims_load_artifacts/loaders.py) for use with IUF.

## [2.5.0] - 2023-05-24
### Changed
- Default to creating BOS session templates using BOS v2 instead of BOS v1. Add support for new `BOS_SESSIONTEMPLATES_ENDPOINT`
  environment variable, reflecting corresponding change in the [`cray-import-kiwi-recipe-image`](https://github.com/Cray-HPE/cray-import-kiwi-recipe-image)
  repository.

## [2.4.0] - 2023-05-23
### Changed
- BOS session templates that are created now follow BOS's stated (but currently unenforced)
  restrictions on template names.
  
### Removed
- Removed defunct files leftover from previous versioning system

## [2.3.0] - 2023-04-18
### Changed
- Use `ims-python-helper>=2.12.0` to use artifact checksums to determine equality
  of IMS images and recipes.

## [2.2.1] - 2023-02-07
### Changed
- Use `ims-python-helper>=2.11.1` to fix `KeyError` bug when finding duplicate
  IMS images.

## [2.2.0] - 2023-02-03
### Changed
- Use `ims-python-helper>=2.11.0` to prevent new images from being
  created with a duplicate name in the IUF.

## [2.1.0] - 2023-02-03
### Fixed
- CASMINST-5843: Update the nobody user in Dockerfile to own the `/etc/ssl/certs` directory to allow `update-ca-certificates` to add user certificates.

## [2.0.1] - 2022-12-20
### Added
- Add Artifactory authentication to Jenkinsfile

### Fixed
- Revert constraints to use `ims-python-helper>=2.10.0`.

## [2.0.0] - 2022-12-08
### Added
- Add support for IUF `ims_upload` operation.

## [1.6.2] - 2022-12-02
### Added
- Authenticate to CSM's artifactory

## [1.6.1] - 2022-10-05
### Changed
- CASMCMS-8272 - add timeout to request due to pylint failure.

## [1.6.0] - 2022-08-02
### Changed
- CASMCMS-7970 - update to new version of ims-python-helper.

## [1.5.0] - 2022-07-28
### Changed
- CASMTRIAGE-3756 - added file permission checking and better logging.
- CASMCMS-7970 - ims update cray.dev.com addresses

## [1.4.0] - 2022-06-30
### Added
- Add support for loading IMS recipes that have template parameters
