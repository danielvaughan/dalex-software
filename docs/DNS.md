# DNS for dalex-software.co.uk

The site is served by GitHub Pages from `danielvaughan/dalex-software`. GitHub only issues the
HTTPS certificate once the domain's DNS points at GitHub. Add these records at the registrar or
DNS host for `dalex-software.co.uk` (remove any other A, AAAA or CNAME records on the same names,
such as a registrar parking page).

## Records

Apex (`dalex-software.co.uk`, often written `@`):

| Type | Name | Value |
| --- | --- | --- |
| A | @ | 185.199.108.153 |
| A | @ | 185.199.109.153 |
| A | @ | 185.199.110.153 |
| A | @ | 185.199.111.153 |
| AAAA | @ | 2606:50c0:8000::153 |
| AAAA | @ | 2606:50c0:8001::153 |
| AAAA | @ | 2606:50c0:8002::153 |
| AAAA | @ | 2606:50c0:8003::153 |

`www` subdomain:

| Type | Name | Value |
| --- | --- | --- |
| CNAME | www | danielvaughan.github.io |

GitHub redirects `www.dalex-software.co.uk` to the apex once both resolve. Do not use wildcard
records (`*.dalex-software.co.uk`): they let anyone's Pages site claim a subdomain.

## Check the records

```sh
dig +short dalex-software.co.uk A
dig +short dalex-software.co.uk AAAA
dig +short www.dalex-software.co.uk CNAME
```

The first two should list exactly the four addresses above; the third `danielvaughan.github.io.`.
Propagation usually takes minutes, occasionally up to a day.

## Turn on HTTPS

The repository's Pages settings already name the custom domain (`CNAME` holds
`dalex-software.co.uk`). Once the records resolve, GitHub runs its DNS check and requests a
certificate; this can take up to an hour.

1. Open <https://github.com/danielvaughan/dalex-software/settings/pages>.
2. Wait until the page says the DNS check succeeded and the certificate is issued.
3. Tick **Enforce HTTPS**. Or from a shell:

   ```sh
   gh api -X PUT repos/danielvaughan/dalex-software/pages -F https_enforced=true
   ```

If the custom domain field is ever empty, set it again with
`gh api -X PUT repos/danielvaughan/dalex-software/pages -f cname=dalex-software.co.uk`.

## Verify the domain (prevents takeover)

Verifying the domain on the GitHub account stops any other account publishing a Pages site on it
or its subdomains, even if the repository's Pages settings are later removed.

1. Open <https://github.com/settings/pages> (profile **Settings → Pages**).
2. **Add a domain**, enter `dalex-software.co.uk`.
3. GitHub shows a TXT record, named like `_github-pages-challenge-danielvaughan.dalex-software.co.uk`
   with a random value. Add that TXT record at the DNS host.
4. Check it with `dig +short TXT _github-pages-challenge-danielvaughan.dalex-software.co.uk`, then
   press **Verify**. Keep the TXT record in place afterwards.

## Before DNS is set

Until the records exist, the custom domain does not resolve and GitHub's default Pages address
redirects to it, so the site is not reachable from a browser. Every page links relatively, so the
build itself works under any path.
