# Board Game Olympics

An invite-only, self-hosted site for an annual board game competition. Organizers build a ballot from the game catalog, players rank their choices privately, and everyone can browse results and past editions after the event.

The interface uses a dark holiday theme and adapts to phones and larger screens.

## Run the app

1. Copy [.env.example](.env.example) to `.env`. Set the site's hostname and the Pocket ID issuer, and supply a strong secret (generate one with `python -c 'import secrets; print(secrets.token_urlsafe(64))'`). Set `OLYMPICS_ORGANIZER_SUBJECTS` to a comma-separated list of organizer Pocket ID `sub` values, not usernames or emails.
2. Set up [Pocket ID in Tinyauth](https://tinyauth.app/docs/guides/pocket-id/) and restrict this app to your invited Pocket ID group. Attach the reverse proxy to a Docker network dedicated to this app (`docker network create olympics-proxy` with the example defaults), name that network in `.env`, and forward the authenticated `Remote-Sub` and `Remote-Name` headers. See the example below. For BoardGameGeek imports, [register the application](https://boardgamegeek.com/using_the_xml_api) and set `BGG_API_TOKEN`. You can still add games manually without a token.
3. Set `OLYMPICS_IMAGE=hematic/board-game-olympics:v0.2.0` in `.env`, then pull and start the published image:

   ```sh
   docker compose pull app
   docker compose run --rm app python manage.py migrate --noinput
   docker compose up -d
   ```

   To build from source instead, leave `OLYMPICS_IMAGE` unset and run `docker build -t board-game-olympics:local .` in place of `docker compose pull app`.

Use the site's HTTPS URL to sign in. The SQLite database lives on the `olympics-data` Compose volume. Keep one app replica and back up the volume before upgrading. Run the migration command with the new image before starting it.

Migrations seed an 18-game starter catalog with player counts, playtimes, rules videos, and box-art links where available. Existing matches by title are left untouched. No demo accounts, editions, or ballots are included. Cover images still load from their external hosts. Edits made in a running app stay in its data volume; they do not change the bundled starter catalog.

### Reverse proxy boundary

**Only the trusted proxy should be able to connect to the app container.** Do not publish the app's port or put untrusted containers on its network. The app expects the proxy to remove client-supplied identity headers and get `Remote-Sub` exclusively from a successful Tinyauth authorization response. Do not configure a fallback provider that can issue identifiers for this app. If `Remote-Sub` is missing, the app denies access.

For example, with Caddy serving HTTPS and linked to both the app and Tinyauth:

```caddyfile
olympics.example.com {
    route {
        request_header -Remote-Sub
        request_header -Remote_Sub
        request_header -Remote-Name
        request_header -Remote_Name
        forward_auth tinyauth:3000 {
            uri /api/auth/caddy
            copy_headers Remote-Sub Remote-Name
        }
        reverse_proxy olympics-web:8000 {
            header_up X-Forwarded-Proto https
        }
    }
}
```

Apply the invite-only Tinyauth access policy to this hostname, and check that invited accounts get the member page while other accounts are denied. The app's unauthenticated `/healthz/` is for the internal container probe; the example routes external health requests through Tinyauth too.

## Running an edition

1. Add games manually from **Game catalog**, or search BoardGameGeek if a token is configured. Add YouTube rules links under **Edit game**.
   To show box art, set **Box art image URL** to a direct HTTPS image you have permission to display. The browser loads covers from their source; the app does not download them.
2. Create the year's edition and set the number of lineup slots (8 by default). Invitees must sign in once before you can add them to the voter roster. Add competitors separately and choose the nominees.
3. Open voting. Voters assign points next to each game on the edition page and select **Save ballot**. With the default 8 slots and at least 8 nominees, rank eight distinct games: give 8 points to your favorite, 7 to your next choice, down to 1 for your last pick. Each point value is available for only one game at a time; set a game to **Unranked** to free up its points. The top eight games make the lineup. With fewer nominees than slots, rank all nominees starting at the slot count. Voters can replace their ballot before close. Organizers only see turnout, not ballots or interim totals. Database and backup operators are trusted and can read stored ballots.
4. Close voting to reveal named ballots to all signed-in members. The app picks the highest totals, comparing counts at each rank in order when tied. If a tie still crosses the cutoff, choose among just the tied games and record a reason.
5. Set scoring before each game, then record placements. Shared placements get the same full award, and the next occupied place is skipped (1st, 1st, 3rd). Standings update automatically. Finalize the edition when play finishes.

To enter a past Olympics, check **Historical** when creating the edition. Enter its known lineup, competitors, placements, and voting records without opening a new vote. Leave missing results or votes blank and note any partial records.

## Back up and restore

The database contains identities, ballots, and complete results. Protect the backup and store an encrypted copy off-host. With the app running, take a consistent snapshot using SQLite's backup API:

```sh
umask 077
docker compose exec -T app python -c 'import sqlite3; source = sqlite3.connect("file:/data/olympics.sqlite3?mode=ro", uri=True); target = sqlite3.connect("/tmp/olympics-backup.sqlite3"); source.backup(target); target.close(); source.close()'
docker compose exec -T app cat /tmp/olympics-backup.sqlite3 > olympics-backup.sqlite3
docker compose exec -T app rm /tmp/olympics-backup.sqlite3
```

Rehearse a restore into a fresh volume using a separate Compose project. The backup must exist and be nonempty before you run this:

```sh
test -s olympics-backup.sqlite3 && docker compose --project-name olympics-restore run --rm -T --no-deps app sh -c 'set -C; cat > /data/olympics.sqlite3' < olympics-backup.sqlite3
docker compose --project-name olympics-restore run --rm --no-deps app python -c 'import sqlite3; db = sqlite3.connect("file:/data/olympics.sqlite3?mode=ro", uri=True); assert db.execute("PRAGMA integrity_check").fetchone() == ("ok",); print(db.execute("SELECT year, phase FROM olympics_edition ORDER BY year").fetchall())'
```

## Releases

The [container workflow](.github/workflows/container.yml) runs Django tests and smoke-tests the image. Publishing a non-prerelease GitHub release tagged `vX.Y.Z` pushes the same tested Linux AMD64 image to `hematic/board-game-olympics:vX.Y.Z`. Before publishing, create that repository on Docker Hub and set the `DOCKERHUB_TOKEN` GitHub Actions secret to a Docker Hub access token with write access. For deployment, set `OLYMPICS_IMAGE` to the versioned Docker Hub image instead of the local build.
