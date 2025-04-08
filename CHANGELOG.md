# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## v1.1.0
### Added
- Added `--include-file` argument to include file names at any level in the context tree (equivalent to the `**/{file}` glob pattern).
- Added `-t` alias for `--count-tokens`
### Fixed
- Fixed inclusion of excluded directories in context tree output.
- Fixed detection of some json files as binary.

## v1.0.0
### Added
- Initial release.
