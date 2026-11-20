# Board Game Olympics

An invite-only, self-hosted site for an annual board game competition. The current scaffold includes the app container, Pocket ID identity mapping behind Tinyauth, and the release workflow. The game catalog, voting, scoring, and archive are not implemented yet.

## Run the scaffold

1. Copy [.env.example](.env.example) to `.env`. Set the site's hostname and the Pocket ID issuer, and supply a strong secret (generate one with `python -c 'import secrets; print(secrets.token_urlsafe(64))'`). Set `OLYMPICS_ORGANIZER_SUBJECTS` to a comma-separated list of organizer Pocket ID `sub` values, not usernames or emails.
2. Set up [Pocket ID in Tinyauth](https://tinyauth.app/docs/guides/pocket-id/) and restrict this app to your invited Pocket ID group. Attach the reverse proxy to a Docker network dedicated to this app, name that network in `.env`, and forward the authenticated `Remote-Sub` header. See the example below.
3. Build the image locally until the first release is published:

   ```sh
   docker build -t board-game-olympics:local .
   docker compose run --rm app python manage.py migrate --noinput
   docker compose up -d
   ```

Use the site's HTTPS URL to sign in. The SQLite database lives on the `olympics-data` Compose volume. Keep one app replica and back up the volume before upgrading. Run the migration command with the new image before starting it.

### Reverse proxy boundary

**Only the trusted proxy should be able to connect to the app container.** Do not publish the app's port or put untrusted containers on its network. The app expects the proxy to remove client-supplied identity headers and get `Remote-Sub` exclusively from a successful Tinyauth authorization response. Do not configure a fallback provider that can issue identifiers for this app. If `Remote-Sub` is missing, the app denies access.

For example, with Caddy serving HTTPS and linked to both the app and Tinyauth:

```caddyfile
olympics.example.com {
    route {
        request_header -Remote-Sub
        request_header -Remote_Sub
        forward_auth tinyauth:3000 {
            uri /api/auth/caddy
            copy_headers Remote-Sub
        }
        reverse_proxy olympics-web:8000 {
            header_up X-Forwarded-Proto https
        }
    }
}
```

Apply the invite-only Tinyauth access policy to this hostname, and check that invited accounts get the member page while other accounts are denied. The app's unauthenticated `/healthz/` is for the internal container probe; the example routes external health requests through Tinyauth too.

## Releases

The [container workflow](.github/workflows/container.yml) runs Django tests and smoke-tests the image. Publishing a non-prerelease GitHub release tagged `vX.Y.Z` pushes the same tested Linux AMD64 image to `hematic/board-game-olympics:vX.Y.Z`. Before publishing, create that repository on Docker Hub and set the `DOCKERHUB_TOKEN` GitHub Actions secret to a Docker Hub access token with write access. For deployment, set `OLYMPICS_IMAGE` to the versioned Docker Hub image instead of the local build.
