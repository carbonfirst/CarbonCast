# libaec Changelog
All notable changes to libaec will be documented in this file.

## [1.0.2] - 2017-10-18

### Fixed
- C99 requirement in all build systems

## [1.0.1] - 2017-07-14

### Fixed
- Potential security vulnerabilities in decoder exposed by libFuzzer.

### Added
- Fuzz target for decoding and encoding.

### Changed
- Improved Cmake support by Christoph Junghans

## [1.0.0] - 2016-11-16

### Added
- Include CCSDS test data with libaec. See THANKS.

### Changed
- Better compatibility with OSX for make check.
- Allow Cygwin to build DLLs.

## [0.3.4] - 2016-08-16

### Fixed
- Pad incomplete last line when in SZ compatibility mode.

## [0.3.3] - 2016-05-12

### Fixed
- Bug with zero blocks in the last RSI (reference sample interval)
when data size is not a multiple of RSIs or segments (64 blocks) and
the zero region reaches a segment boundary.
- More robust error handling.

### Changed
- Vectorization improvement for Intel compiler.
- Better compatibility with netcdf's build process.

## [0.3.2] - 2015-02-04

### Changed
- Allow nonconforming block sizes in SZ mode.
- Performance improvement for decoder.

## [0.3.1] - 2014-10-23

### Fixed
- Allow incomplete scanlines in SZ mode.

## [0.3] - 2014-08-06

### Changed
- Performance improvement for encoding pre-precessed data.
- More efficient coding of second extension if reference sample is
present.
- Port library to Windows (Visual Studio).

### Added
- Support building with CMake.
- Benchmarking target using ECHAM data (make bench).

## [0.2] - 2014-02-12

### Fixed
- Incorrect length calculation in assessment of Second Extension
coding.
- Unlimited encoding of fundamental sequences.
- Handle corrupted compressed data more gracefully.

### Added
- Additional testing with official CCSDS sample data.
- Support restricted coding options from latest standard.

### Changed
- Facilitate generation of SIMD instructions by compiler.

## [0.1] - 2013-05-21

### Added
- Initial release.
