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

from typing import Optional
import asyncio, logging, math, random, time
from collections import Counter
import discord
from discord import ButtonStyle
from discord.ui import (
    Button, LayoutView, Modal, TextInput, TextDisplay, Container,
    Section, Thumbnail, ActionRow,
)
import shared
from shared import casino_lock, slots_lock
from constants import cattypes, type_dict, VIEW_TIMEOUT
from core.colors import Colors
from core.utils import get_emoji, do_funny
from database import Profile
from achievements import achemb, progress
from systems.anticheat import _ac_record_casino, _ac_send_report


# ───────────────────────────────────────────────────────────────────────
#  Card helpers for Blackjack
# ───────────────────────────────────────────────────────────────────────

_CARD_SUITS  = ["♠️", "♥️", "♦️", "♣️"]
_CARD_RANKS  = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]

def _build_deck():
    deck = [(rank, suit) for suit in _CARD_SUITS for rank in _CARD_RANKS]
    random.shuffle(deck)
    return deck

def _card_value(rank: str) -> int:
    if rank in ("J", "Q", "K"):
        return 10
    if rank == "A":
        return 11
    return int(rank)

def _hand_value(hand: list) -> int:
    total = sum(_card_value(r) for r, _ in hand)
    aces  = sum(1 for r, _ in hand if r == "A")
    while total > 21 and aces:
        total -= 10
        aces  -= 1
    return total

def _fmt_hand(hand: list, hide_second: bool = False) -> str:
    if hide_second and len(hand) >= 2:
        return f"`{hand[0][0]}{hand[0][1]}` `??`"
    return " ".join(f"`{r}{s}`" for r, s in hand)

def _hl_earned(streak: int) -> int:
    """Triangle-number payout for Higher/Lower: sum of 1..streak."""
    return streak * (streak + 1) // 2


# ───────────────────────────────────────────────────────────────────────
#  Catsino Spin constants
# ───────────────────────────────────────────────────────────────────────

# Cost: 5 Fine cats.
# Each prize is (cat_type, amount).  cat_type=None means nothing.
# Fine coin prizes give the house edge; cat prizes are bonus rewards weighted
# inversely to rarity (higher type_dict weight → more likely to appear).
_SPIN_PRIZES: list[tuple[str | None, int]] = [
    (None,         0),  # nothing
    ("Fine",       3),  # small loss
    ("Fine",       5),  # break-even
    ("Fine",       8),  # small win
    ("Fine",      15),  # Fine jackpot
    # ── one of every cat type ──────────────────────────────────────────────
    ("Fine",       1),
    ("Snacc",      1),
    ("Nice",       1),
    ("Good",       1),
    ("Rare",       1),
    ("Wild",       1),
    ("Kittuh",     1),
    ("Baby",       1),
    ("Princess",   1),
    ("Epic",       1),
    ("Sus",        1),
    ("Water",      1),
    ("Brave",      1),
    ("Unknown",    1),
    ("Rickroll",   1),
    ("Reverse",    1),
    ("Superior",   1),
    ("Trash",      1),
    ("Legendary",  1),
    ("Bloodmoon",  1),
    ("Mythic",     1),
    ("8bit",       1),
    ("Corrupt",    1),
    ("Professor",  1),
    ("Rainbow",    1),
    ("Divine",     1),
    ("Space",      1),
    ("Real",       1),
    ("Ultimate",   1),
    ("eGirl",      1),
    ("eBoy",       1),
    ("Angel",      1),
]
# Weights for coin prizes are fixed; cat-type prizes scale with type_dict rarity
# (common cats = higher weight, ultra-rare cats = lower weight).
# Cat-prize weights are type_dict[type] / 20 so the whole bucket stays balanced.
_SPIN_WEIGHTS = [
    20,    # nothing
    25,    # 3 Fine
    22,    # 5 Fine
    12,    # 8 Fine
    6,     # 15 Fine jackpot
    # cat prizes (type_dict value / 20, floored at 0.05)
    *(max(v / 20, 0.05) for v in list(type_dict.values())),
]
_SPIN_LABELS: dict[tuple[str | None, int], str] = {
    (None,        0): "😿 Nothing",
    ("Fine",      3): "😺 3 Fine cats",
    ("Fine",      5): "😸 5 Fine cats (break-even!)",
    ("Fine",      8): "🎉 8 Fine cats",
    ("Fine",     15): "🏆 15 Fine cats – JACKPOT!",
}


# ───────────────────────────────────────────────────────────────────────
#  Scratch Card constants
# ───────────────────────────────────────────────────────────────────────

_SCRATCH_SYMBOLS = ["🍒", "🍋", "🍇", "⭐", "🔔", "💎", "🐱"]
_SCRATCH_PRIZES  = {"🍒": 2, "🍋": 4, "🍇": 6, "⭐": 10, "🔔": 15, "💎": 25, "🐱": 50}
_SCRATCH_WEIGHTS = [30, 22, 18, 13, 9, 6, 2]


# ───────────────────────────────────────────────────────────────────────
#  /casino  —  multi-game lobby
# ───────────────────────────────────────────────────────────────────────

@shared.bot.tree.command(description="Welcome to the Catsino! Pick a game and try your luck 🎰")
async def casino(message: discord.Interaction):
    if message.user.id + message.guild.id in casino_lock:
        await message.response.send_message(
            "You're already inside the Catsino! Finish your current game first.",
            ephemeral=True,
        )
        await achemb(message, "paradoxical_gambler", "followup")
        return

    profile   = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
    total_sum = await Profile.sum("gambles", "gambles > 0")

    embed = discord.Embed(
        title="🎰 Welcome to the Catsino!",
        description=(
            f"You've visited **{profile.gambles:,}** times.  "
            f"All players combined: **{total_sum:,}** visits.\n\n"
            "**Pick a game below:**\n\n"
            f"🎲 **Catsino Spin** — costs 5 {get_emoji('finecat')} Fine cats · honest odds shown\n"
            "🃏 **Blackjack** — beat the dealer · bet Fine cats\n"
            "🪙 **Coin Flip** — 50/50 double-or-nothing · bet Fine cats\n"
            "🔢 **Higher/Lower** — streak multiplier guessing game · free to play\n"
            "🎟️ **Scratch Card** — costs 3 Fine cats · instant prizes\n"
        ),
        color=Colors.maroon,
    )

    class _GameSelect(discord.ui.Select):
        def __init__(self):
            options = [
                discord.SelectOption(label="Catsino Spin",  value="spin",    emoji="🎲",
                                     description="Pay 5 Fine cats, win up to 15"),
                discord.SelectOption(label="Blackjack",     value="bj",      emoji="🃏",
                                     description="Classic card game vs the dealer"),
                discord.SelectOption(label="Coin Flip",     value="coin",    emoji="🪙",
                                     description="50/50 double-or-nothing"),
                discord.SelectOption(label="Higher/Lower",  value="hl",      emoji="🔢",
                                     description="Free to play, streak multiplier rewards"),
                discord.SelectOption(label="Scratch Card",  value="scratch", emoji="🎟️",
                                     description="Pay 3 Fine cats, reveal instant prizes"),
            ]
            super().__init__(placeholder="Choose a game…", options=options,
                             min_values=1, max_values=1, custom_id="casino_game_select")

        async def callback(self, interaction: discord.Interaction):
            if interaction.user.id != message.user.id:
                await do_funny(interaction)
                return
            choice = self.values[0]
            if choice == "spin":
                await _casino_spin(interaction, message, profile)
            elif choice == "bj":
                await _casino_blackjack_start(interaction, message, profile)
            elif choice == "coin":
                await _casino_coinflip_start(interaction, message, profile)
            elif choice == "hl":
                await _casino_higher_lower(interaction, message, profile)
            elif choice == "scratch":
                await _casino_scratch(interaction, message, profile)

    view = LayoutView(timeout=VIEW_TIMEOUT)
    view.add_item(_GameSelect())
    await message.response.send_message(embed=embed, view=view)


