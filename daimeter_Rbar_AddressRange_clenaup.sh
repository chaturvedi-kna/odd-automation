#!/bin/bash

# Directory containing the files
cd /home/drapush/BDRA/AHD/ADRA/ADRA01/SOAM/RBAR/Rbar/ || exit 1

# Save the latest 5 PeerRouteRule files
ls -ltrh *Rbar_AddressRange.csv | tail -n 6 | awk '{print $NF}' > /tmp/keep_AddressRange.list

# Delete everything except those 5 files
find . -maxdepth 1 -type f | while read -r f; do
    grep -Fxq "${f#./}" /tmp/keep_AddressRange.list || rm -f "$f"
done