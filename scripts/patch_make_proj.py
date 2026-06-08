#!/usr/bin/env python3
# patch_make_proj.py — patch make_proj.tcl for cloud batch builds.
#
# Injects an IP import block after the source-file add step, which is
# the batch-mode equivalent of the manual GUI step:
#   "Add Sources → import_ip/ → Copy sources checked"
#
# This is needed because --regen_ip is broken in Vivado 2024.2, and the
# GUI step is not performed in headless builds.
#
# Usage: python3 patch_make_proj.py <path/to/make_proj.tcl>

import sys

path = sys.argv[1]
with open(path) as f:
    content = f.read()

# The block we anchor against — present in all known versions of make_proj.tcl
MARKER = (
    'if {[string equal $proj_create "yes"]} {\n'
    '    add_files -norecurse -fileset [get_filesets sources_1] $files\n'
    '}'
)

INJECT = """
# Import IP XCI files from import_ip/ (cloud batch equivalent of GUI step 8)
if {[string equal $proj_create "yes"]} {
    foreach xci_file [glob -nocomplain KiwiSDR/import_ip/*.xci] {
        import_ip $xci_file
    }
    upgrade_ip -quiet [get_ips *]
    generate_target all [get_ips *]
}"""

if MARKER not in content:
    print(f"ERROR: anchor not found in {path} — make_proj.tcl may have changed", file=sys.stderr)
    sys.exit(1)

patched = content.replace(MARKER, MARKER + INJECT, 1)

with open(path, 'w') as f:
    f.write(patched)

print(f"Patched {path}: IP import block injected")