# ───────────────────────────────────────────────────────────────────────
#  Shared lobby helper  (Back-to-lobby buttons call this)
# ───────────────────────────────────────────────────────────────────────

async def _casino_lobby(interaction: discord.Interaction,
                        message:     discord.Interaction,
                        profile):
    await profile.refresh_from_db()
    total_sum = await Profile.sum("gambles", "gambles > 0")

    embed = discord.Embed(
        title="🎰 The Catsino – Lobby",
        description=(
            f"You've visited **{profile.gambles:,}** times.  "
            f"All players combined: **{total_sum:,}** visits.\n\n"
            "**Pick a game:**\n\n"
            f"🎲 **Catsino Spin** — costs 5 {get_emoji('finecat')} Fine cats · house edge ~9%\n"
            "🃏 **Blackjack** — beat the dealer · bet Fine cats\n"
            "🪙 **Coin Flip** — 50/50 double-or-nothing · bet Fine cats\n"
            "🔢 **Higher/Lower** — free to play · streak multiplier\n"
            "🎟️ **Scratch Card** — costs 3 Fine cats · instant prizes\n"
        ),
        color=Colors.maroon,
    )

    class _LobbySelect(discord.ui.Select):
        def __init__(self):
            options = [
                discord.SelectOption(label="Catsino Spin",  value="spin",    emoji="🎲",
                                     description="Pay 5 Fine cats, win up to 15"),
                discord.SelectOption(label="Blackjack",     value="bj",      emoji="🃏",
                                     description="Classic card game vs the dealer"),
                discord.SelectOption(label="Coin Flip",     value="coin",    emoji="🪙",
                                     description="50/50 double-or-nothing"),
                discord.SelectOption(label="Higher/Lower",  value="hl",      emoji="🔢",
                                     description="Free to play, streak multiplier rewards"),
                discord.SelectOption(label="Scratch Card",  value="scratch", emoji="🎟️",
                                     description="Pay 3 Fine cats, reveal instant prizes"),
            ]
            super().__init__(placeholder="Choose a game…", options=options,
                             min_values=1, max_values=1, custom_id="casino_lobby_select")

        async def callback(self, inter: discord.Interaction):
            if inter.user.id != message.user.id:
                await do_funny(inter)
                return
            choice = self.values[0]
            if choice == "spin":
                await _casino_spin(inter, message, profile)
            elif choice == "bj":
                await _casino_blackjack_start(inter, message, profile)
            elif choice == "coin":
                await _casino_coinflip_start(inter, message, profile)
            elif choice == "hl":
                await _casino_higher_lower(inter, message, profile)
            elif choice == "scratch":
                await _casino_scratch(inter, message, profile)

    view = LayoutView(timeout=VIEW_TIMEOUT)
    view.add_item(_LobbySelect())
    try:
        await interaction.response.edit_message(embed=embed, view=view)
    except Exception:
        try:
            await interaction.edit_original_response(embed=embed, view=view)
        except Exception:
            await interaction.followup.send(embed=embed, view=view)


# ───────────────────────────────────────────────────────────────────────
#  Game 1 – Catsino Spin
# ───────────────────────────────────────────────────────────────────────

