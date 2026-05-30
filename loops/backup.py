# cattito - A Discord bot about catching cats.
# Copyright (C) 2026 Lia Milenakos & cattito Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import asyncio, datetime, logging, os, traceback

import discord

import config
import shared
import shared

BACKUP_BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backups")


async def do_backup() -> tuple[bool, str]:
    """
    Run pg_dump into backups/DD-MM-YYYY/backup_HH-MM-SS.dump
    Returns (success, message).
    """
    try:
        now = datetime.datetime.now()
        date_folder = now.strftime("%d-%m-%Y")          # UK format: 18-04-2026
        time_suffix = now.strftime("%H-%M-%S")          # e.g. 14-35-02
        folder = os.path.join(BACKUP_BASE_DIR, date_folder)
        os.makedirs(folder, exist_ok=True)

        backup_file = os.path.join(folder, f"backup_{time_suffix}.dump")

        process = await asyncio.create_subprocess_shell(
            f"PGPASSWORD=meow pg_dump -U cat_bot -h 127.0.0.1 -p 5432 -Fc -Z 9 -f {backup_file} cat_bot",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()

        if process.returncode != 0:
            err = stderr.decode().strip()
            logging.warning(f"pg_dump failed: {err}")
            return False, f"pg_dump exited with code {process.returncode}: {err}"

        size = os.path.getsize(backup_file)
        size_str = f"{size / 1024 / 1024:.2f} MB" if size > 1024 * 1024 else f"{size / 1024:.1f} KB"
        msg = f"Backup saved to `backups/{date_folder}/backup_{time_suffix}.dump` ({size_str})"
        logging.info(msg)
        return True, msg

    except Exception as e:
        logging.warning(f"Backup error: {e}")
        return False, f"Backup failed: {traceback.format_exc()}"


async def backup_task(bot, backupchannel_id, exportbackup=None):
    backupchannel = shared.bot.get_partial_messageable(backupchannel_id)

    while True:
        # Wait until midnight UTC so backups happen at the start of each day
        now = datetime.datetime.utcnow()
        tomorrow = (now + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        wait_seconds = (tomorrow - now).total_seconds()
        logging.info(f"Next scheduled backup in {wait_seconds:.0f}s (at midnight UTC)")
        await asyncio.sleep(wait_seconds)

        success, msg = await do_backup()

        try:
            if success:
                await backupchannel.send(f"✅ Daily backup complete: {msg}")
            else:
                await backupchannel.send(f"❌ Daily backup failed: {msg}")
        except Exception as e:
            logging.warning(f"Could not send backup notification: {e}")
