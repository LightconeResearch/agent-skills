#!/bin/bash
# Single source of truth for the `lc` (lightcone-cli) version range this plugin
# is built against. The lightcone plugin ships one global version that tracks the
# marketplace, so it can drift from the `lc` a project actually has installed.
# The session-start hook sources this file and WARNS (never blocks) when the
# installed `lc` falls outside the declared range — a hard block would brick
# every session on version skew.
#
# The astra plugin needs no equivalent: it pins astra-spec and runs astra via
# uvx, so it is self-consistent by construction.
#
# LC_VERSION_MIN — lowest `lc` this plugin supports (inclusive).
# LC_VERSION_MAX — exclusive upper bound; empty means open-ended.
#
# Range: 0.4.0 <= lc < 0.5.0 (agreed 2026-07-24, pending confirmation with
# Francois and Alexandre). 0.4.0 is the first de-bundled lightcone-cli release:
# older CLIs bundle their own copy of the skills, so running them next to the
# marketplace plugin double-ships every skill. The exclusive ceiling means the
# whole 0.4 series is in range; a future 0.5 warns until a plugin release
# blesses it. Both bounds move together at each contract-changing release.
LC_VERSION_MIN="0.4.0"
LC_VERSION_MAX="0.5.0"

# True when semver $1 is strictly less than semver $2 (sort -V ordering).
lc_version_lt() {
  [ "$1" != "$2" ] && [ "$(printf '%s\n%s\n' "$1" "$2" | sort -V | head -n1)" = "$1" ]
}

# Echo the installed `lc` core version (X.Y.Z), stripping any dev/local suffix.
# Empty output means lc is absent or its --version output was unparseable.
lc_installed_version() {
  command -v lc &>/dev/null || return 0
  lc --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -n1
}

# Echo a one-line warning when the installed lc is out of range; echo nothing
# when lc is absent, unparseable, or in range. Silent = fine, as before.
lc_version_warning() {
  local cur
  cur=$(lc_installed_version)
  [ -z "$cur" ] && return 0

  if lc_version_lt "$cur" "$LC_VERSION_MIN"; then
    echo "WARNING: lc $cur is older than this plugin's minimum (${LC_VERSION_MIN}). lightcone-cli is behind the plugin; some skills may misbehave. Please suggest upgrading lightcone-cli to the user."
    return 0
  fi
  if [ -n "$LC_VERSION_MAX" ] && ! lc_version_lt "$cur" "$LC_VERSION_MAX"; then
    echo "WARNING: lc $cur is at or beyond this plugin's tested ceiling (${LC_VERSION_MAX}, exclusive). The plugin is behind lightcone-cli; behavior may differ from what the skills expect. Please suggest updating the lightcone plugin to the user (plugin marketplace update)."
    return 0
  fi
}
