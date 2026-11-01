# Changelog

## 0.1.2

- Save valid bracketed IPv6 rules from the picker's Always action; accept bare
  IPv6 rules saved by older versions without breaking unrelated links.
- Keep international domains distinct with non-transitional UTS #46 handling.
  Adds the `python-idna` runtime dependency, checked by the installer.
- Resolve literal/encoded dot segments and HTTP backslash separators before
  matching path rules, preventing links from selecting the wrong profile.
- Queue URLs and open the picker when the saved system browser is unavailable.
- Tolerate queued links disappearing during concurrent picker refreshes.
- Check the rule limit before launching or removing a link via Always.

## 0.1.1

- Fix the router desktop entry so Omarchy recognizes its executable instead of
  skipping it and falling back to another installed browser.

## 0.1.0

- Initial browser/profile discovery, URL rules, native settings and picker.