async def _casino_spin(interaction: discord.Interaction,
                       message:     discord.Interaction,
                       profile):
    if message.user.id + message.guild.id in casino_lock:
        await interaction.response.send_message("Finish your current game first!", ephemeral=True)
        return

    await profile.refresh_from_db()
    if profile.cat_Fine < 5:
        await interaction.response.send_message(
            f"You need at least **5 Fine cats** to spin. You only have **{profile.cat_Fine}**.",
            ephemeral=True,
        )
        await achemb(interaction, "broke", "followup")
        return

    await interaction.response.defer()
    casino_lock.append(message.user.id + message.guild.id)
    _ac_casino_reason = _ac_record_casino(message.user.id)
    if _ac_casino_reason:
        shared.bot.loop.create_task(_ac_send_report(
            user_id  = message.user.id,
            guild_id = message.guild.id,
            trigger  = _ac_casino_reason,
            context  = "Casino interaction — game entry",
        ))
    _ac_casino_reason = _ac_record_casino(message.user.id)
    if _ac_casino_reason:
        shared.bot.loop.create_task(_ac_send_report(
            user_id  = message.user.id,
            guild_id = message.guild.id,
            trigger  = _ac_casino_reason,
            context  = f"Casino interaction — game entry",
        ))
    profile.cat_Fine -= 5
    profile.gambles  += 1
    await profile.save()

    cat_type, amount = random.choices(_SPIN_PRIZES, weights=_SPIN_WEIGHTS)[0]

    reel_items = [
        f"{get_emoji('finecat')} Fine cat",
        f"{get_emoji('rarecat')} Rare cat",
        f"{get_emoji('epiccat')} Epic cat",
        f"{get_emoji('legendarycat')} Legendary cat",
        f"{get_emoji('divinecat')} Divine cat",
        f"{get_emoji('angelcat')} Angel cat",
    ]
    random.shuffle(reel_items)
    for item in reel_items:
        emb = discord.Embed(title="🎲 Catsino Spin", description=f"**{item}**", color=Colors.maroon)
        try:
            await interaction.edit_original_response(embed=emb, view=None)
        except Exception:
            pass
        await asyncio.sleep(0.9)

    await profile.refresh_from_db()
    if cat_type is not None and amount > 0:
        profile[f"cat_{cat_type}"] += amount
    await profile.save()

    label = _SPIN_LABELS.get(
        (cat_type, amount),
        f"🐱 1 {cat_type} cat!" if cat_type else "😿 Nothing",
    )

    # Balance line: always show Fine cats; also show the won type if it's not Fine
    balance_lines = f"Fine cats: **{profile.cat_Fine:,}** {get_emoji('finecat')}"
    if cat_type is not None and cat_type != "Fine":
        type_lc = cat_type.lower()
        balance_lines += (
            f"\n{cat_type} cats: **{profile[f'cat_{cat_type}']:,}** {get_emoji(f'{type_lc}cat')}"
        )

    result_emb = discord.Embed(
        title="🎲 Catsino Spin – Result",
        description=(
            f"**{label}**\n\n"
            f"{balance_lines}\n\n"
            f"*(Odds: Fine jackpot 6% · common cat ~11% · ultra-rare cat <1% · house edge ~9%)*"
        ),
        color=Colors.maroon,
    )

    spin_btn = Button(label="Spin again (−5 Fine cats)", style=ButtonStyle.blurple)
    back_btn = Button(label="Back to lobby",             style=ButtonStyle.grey)

    async def _respin(i: discord.Interaction):
        if i.user.id != message.user.id:
            await do_funny(i)
            return
        try:
            casino_lock.remove(message.user.id + message.guild.id)
        except ValueError:
            pass  # double-fire guard
        await _casino_spin(i, message, profile)

    async def _back(i: discord.Interaction):
        if i.user.id != message.user.id:
            await do_funny(i)
            return
        try:
            casino_lock.remove(message.user.id + message.guild.id)
        except ValueError:
            pass  # double-fire guard
        await _casino_lobby(i, message, profile)

    spin_btn.callback = _respin
    back_btn.callback = _back
    view = LayoutView(timeout=VIEW_TIMEOUT)
    view.add_item(spin_btn)
    view.add_item(back_btn)

    # Lock stays held until the user clicks a button — do NOT remove it here.

    await progress(interaction, profile, "casino_spin")
    await progress(interaction, profile, "any_game")
    if amount > 0:
        await progress(interaction, profile, "casino_win")
        await progress(interaction, profile, "casino_wins")
    if profile.gambles >= 10:
        await achemb(interaction, "gambling_one", "followup")
    if profile.gambles >= 50:
        await achemb(interaction, "gambling_two", "followup")

    try:
        await interaction.edit_original_response(embed=result_emb, view=view)
    except Exception:
        await interaction.followup.send(embed=result_emb, view=view)


# ───────────────────────────────────────────────────────────────────────
#  Game 2 – Blackjack
# ───────────────────────────────────────────────────────────────────────

async def _casino_blackjack_start(interaction: discord.Interaction,
                                   message:     discord.Interaction,
                                   profile):
    if message.user.id + message.guild.id in casino_lock:
        await interaction.response.send_message("Finish your current game first!", ephemeral=True)
        return

    await profile.refresh_from_db()
    if profile.cat_Fine <= 0:
        await interaction.response.send_message(
            "You need at least **1 Fine cat** to play Blackjack. You're broke!", ephemeral=True
        )
        await achemb(interaction, "broke", "followup")
        return

    class _BetModal(Modal, title="🃏 Blackjack – Place Your Bet"):
        bet = TextInput(
            label="Bet (Fine cats)",
            style=discord.TextStyle.short,
            placeholder=f"1 – {profile.cat_Fine}",
            required=True, min_length=1, max_length=6,
        )

        async def on_submit(self_m, inter: discord.Interaction):
            try:
                amount = int(self_m.bet.value)
            except ValueError:
                await inter.response.send_message("Enter a whole number.", ephemeral=True)
                return
            await profile.refresh_from_db()
            if amount <= 0 or amount > profile.cat_Fine:
                await inter.response.send_message(
                    f"Bet must be between 1 and {profile.cat_Fine} Fine cats.", ephemeral=True
                )
                return
            await _casino_blackjack_play(inter, message, profile, amount)

    await interaction.response.send_modal(_BetModal())


