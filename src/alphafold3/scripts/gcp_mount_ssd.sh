#!/bin/bash
# Copyright 2024 DeepMind Technologies Limited
#
# AlphaFold 3 source code is licensed under CC BY-NC-SA 4.0. To view a copy of
# this license, visit https://creativecommons.org/licenses/by-nc-sa/4.0/
#
# To request access to the AlphaFold 3 model parameters, follow the process set
# out at https://github.com/google-deepmind/alphafold3. You may only use these
# if received directly from Google. Use is subject to terms of use available at
# https://github.com/google-deepmind/alphafold3/blob/main/WEIGHTS_TERMS_OF_USE.md

set -euo pipefail

readonly MOUNT_DIR="${1:-/mnt/disks/ssd}"

if [[ -d "${MOUNT_DIR}" ]]; then
  echo "Mount directory ${MOUNT_DIR} already exists, skipping"
  exit 0
fi

for SSD_DISK in $(realpath "$(find /dev/disk/by-id/ | grep google-local)")
do
  # Check if the disk is already formatted
  if ! blkid -o value -s TYPE "${SSD_DISK}" > /dev/null 2>&1; then
    echo "Disk ${SSD_DISK} is not formatted, format it."
    mkfs.ext4 -m 0 -E lazy_itable_init=0,lazy_journal_init=0,discard "${SSD_DISK}" || continue
  fi

  # Check if the disk is already mounted
  if grep -qs "^/dev/nvme0n1 " /proc/mounts; then
    grep -s "^/dev/nvme0n1 " /proc/mounts
    echo "Disk ${SSD_DISK} is already mounted, skip it."
    continue
  fi

  # Disk is not mounted, mount it
  echo "Mounting ${SSD_DISK} to ${MOUNT_DIR}"
  mkdir -p "${MOUNT_DIR}"
  chmod -R 777 "${MOUNT_DIR}"
  mount "${SSD_DISK}" "${MOUNT_DIR}"
  break
done

if [[ ! -d "${MOUNT_DIR}" ]]; then
  echo "No unmounted SSD disks found"
  exit 1
fi
