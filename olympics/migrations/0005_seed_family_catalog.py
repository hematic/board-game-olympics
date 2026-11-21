from django.db import migrations


DESCRIPTIONS = {
    "Azul": (
        "Take turns choosing colored tiles from shared suppliers, then arrange them on your board "
        "to decorate the palace. Score for the tiles you place, with bonuses for patterns and "
        "completed sets. Leftover tiles cost you points. The highest score wins."
    ),
    "Splendor": (
        "Play a Renaissance gem merchant competing for prestige. Gather gem tokens and spend them "
        "on development cards representing mines, trade routes, and shops. Your investments make "
        "later purchases cheaper and can attract nobles, whose visits earn extra prestige."
    ),
}

GAMES = (
    ("Splendor", 2014, 2, 4, 30, "2A0CQ0xsrv0", "https://cf.geekdo-images.com/vNFe4JkhKAERzi4T0Ntwpw__imagepage/img/JXnPzdgTeDkRrxESA86gnCw4Zws=/fit-in/900x600/filters:no_upscale():strip_icc()/pic8234167.png",
     "Collect gem tokens and buy development cards that discount future purchases. Earn enough prestige to trigger the final round.",
     "https://boardgamegeek.com/boardgame/148228/splendor"),
    ("Azul", 2017, 2, 4, None, "byHjDCxF5WU", "https://tse4.mm.bing.net/th/id/OIP.42vtpRGDdfDZ2a9f2n9Q4QHaEK?r=0&rs=1&pid=ImgDetMain&o=7&rm=3",
     "Listed time: 30–45 minutes.",
     "https://azulthegame.com/"),
    ("Guillotine", 1998, 2, 5, 30, "ft3Wbp5XgyI", "https://cf.geekdo-images.com/gDbDLBdIZfkU9rc8rK4g2g__imagepage/img/m-PjfXTlXtjmMvQ9fWDJSBTjKM0=/fit-in/900x600/filters:no_upscale():strip_icc()/pic9528692.jpg",
     "Rearrange a line of nobles with action cards, collect the front card, and total points after three rounds.",
     "https://boardgamegeek.com/boardgame/116/guillotine"),
    ("Mexican Train Dominoes", None, 2, 8, None, "jxeIR8HCSYI", "https://cf.geekdo-images.com/VFt5NUiI65V-pYP-e7uNeg__imagepage/img/Rc143ptLwBEZGjZErKb5uKh_9ms=/fit-in/900x600/filters:no_upscale():strip_icc()/pic117397.jpg",
     "Match dominoes onto personal trains or a shared train and aim for the lowest total of leftover pips. The 2–8 count is for the Pressman double-12 set. Allow roughly 20 minutes for a single round; full sessions vary with the number of rounds. Check your set’s rules for doubles and opening turns.",
     "https://manualzz.com/doc/65690809/pressman-dominoes--mexican-train-dominoes-instruction"),
    ("Sushi Go Party!", 2016, 2, 8, 30, "FnnT4nlAPuM", "https://cf.geekdo-images.com/2f9uTicUSXkdPp2Yks6zFw__imagepage/img/BeU9AH0pcKCbXi7ViuC87zS1WfI=/fit-in/900x600/filters:no_upscale():strip_icc()/pic5885689.jpg",
     "Build a custom menu, then pick and pass cards to assemble scoring combos over three rounds. This is the Party version, not the original Sushi Go!",
     "https://gamewright.com/product/Sushi-Go-Party"),
    ("Tiny Towns", 2019, 1, 6, None, "yF--uYWp0zw", "https://cf.geekdo-images.com/aE1EoOzr530gQin8bj8QDA__imagepage/img/m9dEp_Ze7eUFxXMdlpjHFMuml5E=/fit-in/900x600/filters:no_upscale():strip_icc()/pic4460401.jpg",
     "Everyone places the resource called by the master builder, then turns patterns on a small grid into buildings. Listed time: 45–60 minutes. One player is the solo mode.",
     "https://boardgamegeek.com/boardgame/265736/tiny-towns"),
    ("Wingspan", 2019, 1, 5, None, "lgDgcLI2B0U", "https://cf.geekdo-images.com/yLZJCVLlIx4c7eJEWUNJ7w__imagepage/img/uIjeoKgHMcRtzRSR4MoUYl3nXxs=/fit-in/900x600/filters:no_upscale():strip_icc()/pic4458123.jpg",
     "Attract birds to three habitats and build chains of powers for food, eggs, and cards. Listed time: 40–70 minutes; solo uses Automa.",
     "https://www.boardgamevideo.com/videos/wingspan-how-to-play-lgDgcLI2B0U"),
    ("King of Tokyo", 2011, 2, 6, 30, "DjfsX847nb0", "https://cf.geekdo-images.com/m_RzXpHURC0_xLkvRSR_sw__imagepage/img/oSNvtltDuWj3LP74IEFj8Ov2B0k=/fit-in/900x600/filters:no_upscale():strip_icc()/pic3043734.jpg",
     "Roll and reroll dice to attack, heal, gain energy, or score. Win by reaching 20 points or being the last monster standing.",
     "https://boardgamegeek.com/boardgame/70323/king-of-tokyo"),
    ("Yahtzee", 1956, 1, 10, 30, "sQM7sN4NPz8", "https://cf.geekdo-images.com/dp-pJkUemCjhrwi9QItrPA__imagepage/img/o73ZDMuyE1V8Dh6jgvoyOaTFzRg=/fit-in/900x600/filters:no_upscale():strip_icc()/pic378237.jpg",
     "Roll five dice up to three times per turn and fill one of 13 scoring boxes. Hasbro’s rules say 1 or more; 10 is a catalog reference, not a rules cap. Playing time grows with the group.",
     "https://www.hasbro.com/common/instruct/yahtzee.pdf"),
    ("Sheriff of Nottingham", 2014, 3, 5, 60, "ofZS29XArzM", "https://cf.geekdo-images.com/BBgLFKUzr6tcKtlIM2JSFw__imagepage/img/_3bSh9NeLxkL23XBruNlzxk5QCM=/fit-in/900x600/filters:no_upscale():strip_icc()/pic2075830.jpg",
     "Merchants declare goods while a rotating sheriff decides whether to inspect their bags. These details and the tutorial cover the original; 2nd Edition supports 3–6 players and includes additional rules.",
     "https://boardgamegeek.com/boardgame/157969/sheriff-of-nottingham"),
    ("7 Wonders", None, 3, 7, 30, "QVLUu7qkLWI", "https://gamenightblog.com/wp-content/uploads/2021/03/7-wonders-box.jpg",
     "Draft cards simultaneously over three ages to develop your city and wonder. The linked tutorial covers Second Edition; check your box’s rules if you own the original.",
     "https://www.rprod.com/index.php/en/games/7-wonders"),
    ("Heat: Pedal to the Metal", 2022, 1, 6, None, "Ychy0Tgegjk", "https://cf.geekdo-images.com/-vOrd4bOspibyohYExLqWg__imagepage/img/k4uPIqjYuWBzofFiCyjSWN6KJow=/fit-in/900x600/filters:no_upscale():strip_icc()/pic6940449.png",
     "Manage speed, gears, and engine heat while slipstreaming and negotiating corners. Listed time: 30–60 minutes for the base game; the championship spans multiple races.",
     "https://boardgamegeek.com/boardgame/366013/heat-pedal-to-the-metal"),
    ("Plunder", None, 2, 6, None, "QrJXLhFo79s", "https://cf.geekdo-images.com/e5xwvJIQVWh7Pt2swQmloA__imagepage/img/N5xTMa8vPdhnvGAg5nWRJZ-MDFE=/fit-in/900x600/filters:no_upscale():strip_icc()/pic5243200.jpg",
     "Assumed to be Plunder: A Pirate’s Life by Lost Boy Entertainment. Build and upgrade ships, conquer islands, and race to ten Plunder Points. Listed time: 40–120 minutes.",
     "https://boardgamegeek.com/boardgame/281094/plunder-a-pirates-life"),
    ("Carcassonne", 2000, 2, 5, None, "R1qh-lhxy9s", "https://i5.walmartimages.com/asr/9e79139e-19e6-4bb8-9be8-df46bd215045.90cccd3e09715113e35b91f391ea695b.jpeg?odnHeight=612&odnWidth=612&odnBg=FFFFFF",
     "Place landscape tiles and deploy meeples to score roads, cities, monasteries, and farms. Allow about 30–45 minutes for the base game; expansions may change timing or capacity.",
     "https://boardgamegeek.com/boardgame/822/carcassonne"),
    ("Ticket to Ride: Europe", 2005, 2, 5, None, "x1__CNpTreg", "https://cf.geekdo-images.com/EQJZDO1Jq8KL-HxmWLwL-Q__imagepage/img/EQkXYYRM_4xP7XFtUFqzl2egipI=/fit-in/900x600/filters:no_upscale():strip_icc()/pic9580918.jpg",
     "Collect train cards, claim routes and complete destination tickets. Europe adds tunnels, ferries, and stations; the linked guide focuses on setup and those additions. Publisher lists 30–60 minutes and links the full rules.",
     "https://www.daysofwonder.com/game/ticket-to-ride-europe/"),
    ("Scattergories", 1988, 2, 6, 30, "WgRm_auxt_w", "https://cf.geekdo-images.com/eIL4hvMb7ZPgizc7BZOh-g__imagepage/img/-6dsLegxiO4En99P1IRSSYc1Svs=/fit-in/900x600/filters:no_upscale():strip_icc()/pic4994410.jpg",
     "Race the timer to write answers for categories using one starting letter. Answers duplicated by other players do not score. This guide is for the classic boxed game, not the card game.",
     "https://boardgamegeek.com/boardgame/2381/scattergories"),
    ("Play Nine", None, 2, 6, 45, "eKdn5coKmsw", "https://cf.geekdo-images.com/6fP6ySSuDKEe0Hq8WSAbMQ__imagepage/img/D9kQRsiAVmftT2qU4sYo0osmQFs=/fit-in/900x600/filters:no_upscale():strip_icc()/pic9203685.jpg",
     "Draw and swap cards to lower your stroke count. Matching cards in a column usually cancel out; the lowest total after nine holes wins. Ages 8+.\n\nOfficial rules: https://playnine.com/pages/how-to-play",
     "https://boardgamegeek.com/boardgame/22950/play-nine"),
    ("Love Letter", 2019, 2, 6, 20, "RiQ2To5KWJM", "https://cf.geekdo-images.com/V7WQjhAh0AatPXTYOrXtCQ__imagepage/img/aY1TC_Wu1Lp8suwWdcTx8_hU-6U=/fit-in/900x600/filters:no_upscale():strip_icc()/pic4766499.png",
     "Draw a card, play one, and use its ability to deduce or eliminate rivals. Win rounds to collect favor tokens. This is the 21-card Z-Man edition for 2–6 players, ages 10+. The original 16-card edition seats only up to four.",
     "https://www.zmangames.com/game/love-letter/"),
)


def seed_catalog(apps, schema_editor):
    games = apps.get_model("olympics", "Game").objects.using(schema_editor.connection.alias)
    for title, year, min_players, max_players, minutes, video, cover, notes, reference in GAMES:
        if not games.filter(title__iexact=title).exists():
            games.create(
                title=title,
                year=year,
                min_players=min_players,
                max_players=max_players,
                playing_time=minutes,
                video_url=f"https://www.youtube.com/watch?v={video}",
                cover_url=cover,
                description=DESCRIPTIONS.get(title, ""),
                notes=f"{notes}\n\nReference: {reference}",
            )


class Migration(migrations.Migration):
    dependencies = [("olympics", "0004_game_cover_url")]

    operations = [
        # Don't delete games on rollback: editions may already use them.
        migrations.RunPython(seed_catalog, migrations.RunPython.noop),
    ]