async def _casino_blackjack_play(interaction: discord.Interaction,
                                  message:     discord.Interaction,
                                  profile,
                                  bet: int):
    if message.user.id + message.guild.id in casino_lock:
        await interaction.response.send_message("Already in a game!", ephemeral=True)
        return

    await interaction.response.defer()
    casino_lock.append(message.user.id + message.guild.id)
    _ac_casino_reason = _ac_record_casino(message.user.id)
    if _ac_casino_reason:
        shared.bot.loop.create_task(_ac_send_report(
            user_id  = message.user.id,
            guild_id = message.guild.id,
            trigger  = _ac_casino_reason,
            context  = "Casino interaction — game entry",
        ))
    _ac_casino_reason = _ac_record_casino(message.user.id)
    if _ac_casino_reason:
        shared.bot.loop.create_task(_ac_send_report(
            user_id  = message.user.id,
            guild_id = message.guild.id,
            trigger  = _ac_casino_reason,
            context  = f"Casino interaction — game entry",
        ))

    await profile.refresh_from_db()
    profile.cat_Fine -= bet
    profile.gambles  += 1
    await profile.save()

    deck        = _build_deck()
    player_hand = [deck.pop(), deck.pop()]
    dealer_hand = [deck.pop(), deck.pop()]

    def _state_embed(ended: bool = False, result_text: str = "") -> discord.Embed:
        pval = _hand_value(player_hand)
        dval = _hand_value(dealer_hand)
        desc = (
            (f"{result_text}\n\n" if result_text else "") +
            f"**Bet:** {bet:,} Fine cats\n\n"
            f"🧑 **Your hand** ({pval})\n{_fmt_hand(player_hand)}\n\n"
            f"🤖 **Dealer's hand** {'(' + str(dval) + ')' if ended else '(?)'}\n"
            f"{_fmt_hand(dealer_hand, hide_second=not ended)}\n\n"
            f"Balance: **{profile.cat_Fine:,}** {get_emoji('finecat')} Fine cats"
        )
        return discord.Embed(title="🃏 Blackjack", description=desc, color=Colors.maroon)

    async def _finish(inter: discord.Interaction, result: str, payout: int):
        await profile.refresh_from_db()
        profile.cat_Fine += payout
        await profile.save()
        try:
            casino_lock.remove(message.user.id + message.guild.id)
        except ValueError:
            pass  # double-fire guard

        await progress(inter, profile, "casino_spin")
        await progress(inter, profile, "any_game")
        if payout > bet:
            await progress(inter, profile, "casino_win")
            await progress(inter, profile, "casino_wins")
        if profile.gambles >= 10:
            await achemb(inter, "gambling_one", "followup")
        if profile.gambles >= 50:
            await achemb(inter, "gambling_two", "followup")

        again_btn = Button(label=f"Play again (bet {bet})", style=ButtonStyle.blurple)
        back_btn  = Button(label="Back to lobby",            style=ButtonStyle.grey)

        async def _again(i: discord.Interaction):
            if i.user.id != message.user.id:
                await do_funny(i)
                return
            await _casino_blackjack_play(i, message, profile, bet)

        async def _back(i: discord.Interaction):
            if i.user.id != message.user.id:
                await do_funny(i)
                return
            await _casino_lobby(i, message, profile)

        again_btn.callback = _again
        back_btn.callback  = _back
        v = LayoutView(timeout=VIEW_TIMEOUT)
        v.add_item(again_btn)
        v.add_item(back_btn)

        emb = _state_embed(ended=True, result_text=result)
        try:
            await inter.edit_original_response(embed=emb, view=v)
        except Exception:
            await inter.followup.send(embed=emb, view=v)

    # Immediate blackjack check
    player_bj = _hand_value(player_hand) == 21
    dealer_bj = _hand_value(dealer_hand) == 21
    if player_bj and dealer_bj:
        await _finish(interaction, "🤝 Push – both have Blackjack! Bet returned.", bet)
        return
    if player_bj:
        payout = bet + int(bet * 1.5)
        await _finish(interaction, f"🎉 Blackjack! You win **+{payout - bet:,}** Fine cats!", payout)
        return
    if dealer_bj:
        await _finish(interaction, "😿 Dealer has Blackjack. You lose.", 0)
        return

    # Hit / Stand buttons
    async def _dealer_play(inter: discord.Interaction):
        while _hand_value(dealer_hand) < 17:
            dealer_hand.append(deck.pop())
        pval = _hand_value(player_hand)
        dval = _hand_value(dealer_hand)
        if dval > 21:
            await _finish(inter, f"🎉 Dealer busts at {dval}! You win **+{bet:,}** Fine cats!", bet * 2)
        elif pval > dval:
            await _finish(inter, f"✅ You win! {pval} vs {dval}. **+{bet:,}** Fine cats!", bet * 2)
        elif dval > pval:
            await _finish(inter, f"😿 Dealer wins. {dval} vs {pval}. You lose.", 0)
        else:
            await _finish(inter, f"🤝 Push at {pval}! Bet returned.", bet)

    async def _hit(inter: discord.Interaction):
        if inter.user.id != message.user.id:
            await do_funny(inter)
            return
        player_hand.append(deck.pop())
        pval = _hand_value(player_hand)
        if pval > 21:
            await inter.response.defer()
            await _finish(inter, f"💥 Bust! Your hand is {pval}. You lose.", 0)
        elif pval == 21:
            await inter.response.defer()
            await _dealer_play(inter)
        else:
            hit2  = Button(label="Hit",   style=ButtonStyle.green)
            stand2 = Button(label="Stand", style=ButtonStyle.red)
            hit2.callback   = _hit
            stand2.callback = _stand
            v = LayoutView(timeout=VIEW_TIMEOUT)
            v.add_item(hit2)
            v.add_item(stand2)
            await inter.response.edit_message(embed=_state_embed(), view=v)

    async def _stand(inter: discord.Interaction):
        if inter.user.id != message.user.id:
            await do_funny(inter)
            return
        await inter.response.defer()
        await _dealer_play(inter)

    hit_btn   = Button(label="Hit",   style=ButtonStyle.green)
    stand_btn = Button(label="Stand", style=ButtonStyle.red)
    hit_btn.callback   = _hit
    stand_btn.callback = _stand
    v = LayoutView(timeout=VIEW_TIMEOUT)
    v.add_item(hit_btn)
    v.add_item(stand_btn)

    try:
        await interaction.edit_original_response(embed=_state_embed(), view=v)
    except Exception:
        await interaction.followup.send(embed=_state_embed(), view=v)


# ───────────────────────────────────────────────────────────────────────
#  Game 3 – Coin Flip  (true 50/50, no house edge)
# ───────────────────────────────────────────────────────────────────────

