# Contributing to Clipper Terminal

Thank you for your interest in Clipper Terminal, a product of Whalesback
Systems LLC.

## Licensing of contributions

Clipper Terminal is licensed under the GNU AGPLv3 or later. Whalesback
Systems LLC intends to keep the ability to offer Clipper Terminal under other
license terms as well (dual licensing).

### Contributor License Agreement (required, pending adoption)

Every external contribution will need a signed Contributor License Agreement
(CLA) before it can be accepted. The agreement is going through legal review
and has not been adopted yet.

**Until the CLA is adopted, no external contributions will be merged.** You are
welcome to open issues and discussions. Please wait for the CLA before opening
pull requests that contain code or documentation you want merged. This file
will link to the agreement and explain how to sign it once it is available.

The CLA grants rights to Whalesback Systems LLC only. The public release of
Clipper Terminal stays under the AGPLv3 or later, and third-party code stays
under its own licenses.

### Developer Certificate of Origin

Also sign off every commit to certify the
[Developer Certificate of Origin](https://developercertificate.org/):

```
git commit -s
```

## Source file headers

New source files should start with an SPDX header:

```
// SPDX-FileCopyrightText: 2026 Whalesback Systems LLC
// SPDX-License-Identifier: AGPL-3.0-or-later
```

Never change the header of a file that came from a third party. Keep its
original copyright and license lines. If you modify it, add a line saying so,
as described in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

## Adding or updating a third-party dependency

Do all of the following in the same pull request that adds the dependency:

1. **Check compatibility.** The dependency's license must be compatible with
   AGPLv3 for the way it is used:
   - **Generally compatible:** MIT, BSD-2-Clause, BSD-3-Clause, ISC, Zlib,
     Apache-2.0, MPL-2.0, LGPL-2.1-or-later, LGPL-3.0, GPL-3.0, AGPL-3.0,
     Unlicense, CC0-1.0.
   - **Incompatible or needs review:** GPL-2.0-only, CDDL, EPL-1.0, SSPL,
     BUSL, "Commons Clause", any non-commercial or field-of-use restriction,
     proprietary, or no license at all. Do not add these without written
     sign-off from Whalesback Systems LLC.
2. **Record it.** Add a row to [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
3. **Include the license text.** Add the full license text to
   [`LICENSES/`](LICENSES/) if it is not already there. For MIT, BSD, and
   similar licenses, keep the component's own copyright line.
4. **Carry forward NOTICE files.** If the component is Apache-2.0 and has a
   `NOTICE` file, copy its attribution content into the root
   [`NOTICE`](NOTICE).
5. **Keep upstream attribution.** Never remove, shorten, or rebrand upstream
   copyright notices. Whalesback Systems branding applies to the project as a
   whole, not to third-party code.

## Releases

Every binary or packaged release must include `LICENSE`, `NOTICE`,
`THIRD_PARTY_NOTICES.md`, and the `LICENSES/` directory. It must also give
recipients a way to get the Corresponding Source, as AGPLv3 sections 6 and 13
require.
