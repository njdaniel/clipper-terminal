# Third-Party Notices

Clipper Terminal is licensed under the GNU AGPLv3 by Whalesback Systems LLC.
It also includes or depends on third-party components that keep their own
licenses. This file lists them.

The project's AGPLv3 license does not replace or override these licenses. When
you redistribute Clipper Terminal, in source or binary form, you must also
follow each component's own terms. In practice that means keeping its
copyright notices, license text, and any NOTICE attribution.

## Components

| Component | Version | License (SPDX) | Copyright / Author | Source | How it is used |
|-----------|---------|----------------|--------------------|--------|----------------|
| _none yet_ | | | | | |

"How it is used" is one of: `vendored` (the code is copied into this
repository), `bundled` (it ships in release artifacts), or `dependency`
(package managers fetch it at build time or run time).

## Full license texts

The full text of every license named above is in [`LICENSES/`](LICENSES/),
named by SPDX identifier (for example `LICENSES/MIT.txt`,
`LICENSES/Apache-2.0.txt`).

A license that needs component-specific text, such as the copyright line in
MIT or BSD, is stored per component as `LICENSES/<component>-<SPDX-ID>.txt`,
with the original copyright notice unchanged.

## Vendored and modified code

Third-party source copied into this repository must:

1. keep every original copyright header and license notice in each file,
2. sit next to its upstream `LICENSE`, `COPYING`, and `NOTICE` files, unchanged,
3. carry a prominent notice of any changes made by Whalesback Systems LLC, with
   the date of the change. Apache-2.0 section 4(b), the GPL family, and
   MPL-2.0 require this. For example:
   `Modified by Whalesback Systems LLC, 2026: <summary of changes>`.

Do not remove or rewrite upstream attribution to apply Whalesback Systems
branding. The branding covers the work as a whole; each third-party component
keeps its own copyright holder's notice.