async def _casino_coinflip_start(interaction: discord.Interaction,
                                  message:     discord.Interaction,
                                  profile):
    await profile.refresh_from_db()
    if profile.cat_Fine <= 0:
        await interaction.response.send_message(
            "You need at least **1 Fine cat** to flip. You're broke!", ephemeral=True
        )
        await achemb(interaction, "broke", "followup")
        return

    class _CoinModal(Modal, title="🪙 Coin Flip – Place Your Bet"):
        bet = TextInput(
            label="Bet (Fine cats)",
            style=discord.TextStyle.short,
            placeholder=f"1 – {profile.cat_Fine}",
            required=True, min_length=1, max_length=6,
        )
        side = TextInput(
            label="Heads or Tails?",
            style=discord.TextStyle.short,
            placeholder="heads / tails",
            required=True, min_length=4, max_length=5,
        )

        async def on_submit(self_m, inter: discord.Interaction):
            if self_m.side.value.lower() not in ("heads", "tails"):
                await inter.response.send_message("Choose **heads** or **tails**.", ephemeral=True)
                return
            try:
                amount = int(self_m.bet.value)
            except ValueError:
                await inter.response.send_message("Enter a whole number.", ephemeral=True)
                return
            await profile.refresh_from_db()
            if amount <= 0 or amount > profile.cat_Fine:
                await inter.response.send_message(
                    f"Bet must be between 1 and {profile.cat_Fine}.", ephemeral=True
                )
                return

            await inter.response.defer()
            casino_lock.append(message.user.id + message.guild.id)
            _ac_casino_reason = _ac_record_casino(message.user.id)
            if _ac_casino_reason:
                shared.bot.loop.create_task(_ac_send_report(
                    user_id  = message.user.id,
                    guild_id = message.guild.id,
                    trigger  = _ac_casino_reason,
                    context  = "Casino interaction — game entry",
                ))

            chosen = self_m.side.value.lower()
            result = random.choice(["heads", "tails"])
            won    = chosen == result

            for _ in range(5):
                emb = discord.Embed(
                    title="🪙 Coin Flip", description="Flipping… 🪙", color=Colors.maroon
                )
                try:
                    await inter.edit_original_response(embed=emb, view=None)
                except Exception:
                    pass
                await asyncio.sleep(0.6)

            await profile.refresh_from_db()
            profile.cat_Fine += amount if won else -amount
            profile.gambles  += 1
            await profile.save()
            try:
                casino_lock.remove(message.user.id + message.guild.id)
            except ValueError:
                pass  # double-fire guard

            await progress(inter, profile, "casino_spin")
            await progress(inter, profile, "any_game")
            if won:
                await progress(inter, profile, "casino_win")
                await progress(inter, profile, "casino_wins")
            if profile.gambles >= 10:
                await achemb(inter, "gambling_one", "followup")
            if profile.gambles >= 50:
                await achemb(inter, "gambling_two", "followup")

            outcome = (
                f"✅ **{result.capitalize()}! You win +{amount:,} Fine cats!**"
                if won else
                f"😿 **{result.capitalize()}. You lose {amount:,} Fine cats.**"
            )
            result_emb = discord.Embed(
                title="🪙 Coin Flip",
                description=(
                    f"You chose: **{chosen.capitalize()}**\n"
                    f"Result: **{result.capitalize()}** 🪙\n\n"
                    f"{outcome}\n\n"
                    f"Balance: **{profile.cat_Fine:,}** {get_emoji('finecat')} Fine cats\n\n"
                    f"*(True 50/50 — no house edge)*"
                ),
                color=Colors.maroon,
            )

            again_btn = Button(label="Flip again", style=ButtonStyle.blurple)
            back_btn  = Button(label="Back to lobby", style=ButtonStyle.grey)

            async def _again(i: discord.Interaction):
                if i.user.id != message.user.id:
                    await do_funny(i)
                    return
                await _casino_coinflip_start(i, message, profile)

            async def _back(i: discord.Interaction):
                if i.user.id != message.user.id:
                    await do_funny(i)
                    return
                await _casino_lobby(i, message, profile)

            again_btn.callback = _again
            back_btn.callback  = _back
            v = LayoutView(timeout=VIEW_TIMEOUT)
            v.add_item(again_btn)
            v.add_item(back_btn)
            try:
                await inter.edit_original_response(embed=result_emb, view=v)
            except Exception:
                await inter.followup.send(embed=result_emb, view=v)

    await interaction.response.send_modal(_CoinModal())


# ───────────────────────────────────────────────────────────────────────
#  Game 4 – Higher / Lower  (free, streak multiplier)
# ───────────────────────────────────────────────────────────────────────

async def _casino_higher_lower(interaction: discord.Interaction,
                                message:     discord.Interaction,
                                profile):
    if message.user.id + message.guild.id in casino_lock:
        await interaction.response.send_message("Finish your current game first!", ephemeral=True)
        return

    await interaction.response.defer()
    casino_lock.append(message.user.id + message.guild.id)
    _ac_casino_reason = _ac_record_casino(message.user.id)
    if _ac_casino_reason:
        shared.bot.loop.create_task(_ac_send_report(
            user_id  = message.user.id,
            guild_id = message.guild.id,
            trigger  = _ac_casino_reason,
            context  = "Casino interaction — game entry",
        ))
    _ac_casino_reason = _ac_record_casino(message.user.id)
    if _ac_casino_reason:
        shared.bot.loop.create_task(_ac_send_report(
            user_id  = message.user.id,
            guild_id = message.guild.id,
            trigger  = _ac_casino_reason,
            context  = f"Casino interaction — game entry",
        ))
    profile.gambles += 1
    await profile.save()

    current = random.randint(1, 10)
    streak  = 0

    async def _show_round(inter: discord.Interaction, prev_result: str = ""):
        nonlocal current, streak
        desc = (
            (f"{prev_result}\n\n" if prev_result else "") +
            f"Current number: **{current}** / 10\n"
            f"Streak: **{streak}** (earned **{_hl_earned(streak):,}** Fine cats so far)\n\n"
            f"Will the next number be **Higher**, **Lower**, or **Equal**?\n"
            f"*(Equal pays ×3 streak bonus but is rare — 1 in 10 chance)*"
        )
        emb = discord.Embed(title="🔢 Higher / Lower", description=desc, color=Colors.maroon)

        high_btn  = Button(label="Higher ⬆️",  style=ButtonStyle.green)
        low_btn   = Button(label="Lower ⬇️",   style=ButtonStyle.red)
        equal_btn = Button(label="Equal ➡️",   style=ButtonStyle.grey)
        cash_btn  = Button(
            label=f"Cash out ({_hl_earned(streak):,} Fine cats)",
            style=ButtonStyle.blurple,
            disabled=(streak == 0),
        )

        async def _guess(i: discord.Interaction, guess: str):
            nonlocal current, streak
            if i.user.id != message.user.id:
                await do_funny(i)
                return
            await i.response.defer()

            nxt = random.randint(1, 10)
            actual = "higher" if nxt > current else ("lower" if nxt < current else "equal")
            correct = (guess == actual)

            if correct and actual == "equal":
                streak += 3
            elif correct:
                streak += 1

            if not correct:
                try:
                    casino_lock.remove(message.user.id + message.guild.id)
                except ValueError:
                    pass  # double-fire guard
                await progress(i, profile, "casino_spin")
                await progress(i, profile, "any_game")

                fail_emb = discord.Embed(
                    title="🔢 Higher / Lower – Game Over",
                    description=(
                        f"The number was **{nxt}** "
                        f"({'higher' if nxt > current else 'lower' if nxt < current else 'equal'} than {current}).\n"
                        f"You guessed **{guess}** — wrong!\n\n"
                        f"Streak was **{streak}**. You earned nothing.\n\n"
                        f"*(Tip: Cash out while you're ahead!)*"
                    ),
                    color=Colors.maroon,
                )
                again_btn = Button(label="Play again", style=ButtonStyle.blurple)
                back_btn  = Button(label="Back to lobby", style=ButtonStyle.grey)

                async def _again(ii: discord.Interaction):
                    if ii.user.id != message.user.id:
                        await do_funny(ii)
                        return
                    await _casino_higher_lower(ii, message, profile)

                async def _back(ii: discord.Interaction):
                    if ii.user.id != message.user.id:
                        await do_funny(ii)
                        return
                    await _casino_lobby(ii, message, profile)

                again_btn.callback = _again
                back_btn.callback  = _back
                vv = LayoutView(timeout=VIEW_TIMEOUT)
                vv.add_item(again_btn)
                vv.add_item(back_btn)
                try:
                    await i.edit_original_response(embed=fail_emb, view=vv)
                except Exception:
                    await i.followup.send(embed=fail_emb, view=vv)
                return

            res_text = (
                f"✅ Correct! The number was **{nxt}** ({actual})."
                + (" **EQUAL – ×3 streak bonus!**" if actual == "equal" and guess == "equal" else "")
            )
            current = nxt
            await _show_round(i, prev_result=res_text)

        async def _cash(i: discord.Interaction):
            nonlocal streak
            if i.user.id != message.user.id:
                await do_funny(i)
                return
            earned = _hl_earned(streak)
            await i.response.defer()
            await profile.refresh_from_db()
            profile.cat_Fine += earned
            await profile.save()
            try:
                casino_lock.remove(message.user.id + message.guild.id)
            except ValueError:
                pass  # double-fire guard

            await progress(i, profile, "casino_spin")
            await progress(i, profile, "any_game")
            if earned > 0:
                await progress(i, profile, "casino_win")
                await progress(i, profile, "casino_wins")

            cash_emb = discord.Embed(
                title="🔢 Higher / Lower – Cashed Out!",
                description=(
                    f"Streak: **{streak}**\n"
                    f"Earned: **+{earned:,}** {get_emoji('finecat')} Fine cats\n"
                    f"Balance: **{profile.cat_Fine:,}** Fine cats"
                ),
                color=Colors.maroon,
            )
            again_btn = Button(label="Play again", style=ButtonStyle.blurple)
            back_btn  = Button(label="Back to lobby", style=ButtonStyle.grey)

            async def _again2(ii: discord.Interaction):
                if ii.user.id != message.user.id:
                    await do_funny(ii)
                    return
                await _casino_higher_lower(ii, message, profile)

            async def _back2(ii: discord.Interaction):
                if ii.user.id != message.user.id:
                    await do_funny(ii)
                    return
                await _casino_lobby(ii, message, profile)

            again_btn.callback = _again2
            back_btn.callback  = _back2
            vv = LayoutView(timeout=VIEW_TIMEOUT)
            vv.add_item(again_btn)
            vv.add_item(back_btn)
            try:
                await i.edit_original_response(embed=cash_emb, view=vv)
            except Exception:
                await i.followup.send(embed=cash_emb, view=vv)

        high_btn.callback  = lambda i: _guess(i, "higher")
        low_btn.callback   = lambda i: _guess(i, "lower")
        equal_btn.callback = lambda i: _guess(i, "equal")
        cash_btn.callback  = _cash

        v = LayoutView(timeout=VIEW_TIMEOUT)
        v.add_item(high_btn)
        v.add_item(low_btn)
        v.add_item(equal_btn)
        v.add_item(cash_btn)
        try:
            await inter.edit_original_response(embed=emb, view=v)
        except Exception:
            await inter.followup.send(embed=emb, view=v)

    await _show_round(interaction)


