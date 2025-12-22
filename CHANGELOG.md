# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.0]
### Added
- Adds new `--no-content-template-default` flag to enable the no-content template.
### Fixed
- Fixed `ValueError` when encountering symlinks pointing outside the indexed directory.

## [1.2.0]
### Added
- Added `--encoding` "gemini", "gemini-1.5-pro", "gemini-1.5-flash" options using Vertexai local tokenization.

## [1.1.0]
### Added
- Added `--include-file` argument to include file names at any level in the context tree (equivalent to the `**/{file}` glob pattern).
- Added `-t` alias for `--count-tokens`
### Fixed
- Fixed inclusion of excluded directories in context tree output.
- Fixed detection of some json files as binary.

## [1.0.0]
### Added
- Initial release.
