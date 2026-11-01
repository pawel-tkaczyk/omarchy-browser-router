# Browser Router for Omarchy

Open work links in your work profile, personal links in your personal profile,
and shared sites in a browser picker. A native Omarchy shell plugin with a small,
local URL handler. No Python packages, background daemon, or network service.

**Status: initial release (0.1.1).** Requires Omarchy's Quickshell plugin system
(`omarchy plugin validate` must be available), Python 3.10+, and xdg-utils.

## Features

- Detect installed browsers from XDG desktop entries and executable availability.
- Discover named Chromium profiles from `Local State`, and Firefox-family profiles
  from `profiles.ini`; include each browser's own default as an additional choice.
- Route domains, subdomains, or paths to a browser/profile, or **Ask each time**.
- Unmatched URLs use your chosen default browser/profile; initially follows
  Omarchy's browser choice.
- Compact picker with **Open once**, **Always for this domain**, and **Skip**.
- Add, edit, remove, and reorder rules. First matching rule wins.
- Pause rules and test a URL without opening a browser.
- Enable/disable routing, preserving previous HTTP and HTTPS handlers separately.
- Theme-aware QML controls, keyboard focus, RTL layouts, and translation catalogs.
- Private-window requests preserve private mode for supported browser families.
- If a saved profile disappears, ask instead of silently selecting another identity.

## Install

```sh
git clone https://github.com/pawel-tkaczyk/omarchy-browser-router.git
cd omarchy-browser-router
python3 install.py --enable-plugin
```

Open **Browser Router Settings** in your app launcher, choose your fallback, add
rules, then click **Enable routing**. Installation alone does not change your
default browser. The installer backs up `~/.config/omarchy/shell.json` before
registering the panel. The shell watches plugin and config changes automatically.

Alternatively, install the repository using Omarchy's plugin manager, then run
its installer to register the URL handler and settings launcher:

```sh
omarchy plugin add https://github.com/pawel-tkaczyk/omarchy-browser-router
python3 ~/.config/omarchy/plugins/paweltkaczyk.browser-router/install.py --enable-plugin
```

Optional bar icon (the panel also works without one):

```sh
python3 ~/.config/omarchy/plugins/paweltkaczyk.browser-router/install.py --bar-icon
```

Open settings from the terminal:

```sh
omarchy-browser-router settings
```

If your `PATH` does not include `~/.local/bin`, use that directory's absolute
path for the command. The installed desktop entries use absolute paths for
ordinary home directories. If your home path requires quoting (for example,
contains spaces), the browser handler uses the bare command and `~/.local/bin`
must be on the session's `PATH`, since Omarchy's browser resolver does not parse
quoted executables in desktop entries.

## Rules

| Pattern | Matches |
|---|---|
| `example.com` | That exact domain, any path, HTTP or HTTPS |
| `*.example.com` | Subdomains, including nested ones; excludes `example.com` |
| `github.com/company` | `/company` and descendants, excluding `/company-other` |
| `https://example.com/team` | That path, HTTPS only |
| `localhost:3000` | That host and explicit port |

Domains are case insensitive and international domain names are normalized.
Paths are case sensitive. Query strings and fragments are ignored when matching;
rules themselves cannot contain either. A trailing slash does not change a path
rule's meaning. Put narrow path rules above broad domain rules.

Choose **Ask each time** for sites you use in multiple profiles. The picker’s
**Always for this domain** adds an exact-domain rule at the top of the list.

## Omarchy integration

The system default is read through `omarchy-cmd-default-browser`, the same source
used by `omarchy launch browser`; there is no separate hardcoded default browser.
While the router is registered as the default HTTP/HTTPS handler, **Follow
Omarchy’s browser setting** uses the browser selected immediately before routing
was enabled. An explicitly selected fallback profile overrides that choice.

`omarchy default browser firefox` (and Omarchy's browser selection menu) replaces
the XDG handler with Firefox, disabling interception. Click **Enable routing**
again to adopt the new setting. This is deliberate: the plugin never fights
Omarchy's browser setter or edits packaged Omarchy scripts.

An existing `omarchy-browser.desktop` handler is left intact; Omarchy's launcher
resolves the underlying router through its regular default-browser lookup.
Other commands that invoke a browser binary directly bypass routing.

## Browser support

| Family | Native profiles |
|---|---|
| Chromium | Brave, Brave Origin, Chrome, Chromium, Edge, Vivaldi, Opera |
| Firefox | Firefox, Zen, LibreWolf, Floorp, Waterfox, Mullvad Browser |
| Other XDG HTTPS browsers | Browser-level selection; no profile discovery |

Flatpak desktop launchers and conventional profile locations are supported.
Snap profile roots are recognized for `/snap/` launchers. Sandboxed browser
packaging and less common forks may use different profile locations; report
examples with browser/version and a redacted launcher, without profile data.
Native beta/nightly channels currently fall back to browser-level discovery.
Firefox's newer selectable-profile SQLite databases and Firefox containers are
not discovered; `profiles.ini` is the supported registry. Profiles launched with
Firefox's `--no-remote` cannot accept subsequent external links normally.
Browser wrappers and their existing arguments are preserved, including Omarchy's
packaged launchers and browser flags. Browsers perform their own running-instance
handoff. Generic browsers have no assumed private-mode flag.

## Scope and privacy

Routes **links opened from other applications**, not navigation inside an
existing browser tab. No browser extension is installed.

Only HTTP(S) links without embedded credentials are accepted. URL and profile
arguments are passed as an argument array, never evaluated as shell commands.
Matching does not fetch URLs, follow HTTP redirects, or contact any service.
SafeLinks/Google redirect unwrapping is intentionally left for a later opt-in
feature; this release opens the URL the calling application provided.

Rules live in `~/.config/omarchy/browser-router.json` (honoring `XDG_CONFIG_HOME`).
Queued picker links are stored in private files under
`~/.local/state/omarchy/browser-router/pending/` (`XDG_STATE_HOME` respected),
deleted when handled and expired after one day on the next settings refresh.
Closing the picker leaves links queued so accidental dismissal does not lose
them. Reopen settings to handle them. There is no browsing history or telemetry.

## Update and uninstall

For a cloned checkout, `git pull` and rerun `python3 install.py --enable-plugin`.
For a plugin-manager checkout, use `omarchy plugin update paweltkaczyk.browser-router`
and rerun its installer if installed launcher paths have changed.

```sh
python3 ~/.config/omarchy/plugins/paweltkaczyk.browser-router/install.py --uninstall
```

Uninstall restores the previous handlers only where the router is still selected,
removes launchers and shell registration, and keeps URL rules. If running the
uninstaller from inside its own plugin checkout, the source directory is kept;
remove it afterwards with Omarchy's plugin manager. Choose **Disable routing**
first if you prefer to remove the plugin through Omarchy's UI.

## Development

```sh
python3 -m unittest discover -s tests -v
python3 -m py_compile bin/omarchy-browser-router install.py
omarchy plugin validate .
./bin/omarchy-browser-router snapshot
./bin/omarchy-browser-router test https://example.com
```

The test suite uses temporary directories and mocked browser launches/handler
changes; it never changes the developer's default browser or opens real links.
A JSON `snapshot` includes local browser/profile information: redact it before
sharing. Add translations as `i18n/<Omarchy-language-code>.json` (English fallback).

## Credits

Inspired by Safari's profile URL assignments and [Silo](https://github.com/no-faff/Silo).
Silo's domain/path rules, ask exceptions, and “Always” workflow informed this
implementation. This plugin is independently implemented for Omarchy; no Silo
source code is included.

MIT licensed. Contributions welcome.