# ───────────────────────────────────────────────────────────────────────
#  Game 5 – Scratch Card
# ───────────────────────────────────────────────────────────────────────

async def _casino_scratch(interaction: discord.Interaction,
                           message:     discord.Interaction,
                           profile):
    if message.user.id + message.guild.id in casino_lock:
        await interaction.response.send_message("Finish your current game first!", ephemeral=True)
        return

    await profile.refresh_from_db()
    if profile.cat_Fine < 3:
        await interaction.response.send_message(
            f"You need **3 Fine cats** to buy a scratch card. You only have **{profile.cat_Fine}**.",
            ephemeral=True,
        )
        await achemb(interaction, "broke", "followup")
        return

    await interaction.response.defer()
    casino_lock.append(message.user.id + message.guild.id)
    _ac_casino_reason = _ac_record_casino(message.user.id)
    if _ac_casino_reason:
        shared.bot.loop.create_task(_ac_send_report(
            user_id  = message.user.id,
            guild_id = message.guild.id,
            trigger  = _ac_casino_reason,
            context  = "Casino interaction — game entry",
        ))
    _ac_casino_reason = _ac_record_casino(message.user.id)
    if _ac_casino_reason:
        shared.bot.loop.create_task(_ac_send_report(
            user_id  = message.user.id,
            guild_id = message.guild.id,
            trigger  = _ac_casino_reason,
            context  = f"Casino interaction — game entry",
        ))
    profile.cat_Fine -= 3
    profile.gambles  += 1
    await profile.save()

    cells = random.choices(_SCRATCH_SYMBOLS, weights=_SCRATCH_WEIGHTS, k=6)

    counts = Counter(cells)
    most_common_sym, most_common_cnt = counts.most_common(1)[0]
    if most_common_cnt >= 6:
        payout     = _SCRATCH_PRIZES[most_common_sym] * 10
        prize_text = f"🎊 **JACKPOT!** 6× {most_common_sym} → **+{payout}** Fine cats!"
    elif most_common_cnt >= 3:
        payout     = _SCRATCH_PRIZES[most_common_sym] * most_common_cnt
        prize_text = f"🎉 **{most_common_cnt}× {most_common_sym}** → **+{payout}** Fine cats!"
    else:
        payout     = 0
        prize_text = "😿 No matching symbols — better luck next time!"

    revealed = ["❓"] * 6
    for idx in range(6):
        revealed[idx] = cells[idx]
        grid = " ".join(revealed[:3]) + "\n" + " ".join(revealed[3:])
        emb = discord.Embed(
            title="🎟️ Scratch Card",
            description=f"Scratching…\n\n{grid}",
            color=Colors.maroon,
        )
        try:
            await interaction.edit_original_response(embed=emb, view=None)
        except Exception:
            pass
        await asyncio.sleep(0.7)

    await profile.refresh_from_db()
    profile.cat_Fine += payout
    await profile.save()
    try:
        casino_lock.remove(message.user.id + message.guild.id)
    except ValueError:
        pass  # double-fire guard

    await progress(interaction, profile, "casino_spin")
    await progress(interaction, profile, "any_game")
    if payout > 0:
        await progress(interaction, profile, "casino_win")
        await progress(interaction, profile, "casino_wins")
    if profile.gambles >= 10:
        await achemb(interaction, "gambling_one", "followup")
    if profile.gambles >= 50:
        await achemb(interaction, "gambling_two", "followup")

    final_grid = " ".join(cells[:3]) + "\n" + " ".join(cells[3:])
    final_emb  = discord.Embed(
        title="🎟️ Scratch Card – Result",
        description=(
            f"{final_grid}\n\n"
            f"{prize_text}\n\n"
            f"Balance: **{profile.cat_Fine:,}** {get_emoji('finecat')} Fine cats\n\n"
            f"*(3-of-a-kind wins · jackpot = all 6 identical)*"
        ),
        color=Colors.maroon,
    )

    again_btn = Button(label="Buy another card (−3 Fine cats)", style=ButtonStyle.blurple)
    back_btn  = Button(label="Back to lobby",                    style=ButtonStyle.grey)

    async def _again(i: discord.Interaction):
        if i.user.id != message.user.id:
            await do_funny(i)
            return
        await _casino_scratch(i, message, profile)

    async def _back(i: discord.Interaction):
        if i.user.id != message.user.id:
            await do_funny(i)
            return
        await _casino_lobby(i, message, profile)

    again_btn.callback = _again
    back_btn.callback  = _back
    v = LayoutView(timeout=VIEW_TIMEOUT)
    v.add_item(again_btn)
    v.add_item(back_btn)
    try:
        await interaction.edit_original_response(embed=final_emb, view=v)
    except Exception:
        await interaction.followup.send(embed=final_emb, view=v)


