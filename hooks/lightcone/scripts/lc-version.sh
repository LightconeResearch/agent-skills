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
# LC_VERSION_MAX — highest supported `lc` (inclusive); empty means open-ended.
#
# NOTE: 0.0.0 is a placeholder. The real floor is the first de-bundled
# lightcone-cli release; the value is still under discussion. The mechanism is
# what lands now, not the number.
#
# LC_VERSION_MAX is compared against the full installed X.Y.Z (not a minor-series
# prefix). Policy: once the first de-bundled release has a version number, cap
# MAX at the current minor series so the plugin warns on the next minor. Both
# bounds are set together at release time.
LC_VERSION_MIN="0.0.0"
LC_VERSION_MAX=""

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
  if [ -n "$LC_VERSION_MAX" ] && lc_version_lt "$LC_VERSION_MAX" "$cur"; then
    echo "WARNING: lc $cur is newer than this plugin's tested maximum (${LC_VERSION_MAX}). The plugin is behind lightcone-cli; behavior may differ from what the skills expect. Please suggest updating the lightcone plugin to the user (plugin marketplace update)."
    return 0
  fi
}
