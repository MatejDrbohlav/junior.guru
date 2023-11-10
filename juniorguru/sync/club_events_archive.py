from pathlib import Path
from discord import Embed, File, ui
from juniorguru.lib import loggers
from juniorguru.cli.sync import main as cli
from juniorguru.lib import discord_sync, loggers
from juniorguru.lib.discord_club import ClubChannelID, ClubClient
from juniorguru.lib.mutations import mutating_discord
from juniorguru.models.event import Event
from juniorguru.models.base import db


IMAGES_DIR = Path("juniorguru/images")


logger = loggers.from_path(__file__)


@cli.sync_command(dependencies=["club-content", "events"])
def main():
    discord_sync.run(recreate_archive)


@db.connection_context()
async def recreate_archive(client: ClubClient):
    events = list(Event.archive_listing())
    channel = await client.fetch_channel(ClubChannelID.EVENTS_ARCHIVE)
    with mutating_discord(channel) as proxy:
        await proxy.purge(limit=None)
    with mutating_discord(channel) as proxy:
        await proxy.send(
            "# Záznamy klubových akcí\n\n"
            "Tady najdeš všechny přednášky, které se konaly v klubu. "
            "Videa nejsou „veřejná”, ale pokud chceš odkaz poslat kamarádovi mimo klub, můžeš. "
        , suppress=True)
    for event in logger.progress(events, chunk_size=10):
        logger.info(f"Posting {event.title!r}")
        embed = Embed(
            title=event.title,
            url=event.url,
            timestamp=event.start_at_prg,
        )
        embed.set_author(
            name=event.bio_name,
        )
        embed.set_thumbnail(
            url=f"attachment://{Path(event.avatar_path).name}"
        )
        file = File(IMAGES_DIR / event.avatar_path)
        view = await create_view(event)

        with mutating_discord(channel) as proxy:
            await proxy.send(embed=embed, file=file, view=view)


async def create_view(event: Event) -> ui.View:  # View's __init__ touches the event loop
    return ui.View(
        ui.Button(
            emoji="<:youtube:976200175490060299>",
            label="Záznam",
            url=event.recording_url if event.recording_url else None,
            disabled=not event.recording_url,
        )
    )