# ───────────────────────────────────────────────────────────────────────
#  /slots
# ───────────────────────────────────────────────────────────────────────

@shared.bot.tree.command(description="oh no")
async def slots(message: discord.Interaction):
    if message.user.id + message.guild.id in slots_lock:
        await message.response.send_message(
            "you get kicked from the slot machine because you are already there, and two of you playing at once would cause a glitch in the universe",
            ephemeral=True,
        )
        await achemb(message, "paradoxical_gambler", "followup")
        return

    await message.response.defer()

    profile = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
    total_spins, total_wins, total_big_wins = (
        await Profile.sum("slot_spins", "slot_spins > 0"),
        await Profile.sum("slot_wins", "slot_wins > 0"),
        await Profile.sum("slot_big_wins", "slot_big_wins > 0"),
    )
    embed = discord.Embed(
        title=":slot_machine: The Slot Machine",
        description=f"__Your stats__\n{profile.slot_spins:,} spins\n{profile.slot_wins:,} wins\n{profile.slot_big_wins:,} big wins\n\n__Global stats__\n{total_spins:,} spins\n{total_wins:,} wins\n{total_big_wins:,} big wins",
        color=Colors.maroon,
    )

    async def remove_debt(interaction):
        nonlocal message
        if interaction.user.id != message.user.id:
            await do_funny(interaction)
            return
        await profile.refresh_from_db()

        # remove debt
        for i in cattypes:
            profile[f"cat_{i}"] = max(0, profile[f"cat_{i}"])

        await profile.save()
        await interaction.response.send_message("You have removed your debts! Life is wonderful!", ephemeral=True)
        await achemb(interaction, "debt", "followup")

    async def spin(interaction):
        nonlocal message
        if interaction.user.id != message.user.id:
            await do_funny(interaction)
            return
        if message.user.id + message.guild.id in slots_lock:
            await interaction.response.send_message(
                "you get kicked from the slot machine because you are already there, and two of you playing at once would cause a glitch in the universe",
                ephemeral=True,
            )
            return
        await profile.refresh_from_db()

        await interaction.response.defer()
        slots_lock.append(message.user.id + message.guild.id)
        profile.slot_spins += 1
        await profile.save()

        try:
            await achemb(interaction, "slots", "followup")
            await progress(message, profile, "slots")
            await progress(message, profile, "slots2")
        except Exception:
            pass

        variants = ["🍒", "🍋", "🍇", "🔔", "⭐", ":seven:"]
        reel_durations = [random.randint(9, 12), random.randint(15, 22), random.randint(25, 28)]
        random.shuffle(reel_durations)

        # the k number is much cycles it will go before stopping + 1
        col1 = random.choices(variants, k=reel_durations[0])
        col2 = random.choices(variants, k=reel_durations[1])
        col3 = random.choices(variants, k=reel_durations[2])

        blank_emoji = get_emoji("empty")
        for slot_loop_ind in range(1, max(reel_durations) - 1):
            current1 = min(len(col1) - 2, slot_loop_ind)
            current2 = min(len(col2) - 2, slot_loop_ind)
            current3 = min(len(col3) - 2, slot_loop_ind)
            desc = ""
            for offset in [-1, 0, 1]:
                if offset == 0:
                    desc += f"➡️ {col1[current1 + offset]} {col2[current2 + offset]} {col3[current3 + offset]} ⬅️\n"
                else:
                    desc += f"{blank_emoji} {col1[current1 + offset]} {col2[current2 + offset]} {col3[current3 + offset]} {blank_emoji}\n"
            embed = discord.Embed(
                title=":slot_machine: The Slot Machine",
                description=desc,
                color=Colors.maroon,
            )
            try:
                await interaction.edit_original_response(embed=embed, view=None)
            except Exception:
                pass
            await asyncio.sleep(0.5)

        await profile.refresh_from_db()
        big_win = False
        if col1[current1] == col2[current2] == col3[current3]:
            profile.slot_wins += 1
            if col1[current1] == ":seven:":
                desc = "**BIG WIN!**\n\n" + desc
                profile.slot_big_wins += 1
                big_win = True
                await profile.save()
                await achemb(interaction, "big_win_slots", "followup")
                await progress(message, profile, "slots_bigwin")
                await progress(message, profile, "big_win")  # misc quest "Get a Big Win in /slots"
            else:
                desc = "**You win!**\n\n" + desc
                await profile.save()
            await achemb(interaction, "win_slots", "followup")
            await progress(message, profile, "slots_win")
        else:
            desc = "**You lose!**\n\n" + desc

        button = Button(label="Spin", style=ButtonStyle.blurple)
        button.callback = spin

        myview = LayoutView(timeout=VIEW_TIMEOUT)
        myview.add_item(button)

        if big_win:
            # check if user has debt in any cat type
            has_debt = False
            for i in cattypes:
                if profile[f"cat_{i}"] < 0:
                    has_debt = True
                    break
            if has_debt:
                desc += "\n\n**You can remove your debt!**"
                button = Button(label="Remove Debt", style=ButtonStyle.blurple)
                button.callback = remove_debt
                myview.add_item(button)

        slots_lock.remove(message.user.id + message.guild.id)

        embed = discord.Embed(title=":slot_machine: The Slot Machine", description=desc, color=Colors.maroon)

        try:
            await interaction.edit_original_response(embed=embed, view=myview)
        except Exception:
            await interaction.followup.send(embed=embed, view=myview)

    button = Button(label="Spin", style=ButtonStyle.blurple)
    button.callback = spin

    myview = LayoutView(timeout=VIEW_TIMEOUT)
    myview.add_item(button)

    await message.followup.send(embed=embed, view=myview)


# ───────────────────────────────────────────────────────────────────────
#  /roulette
# ───────────────────────────────────────────────────────────────────────

