# Board Game Olympics

An invite-only, self-hosted site for an annual board game competition. Organizers build a ballot from the game catalog, players rank their choices privately, and everyone can browse results and past editions after the event.

The interface uses a dark holiday theme and adapts to phones and larger screens.

## Run the app

1. Copy [.env.example](.env.example) to `.env`. Set `DJANGO_ALLOWED_HOSTS` to the public hostname and `DJANGO_SECRET_KEY` to a strong random secret (for example, generate one with `openssl rand -hex 32`). Set `OLYMPICS_ORGANIZER_USERNAME` and `OLYMPICS_ORGANIZER_PASSWORD` for the first organizer. Keep `.env` private; single-quote passwords containing `$` to avoid Compose interpolation.
2. Configure your HTTPS reverse proxy as described below. For BoardGameGeek imports, [register the application](https://boardgamegeek.com/using_the_xml_api) and set `BGG_API_TOKEN`. You can still add games manually without a token.
3. Pull and start the app. It applies database migrations and creates the first organizer automatically. No management commands are needed.

   ```sh
   docker compose pull app
   docker compose up -d
   ```

   The example uses `hematic/board-game-olympics:v0.4.1`. To build from source instead, set `OLYMPICS_IMAGE=board-game-olympics:local` and run `docker build -t board-game-olympics:local .` in place of `docker compose pull app`.

Use the site's HTTPS URL to sign in. The SQLite database lives on the `olympics-data` Compose volume. Keep one app replica and back up the volume before upgrading. Once an active organizer with a password exists, the bootstrap settings are ignored; remove the bootstrap username and password from `.env` and recreate the container to clear them from its environment. Changing those values never resets an existing password or promotes a family account.

Migrations seed an 18-game starter catalog with player counts, playtimes, rules videos, and box-art links where available. Existing matches by title are left untouched. No demo accounts, editions, or ballots are included. Cover images still load from their external hosts. Edits made in a running app stay in its data volume; they do not change the bundled starter catalog.

### HTTPS reverse proxy

Compose publishes `127.0.0.1:8000` by default, for a proxy running directly on the app host. Set `OLYMPICS_PORT` to change the host port. For Traefik or another proxy on a different host, set `OLYMPICS_BIND_ADDRESS` to the app host's private IP and point the proxy at `http://<app-host-private-ip>:<OLYMPICS_PORT>`. No shared Docker network is required. If upgrading from the old shared-network Compose setup, update the proxy upstream instead of using `olympics-web`.

**Restrict the published port to the trusted proxy** using network/firewall rules that apply to Docker-published ports. The backend is HTTP, so use a trusted private network or encrypted tunnel between hosts. Keep HTTPS on the public side, preserve the public `Host`, and have the proxy set `X-Forwarded-Proto: https`; the app trusts that header. Do not expose the backend directly to the internet. Configure login rate limiting at your proxy or edge.

For example, with Caddy running directly on the app host:

```caddyfile
olympics.example.com {
    reverse_proxy 127.0.0.1:8000 {
        header_up X-Forwarded-Proto https
    }
}
```

### Managing accounts

Sign in as the organizer and open **Accounts** to create a username and initial password for each family member. Share their credentials privately. There is no public signup or email requirement. Family members can change their own password; the organizer can reset family passwords from **Accounts**.

**Upgrading from Pocket ID/Tinyauth:** Back up and keep the data volume. Set the organizer bootstrap variables before starting the new container. Remove the old proxy authentication rule and the `POCKET_ID_ISSUER` and `OLYMPICS_ORGANIZER_SUBJECTS` settings. Existing ballots and scores stay in the database. When creating a local account, select that person's old profile under **Link an existing member** to retain their voting history and existing voter roster entries. The old proxy logins no longer work.

## Running an edition

1. Add games manually from **Game catalog**, or search BoardGameGeek if a token is configured. Add YouTube rules links under **Edit game**.
   To show box art, set **Box art image URL** to a direct HTTPS image you have permission to display. The browser loads covers from their source; the app does not download them.
2. Create the year's edition and set the number of lineup slots (8 by default). Add accounts to the voter roster; they don't need to sign in first. Add competitors separately and choose the nominees.
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
