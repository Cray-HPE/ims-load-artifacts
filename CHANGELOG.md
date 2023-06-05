# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased
### Changed
- CASMCMS-8656: Use `update_external_version` to get latest `ims-python-helper` version.

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