@shared.bot.tree.command(description="Spin the roulette wheel — European rules, honest odds shown")
async def roulette(message: discord.Interaction):
    user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)

    # European roulette: 37 pockets (0–36).
    # Color map indexed by pocket number.
    _ROUL_COLORS = [
        "green",                                              # 0
        "red","black","red","black","red","black","red","black","red","black",   # 1-10
        "black","red","black","red","black","red","black","red",                 # 11-18
        "red","black","red","black","red","black","red","black","red","black",   # 19-28
        "black","red","black","red","black","red","black","red",                 # 29-36
    ]
    _ROUL_EMOJI = {"red": "🔴", "black": "⚫", "green": "🟢"}

    class _RouletteModal(Modal, title="🎡 Roulette — Place Your Bet"):
        bettype = TextInput(
            min_length=1, max_length=6,
            label="Bet type",
            style=discord.TextStyle.short,
            required=True,
            placeholder="red / black / green / 0–36",
        )
        betamount = TextInput(
            min_length=1,
            label="Bet amount (cat dollars)",
            style=discord.TextStyle.short,
            required=True,
            placeholder="100",
        )

        async def on_submit(self_m, interaction: discord.Interaction):
            valids = ["red", "black", "green"] + [str(i) for i in range(37)]
            if self_m.bettype.value.lower() not in valids:
                await interaction.response.send_message(
                    "Invalid bet. Choose **red**, **black**, **green**, or a number **0–36**.",
                    ephemeral=True,
                )
                return

            try:
                bet_amount = int(self_m.betamount.value)
                if bet_amount <= 0:
                    raise ValueError
                max_bet = max(user.roulette_balance, 100)
                if bet_amount > max_bet:
                    await interaction.response.send_message(
                        f"Your max bet is **{max_bet:,}** cat dollars.", ephemeral=True
                    )
                    return
            except ValueError:
                await interaction.response.send_message(
                    "Enter a positive whole number.", ephemeral=True
                )
                return

            await interaction.response.defer()

            bet_type     = self_m.bettype.value.lower()
            final_number = random.randint(0, 36)
            final_color  = _ROUL_COLORS[final_number]

            # Spinning animation
            for wait in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.5]:
                spin_n = random.randint(0, 36)
                spin_c = _ROUL_COLORS[spin_n]
                emb = discord.Embed(
                    title="🎡 Spinning…",
                    description=(
                        f"Your bet: **{bet_amount:,}** cat dollars on "
                        f"**{self_m.bettype.value.capitalize()}**\n\n"
                        f"{_ROUL_EMOJI[spin_c]} **{spin_n}**"
                    ),
                    color=Colors.maroon,
                )
                try:
                    await interaction.edit_original_response(embed=emb, view=None)
                except Exception:
                    pass
                await asyncio.sleep(wait)

            # Settle the bet
            user.roulette_balance -= bet_amount
            user.roulette_spins   += 1
            win        = False
            number_bet = bet_type not in ("red", "black", "green")

            if number_bet or bet_type == "green":
                # Exact number or green (0): 36:1 payout
                if str(final_number) == bet_type or (bet_type == "green" and final_color == "green"):
                    user.roulette_balance += bet_amount * 36
                    user.roulette_wins    += 1
                    win = True
            else:
                # Red / Black: even money (2:1)
                if final_color == bet_type:
                    user.roulette_balance += bet_amount * 2
                    user.roulette_wins    += 1
                    win = True

            user.roulette_balance = int(round(user.roulette_balance))
            await user.save()

            broke_note = (
                "\n\nYou're in debt — you can still bet up to **100** cat dollars."
                if user.roulette_balance <= 0 else ""
            )
            if bet_type in ("red", "black"):
                odds_note = "Red/Black pays **2:1** · ~48.6% win chance · house edge 2.7%"
            else:
                odds_note = "Number/Green pays **36:1** · ~2.7% win chance · house edge 2.7%"

            result_emb = discord.Embed(
                title="🏆 Winner!" if win else "😿 Womp womp",
                description=(
                    f"You bet **{bet_amount:,}** cat dollars on "
                    f"**{self_m.bettype.value.capitalize()}**\n\n"
                    f"{_ROUL_EMOJI[final_color]} **{final_number}** "
                    f"({final_color.capitalize()})\n\n"
                    f"Balance: **{user.roulette_balance:,}** cat dollars{broke_note}\n\n"
                    f"*{odds_note}*"
                ),
                color=Colors.maroon,
            )
            view = LayoutView(timeout=VIEW_TIMEOUT)
            spin_btn = Button(label="Spin again", style=ButtonStyle.blurple)
            spin_btn.callback = modal_select
            view.add_item(spin_btn)
            try:
                await interaction.edit_original_response(embed=result_emb, view=view)
            except Exception:
                await interaction.followup.send(embed=result_emb, view=view)

            if win:
                await progress(message, user, "roulette")
                await progress(message, user, "roulette_streak")
                await progress(message, user, "any_game")
                await achemb(interaction, "roulette_winner", "followup")
                if number_bet or bet_type == "green":
                    await achemb(interaction, "roulette_prodigy", "followup")
            if user.roulette_balance < 0:
                await achemb(interaction, "failed_gambler", "followup")
            await progress(message, user, "roulette_spin")

    async def modal_select(interaction: discord.Interaction):
        if interaction.user != message.user:
            await do_funny(interaction)
            return
        await interaction.response.send_modal(_RouletteModal())

    broke_note = (
        "\n\nYou're in debt — you can still bet up to **100** cat dollars."
        if user.roulette_balance <= 0 else ""
    )
    lobby_emb = discord.Embed(
        title="🎡 Roulette Table",
        description=(
            f"Balance: **{user.roulette_balance:,}** cat dollars{broke_note}\n\n"
            "**Bet options:**\n"
            "🔴 **red** / ⚫ **black** — pays **2:1** · ~48.6% win chance\n"
            "🟢 **green** — pays **36:1** · ~2.7% win chance\n"
            "🔢 **0–36** (exact number) — pays **36:1** · ~2.7% win chance\n\n"
            "*House edge: 2.7% — the same as a real European roulette table.*"
        ),
        color=Colors.maroon,
    )
    view = LayoutView(timeout=VIEW_TIMEOUT)
    spin_btn = Button(label="Place a bet", style=ButtonStyle.blurple)
    spin_btn.callback = modal_select
    view.add_item(spin_btn)
    await message.response.send_message(embed=lobby_emb, view=view)

    if user.roulette_balance < 0:
        await achemb(message, "failed_gambler", "followup")
