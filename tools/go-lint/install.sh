#!/bin/sh
set -eu
version=2.14.0
case "$(uname -s)/$(uname -m)" in
 Linux/x86_64) platform=linux-amd64; checksum=ab90aeb7b066f92a33415b638a50fe5344bbb75a0d32ad30cc248d88f81032ab ;;
 Linux/aarch64) platform=linux-arm64; checksum=ee7ec5f3453d15ddf106fae5a4d6c71737712348a979d1fe9cd52ec7ea299bae ;;
 *) echo "Run development/lint on the project Linux VM" >&2; exit 1 ;;
esac
destination="${CLOUD_LINT_CACHE:-${XDG_CACHE_HOME:-$HOME/.cache}/cloud-lint}/$version/$platform"
binary="$destination/golangci-lint"
if [ ! -x "$binary" ]; then
 temporary=$(mktemp -d)
 trap 'rm -rf "$temporary"' EXIT HUP INT TERM
 archive="golangci-lint-$version-$platform.tar.gz"
 curl --fail --silent --show-error --location "https://github.com/golangci/golangci-lint/releases/download/v$version/$archive" --output "$temporary/$archive"
 echo "$checksum  $temporary/$archive" | sha256sum --check --status
 tar -xzf "$temporary/$archive" -C "$temporary"
 mkdir -p "$destination"
 cp "$temporary/golangci-lint-$version-$platform/golangci-lint" "$binary"
 chmod 755 "$binary"
fi
"$binary" version | grep -Fq "version $version "
printf '%s\n' "$binary"
