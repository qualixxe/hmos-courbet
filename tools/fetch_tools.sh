#!/bin/sh
# Download the erofs-utils build with Android extensions (extract.erofs,
# mkfs.erofs --fs-config-file/--file-contexts) into tools/bin.
# Source: https://github.com/sekaiacg/erofs-utils (Apache-2.0 / GPL-2.0)
set -e
cd "$(dirname "$0")"
TAG=v1.8.10-251217
case "$(uname -m)" in
  x86_64|amd64) ARCH=x86_64; SHA=6d6c6b0e7ad7273cc019644e5d6ad1e263142fad72874e169cc0731854f95bf1 ;;
  aarch64|arm64) ARCH=aarch64; SHA=b5f2563e0b1c9713d71b6f95735df916cf18c1a4ef18197b30f4b54f1d3b461b ;;
  *) echo "unsupported architecture $(uname -m)"; exit 1 ;;
esac
ZIP=erofs-utils-v1.8.10-gee46dd74-251217-Linux_$ARCH.zip
URL=https://github.com/sekaiacg/erofs-utils/releases/download/$TAG/$ZIP
mkdir -p bin
if command -v curl >/dev/null; then curl -L -o "bin/$ZIP" "$URL"; else wget -O "bin/$ZIP" "$URL"; fi
echo "$SHA  bin/$ZIP" | sha256sum -c -
(cd bin && unzip -o "$ZIP" && rm -f "$ZIP" && chmod +x *.erofs)
echo "erofs tools installed in tools/bin:"
ls bin
