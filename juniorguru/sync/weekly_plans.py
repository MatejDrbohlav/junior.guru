import random
import re
from datetime import date, timedelta

import click
from discord import Color, Embed

from juniorguru.cli.sync import main as cli
from juniorguru.lib import discord_task, loggers
from juniorguru.lib.discord_club import (
    DEFAULT_AUTO_ARCHIVE_DURATION,
    ClubClient,
    parse_channel,
)
from juniorguru.lib.mutations import mutating_discord
from juniorguru.models.base import db
from juniorguru.models.club import ClubMessage
from juniorguru.models.wisdom import Wisdom


WEEK_RE = re.compile(
    r"""
        Týden
        \s*
        0?(?P<start_day>\d+)
        (\s*.\s*)?
        0?(?P<start_month>\d+)?
        (\s*.\s*)?
        \s*-\s*
        0?(?P<end_day>\d+)
        (\s*.\s*)?
        0?(?P<end_month>\d+)
        (\s*.\s*)?
        (?P<year>(20)?\d{2})?
    """,
    re.VERBOSE,
)


logger = loggers.from_path(__file__)


@cli.sync_command(dependencies=["club-content", "wisdom"])
@click.option("--channel", "channel_id", default="weekly_plans", type=parse_channel)
@click.option(
    "--today",
    default=lambda: date.today().isoformat(),
    type=date.fromisoformat,
)
def main(channel_id: int, today: date):
    monday = today - timedelta(days=today.weekday())
    thread_messages = ClubMessage.forum_listing(channel_id)
    try:
        last_thread_message = thread_messages[0]
    except IndexError:
        logger.warning("No previous weekly plans found")
    else:
        thread_monday = parse_week(last_thread_message.channel_name, today.year)
        if thread_monday == monday:
            logger.info("Weekly plans already exist")
            return

    with db.connection_context():
        wisdom = random.choice(Wisdom.listing())
    logger.info(f"Selected wisdom by {wisdom.name}: {wisdom.text}")

    discord_task.run(kickoff_weekly_plans, channel_id, wisdom, monday)


async def kickoff_weekly_plans(
    client: ClubClient, channel_id: int, wisdom: Wisdom, monday: date
):
    logger.info("Kicking off the weekly plans")

    name = f"Týden {monday:%-d.%-m.} - {monday + timedelta(days=6):%-d.%-m.}"
    content = (
        "🗓️ Jak jsi na tom? Napiš krátký _update_! Je jedno, jestli jde o učení, práci, nebo vlastní projekt. "
        "Klidně česky, slovensky, nebo si procvič angličtinu 🙂 "
        "\n\n"
        "💭 Proč? Uspořádáš si myšlenky. Uvědomíš si, jak se posunuješ. Dáš do slov, čím teď procházíš. "
        "Všimneš si, s čím zápasí ostatní a třeba uvidíš, že si nějak můžete pomoci. "
        "A někdo když veřejně přislíbí, že něco udělá, tak se k tomu pak spíš dokope. "
        "\n\u200B"  # forces margin between message and the embeds
    )

    template_embed = Embed(
        title="Šablona",
        description=(
            "<:successkid:842730583293558795> Co se mi podařilo minulý týden? / What did I accomplish last week?"
            "\n\n"
            "🛠️ Na čem teď dělám? Čemu se budu věnovat tento týden? / What am I going to focus on this week?"
            "\n\n"
            "🔥 Co mě pálí? Řeším nějaký problém? / Any problems?"
        ),
        color=Color.teal(),
    )
    wisdom_embed = Embed(title="Moudro týdne", description=f"„{wisdom.text}“")
    wisdom_embed.set_footer(text=f"— {wisdom.name}")

    channel = await client.fetch_channel(channel_id)
    with mutating_discord(channel) as proxy:
        await proxy.create_thread(
            name=name,
            content=content,
            embeds=[template_embed, wisdom_embed],
            auto_archive_duration=DEFAULT_AUTO_ARCHIVE_DURATION,
        )


def parse_week(thread_name: str, year: int) -> date:
    year = year or date.today().year
    if match := WEEK_RE.match(thread_name):
        start_day = int(match.group("start_day"))
        month = int(match.group("start_month") or match.group("end_month"))
        year = int(match.group("year") or year)
        start_date = date(year, month, start_day)
        start_monday = start_date - timedelta(days=start_date.weekday())
        return start_monday
    raise ValueError(f"Unable to parse week from {thread_name!r}")
